# Copyright 2017, Inderpreet Singh, All rights reserved.

import signal
import sys
import time
import argparse
import os
import logging
from datetime import datetime
from typing import Optional, Type, TypeVar, List, Dict
import shutil
import platform

# my libs
from common import ServiceExit, Context, Constants, Config, Args, AppError
from common import ServiceRestart
from common import Localization, Status, ConfigError, Persist, PersistError
from common import PathPairManager, NetworkMountManager
from common.log_manager import LogManager
from common.mount_utils import do_mount, MountResult
from controller import Controller, ControllerJob, ControllerPersist, AutoQueue, AutoQueuePersist
from web import WebAppJob, WebAppBuilder


T_Persist = TypeVar("T_Persist", bound=Persist)


class Rapidcopy:
    """
    Implements the service for RapidCopy
    It is run in the main thread (no daemonization)
    """

    __FILE_CONFIG = "settings.cfg"
    __FILE_AUTO_QUEUE_PERSIST = "autoqueue.persist"
    __FILE_CONTROLLER_PERSIST = "controller.persist"
    __CONFIG_DUMMY_VALUE = "<replace me>"

    # This logger is used to print any exceptions caught at top module
    logger: logging.Logger | None = None

    def __init__(self):
        # Parse the args
        args = self._parse_args(sys.argv[1:])

        # Create/load config
        config: Config
        self.config_path = os.path.join(args.config_dir, Rapidcopy.__FILE_CONFIG)
        if os.path.isfile(self.config_path):
            try:
                config = Config.from_file(self.config_path)
            except (ConfigError, PersistError):
                Rapidcopy.__backup_file(self.config_path)
                # Create default config since loading failed
                config = Rapidcopy._create_default_config()
                config.to_file(self.config_path)
        else:
            config = Rapidcopy._create_default_config()
            config.to_file(self.config_path)

        # Determine the true value of debug
        is_debug = args.debug or config.general.debug

        # Create context args
        ctx_args = Args()
        ctx_args.local_path_to_scanfs = args.scanfs
        ctx_args.html_path = args.html
        ctx_args.debug = is_debug
        ctx_args.exit = args.exit
        ctx_args.log_dir = args.logdir

        # Logger setup using LogManager
        # Determine log level from config (defaults to INFO, ignored if debug=True)
        log_level = config.general.log_level if config.general.log_level else "INFO"

        LogManager.initialize(
            log_dir=args.logdir,
            log_level=log_level,
            debug=is_debug,
            use_json=False,  # Can be made configurable in the future
        )

        logger = LogManager.get_main_logger()
        Rapidcopy.logger = logger
        web_access_logger = LogManager.get_web_access_logger()
        logger.info("Debug mode is {}.".format("enabled" if is_debug else "disabled"))

        # Create status
        status = Status()

        # Initialize PathPairManager for multi-path support
        path_pair_manager = PathPairManager(args.config_dir)
        path_pair_manager.load()

        # Migrate legacy single-path config to path pairs if needed
        if config.lftp.remote_path and config.lftp.local_path:
            if path_pair_manager.migrate_from_config(
                remote_path=config.lftp.remote_path, local_path=config.lftp.local_path
            ):
                logger.info("Migrated legacy path config to path pairs")

        # Initialize NetworkMountManager for NFS/CIFS mount support
        network_mount_manager = NetworkMountManager(args.config_dir)
        network_mount_manager.load()

        # Create context
        self.context = Context(
            logger=logger,
            web_access_logger=web_access_logger,
            config=config,
            args=ctx_args,
            status=status,
            path_pair_manager=path_pair_manager,
            network_mount_manager=network_mount_manager,
        )

        # Register the signal handlers
        signal.signal(signal.SIGTERM, self.signal)
        signal.signal(signal.SIGINT, self.signal)

        # Print context to log
        self.context.print_to_log()

        # Load the persists
        self.controller_persist_path = os.path.join(args.config_dir, Rapidcopy.__FILE_CONTROLLER_PERSIST)
        self.controller_persist = self._load_persist(ControllerPersist, self.controller_persist_path)

        self.auto_queue_persist_path = os.path.join(args.config_dir, Rapidcopy.__FILE_AUTO_QUEUE_PERSIST)
        self.auto_queue_persist = self._load_persist(AutoQueuePersist, self.auto_queue_persist_path)

    def run(self):
        self.context.logger.info("Starting RapidCopy")
        self.context.logger.info("Platform: {}".format(platform.machine()))

        # Auto-mount enabled network mounts on startup
        self._auto_mount_network_shares()

        # Create controller
        controller = Controller(self.context, self.controller_persist)

        # Create auto queue
        auto_queue = AutoQueue(self.context, self.auto_queue_persist, controller)

        # Create web app
        web_app_builder = WebAppBuilder(self.context, controller, self.auto_queue_persist)
        web_app = web_app_builder.build()

        # Define child threads
        controller_job = ControllerJob(
            context=self.context.create_child_context(ControllerJob.__name__),
            controller=controller,
            auto_queue=auto_queue,
        )
        webapp_job = WebAppJob(context=self.context.create_child_context(WebAppJob.__name__), web_app=web_app)

        do_start_controller = True

        # Initial checks to see if we should bother starting the controller
        # Pass path_pair_manager to skip legacy path validation if path pairs are configured
        incomplete_fields = Rapidcopy._detect_incomplete_config(self.context.config, self.context.path_pair_manager)
        if incomplete_fields:
            if not self.context.args.exit:
                do_start_controller = False
                self.context.logger.error("Config is incomplete: %s", ", ".join(incomplete_fields))
                self.context.status.server.up = False
                self.context.status.server.error_msg = Localization.Error.SETTINGS_INCOMPLETE_FIELDS.format(
                    ", ".join(incomplete_fields)
                )
            else:
                raise AppError("Config is incomplete: {}".format(", ".join(incomplete_fields)))

        # Start child threads here
        if do_start_controller:
            controller_job.start()
        webapp_job.start()

        try:
            prev_persist_timestamp = datetime.now()

            # Thread loop
            while True:
                # Persist to file occasionally
                now = datetime.now()
                if (now - prev_persist_timestamp).total_seconds() > Constants.MIN_PERSIST_TO_FILE_INTERVAL_IN_SECS:
                    prev_persist_timestamp = now
                    self.persist()

                # Propagate exceptions
                webapp_job.propagate_exception()
                # Catch controller exceptions and keep running, but notify the web server of the error
                try:
                    controller_job.propagate_exception()
                except AppError as exc:
                    if not self.context.args.exit:
                        self.context.status.server.up = False
                        self.context.status.server.error_msg = str(exc)
                        Rapidcopy.logger.exception("Caught exception")
                    else:
                        raise

                # Check if a restart is requested
                if web_app_builder.server_handler.is_restart_requested():
                    raise ServiceRestart()

                # Nothing else to do
                time.sleep(Constants.MAIN_THREAD_SLEEP_INTERVAL_IN_SECS)

        except Exception:
            self.context.logger.info("Exiting Rapidcopy")

            # This sleep is important to allow the jobs to finish setup before we terminate them
            # If we kill too early, the jobs may leave lingering threads around
            # Note: There might be a better way to ensure that job setup has completed, but this
            #       will do for now
            time.sleep(Constants.MAIN_THREAD_SLEEP_INTERVAL_IN_SECS)

            # Join all the threads here
            if do_start_controller:
                controller_job.terminate()
            webapp_job.terminate()

            # Wait for the threads to close
            if do_start_controller:
                controller_job.join()
            webapp_job.join()

            # Last persist
            self.persist()

            # Raise any exceptions so they can be logged properly
            # Note: ServiceRestart and ServiceExit will be caught and handled
            #       by outer code
            raise

    def persist(self):
        # Save the persists
        self.context.logger.debug("Persisting states to file")
        self.controller_persist.to_file(self.controller_persist_path)
        self.auto_queue_persist.to_file(self.auto_queue_persist_path)
        # Only backup and write settings.cfg if the content has actually changed
        new_config_str = self.context.config.to_str()
        try:
            with open(self.config_path) as f:
                existing_config_str = f.read()
        except OSError:
            existing_config_str = None
        if new_config_str != existing_config_str:
            Rapidcopy.__backup_file(self.config_path)
            with open(self.config_path, "w") as f:
                f.write(new_config_str)

    def _auto_mount_network_shares(self):
        """
        Auto-mount enabled network shares on startup.
        Logs warnings for any mounts that fail but continues startup.
        """
        if not self.context.network_mount_manager:
            return

        enabled_mounts = self.context.network_mount_manager.get_enabled_mounts()
        if not enabled_mounts:
            return

        self.context.logger.info(f"Auto-mounting {len(enabled_mounts)} network share(s)...")

        for mount in enabled_mounts:
            try:
                result = do_mount(mount, self.context.network_mount_manager.config_dir, self.context.logger)
                if result.result == MountResult.SUCCESS:
                    self.context.logger.info(f"Mounted: {mount.name} -> {mount.mount_point}")
                elif result.result == MountResult.ALREADY_MOUNTED:
                    self.context.logger.debug(f"Already mounted: {mount.name}")
                else:
                    self.context.logger.warning(f"Failed to mount {mount.name}: {result.message}")
            except Exception as e:
                self.context.logger.warning(f"Error mounting {mount.name}: {e}")

    def signal(self, signum: int, _):
        # noinspection PyUnresolvedReferences
        # Signals is a generated enum
        self.context.logger.info("Caught signal {}".format(signal.Signals(signum).name))
        raise ServiceExit()

    @staticmethod
    def _parse_args(args):
        parser = argparse.ArgumentParser(description="Rapidcopy daemon")
        parser.add_argument("-c", "--config_dir", required=True, help="Path to config directory")
        parser.add_argument("--logdir", help="Directory for log files")
        parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logs")
        parser.add_argument("--exit", action="store_true", help="Exit on error")

        # Whether package is frozen
        is_frozen = getattr(sys, "frozen", False)

        # Html path is only required if not running a frozen package
        # For a frozen package, set default to root/html
        # noinspection PyUnresolvedReferences
        # noinspection PyProtectedMember
        default_html_path = os.path.join(sys._MEIPASS, "html") if is_frozen else None
        parser.add_argument(
            "--html",
            required=not is_frozen,
            default=default_html_path,
            help="Path to directory containing html resources",
        )

        # Scanfs path is only required if not running a frozen package
        # For a frozen package, set default to root/scanfs
        # noinspection PyUnresolvedReferences
        # noinspection PyProtectedMember
        default_scanfs_path = os.path.join(sys._MEIPASS, "scanfs") if is_frozen else None
        parser.add_argument(
            "--scanfs", required=not is_frozen, default=default_scanfs_path, help="Path to scanfs executable"
        )

        return parser.parse_args(args)

    @staticmethod
    def _create_default_config() -> Config:
        """
        Create a config with default values
        :return:
        """
        config = Config()

        config.general.debug = False
        config.general.verbose = False
        config.general.log_level = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

        config.lftp.remote_address = Rapidcopy.__CONFIG_DUMMY_VALUE
        config.lftp.remote_username = Rapidcopy.__CONFIG_DUMMY_VALUE
        config.lftp.remote_password = Rapidcopy.__CONFIG_DUMMY_VALUE
        config.lftp.remote_port = 22
        config.lftp.remote_path = Rapidcopy.__CONFIG_DUMMY_VALUE
        config.lftp.local_path = Rapidcopy.__CONFIG_DUMMY_VALUE
        config.lftp.remote_path_to_scan_script = "/tmp"
        config.lftp.use_ssh_key = False
        config.lftp.num_max_parallel_downloads = 2
        config.lftp.num_max_parallel_files_per_download = 4
        config.lftp.num_max_connections_per_root_file = 4
        config.lftp.num_max_connections_per_dir_file = 4
        config.lftp.num_max_total_connections = 16
        config.lftp.use_temp_file = False
        config.lftp.rate_limit = "0"  # No limit by default

        config.controller.interval_ms_remote_scan = 30000
        config.controller.interval_ms_local_scan = 10000
        config.controller.interval_ms_downloading_scan = 1000
        config.controller.extract_path = "/tmp"
        config.controller.use_local_path_as_extract_path = True

        config.web.port = 8800
        config.web.api_key = ""  # empty = auth disabled

        config.autoqueue.enabled = True
        config.autoqueue.patterns_only = False
        config.autoqueue.auto_extract = True

        config.validation.enabled = True
        config.validation.algorithm = "xxh128"
        config.validation.default_chunk_size = 52428800
        config.validation.min_chunk_size = 1048576
        config.validation.max_chunk_size = 104857600
        config.validation.validate_after_chunk = True
        config.validation.max_retries = 3
        config.validation.retry_delay_ms = 1000
        config.validation.enable_adaptive_sizing = True
        config.validation.settle_delay_secs = 5.0

        return config

    # Human-readable names for config fields
    __FIELD_DISPLAY_NAMES: Dict[str, str] = {
        "remote_address": "Server Address",
        "remote_username": "Server Username",
        "remote_password": "Server Password",
        "remote_path": "Server Directory",
        "local_path": "Local Directory",
        "remote_path_to_scan_script": "Remote Scan Script Path",
    }

    # Legacy path fields that can be skipped if path pairs are configured
    __LEGACY_PATH_FIELDS = {"remote_path", "local_path"}

    @staticmethod
    def _detect_incomplete_config(config: Config, path_pair_manager: Optional[PathPairManager] = None) -> List[str]:
        """
        Detects which config fields are incomplete (still have dummy values).
        Returns a list of human-readable field names that need to be configured.
        Returns an empty list if all fields are properly configured.

        Args:
            config: The configuration to validate
            path_pair_manager: If provided and has path pairs, legacy path fields
                              (remote_path, local_path) are not required

        Returns:
            List of human-readable field names that need to be configured
        """
        # Check if path pairs are configured (legacy fields not required)
        has_path_pairs = (
            path_pair_manager is not None
            and path_pair_manager.collection
            and len(path_pair_manager.collection.path_pairs) > 0
        )

        incomplete_fields: List[str] = []
        config_dict = config.as_dict()
        for sec_name in config_dict:
            for key in config_dict[sec_name]:
                if config_dict[sec_name][key] == Rapidcopy.__CONFIG_DUMMY_VALUE:
                    # Skip legacy path fields if path pairs are configured
                    if has_path_pairs and key in Rapidcopy.__LEGACY_PATH_FIELDS:
                        continue
                    # Use human-readable name if available, otherwise use the key
                    display_name = Rapidcopy.__FIELD_DISPLAY_NAMES.get(key, key)
                    incomplete_fields.append(display_name)
        return incomplete_fields

    @staticmethod
    def _load_persist(cls: Type[T_Persist], file_path: str) -> T_Persist:
        """
        Loads a persist from file.
        Backs up existing persist if it's corrupted. Returns a new blank
        persist in its place.
        :param cls:
        :param file_path:
        :return:
        """
        if os.path.isfile(file_path):
            try:
                return cls.from_file(file_path)
            except PersistError:
                if Rapidcopy.logger:
                    Rapidcopy.logger.exception("Caught exception")

                # backup file
                Rapidcopy.__backup_file(file_path)

                # noinspection PyCallingNonCallable
                return cls()
        else:
            # noinspection PyCallingNonCallable
            return cls()

    @staticmethod
    def __backup_file(file_path: str):
        """Back up file to a backups/ subdirectory with timestamp, keeping last 10."""
        if not os.path.isfile(file_path):
            return
        file_name = os.path.basename(file_path)
        file_dir = os.path.dirname(file_path)
        backup_dir = os.path.join(file_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, "{}.{}.bak".format(file_name, timestamp))
        if Rapidcopy.logger:
            Rapidcopy.logger.info("Backing up {} to {}".format(file_path, backup_path))
        shutil.copy(file_path, backup_path)
        # Rotate: keep only the 10 most recent backups for this file
        prefix = file_name + "."
        existing = sorted(
            [f for f in os.listdir(backup_dir) if f.startswith(prefix) and f.endswith(".bak")]
        )
        for old in existing[:-10]:
            os.remove(os.path.join(backup_dir, old))


if __name__ == "__main__":
    if sys.hexversion < 0x030B0000:
        sys.exit("Python 3.11 or newer is required to run this program.")

    while True:
        try:
            rapidcopy = Rapidcopy()
            rapidcopy.run()
        except ServiceExit:
            break
        except ServiceRestart:
            if Rapidcopy.logger:
                Rapidcopy.logger.info("Restarting...")
            continue
        except Exception:
            if Rapidcopy.logger:
                Rapidcopy.logger.exception("Caught exception")
            raise

        if Rapidcopy.logger:
            Rapidcopy.logger.info("Exited successfully")
