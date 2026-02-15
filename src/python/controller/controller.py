# Copyright 2017, Inderpreet Singh, All rights reserved.

from abc import ABC, abstractmethod
from typing import List, Callable
from threading import Lock
from queue import Queue
from enum import Enum
import copy

# my libs
from .scan import (
    ScannerProcess,
    IScanner,
    ActiveScanner,
    LocalScanner,
    RemoteScanner,
    MultiPathLocalScanner,
    MultiPathRemoteScanner,
    MultiPathActiveScanner,
)
from .extract import ExtractProcess, ExtractStatus
from .validate import ValidationProcess
from .model_builder import ModelBuilder
from common import (
    Context,
    AppError,
    MultiprocessingLogger,
    AppOneShotProcess,
    Constants,
    ValidationConfig,
    ValidationAlgorithm,
)
from model import ModelError, ModelFile, Model, ModelDiff, ModelDiffUtil, IModelListener
from lftp import Lftp, LftpError, LftpJobStatus
from .controller_persist import ControllerPersist
from .delete import DeleteLocalProcess, DeleteRemoteProcess


class ControllerError(AppError):
    """
    Exception indicating a controller error
    """

    pass


class Controller:
    """
    Top-level class that controls the behaviour of the app
    """

    # Scanner instance variables with proper typing for multi-path support
    __active_scanner: IScanner
    __local_scanner: IScanner
    __remote_scanner: IScanner

    class Command:
        """
        Class by which clients of Controller can request Actions to be executed
        Supports callbacks by which clients can be notified of action success/failure
        Note: callbacks will be executed in Controller thread, so any heavy computation
              should be moved out of the callback
        """

        class Action(Enum):
            QUEUE = 0
            STOP = 1
            EXTRACT = 2
            DELETE_LOCAL = 3
            DELETE_REMOTE = 4
            VALIDATE = 5

        class ICallback(ABC):
            """Command callback interface"""

            @abstractmethod
            def on_success(self):
                """Called on successful completion of action"""
                pass

            @abstractmethod
            def on_failure(self, error: str):
                """Called on action failure"""
                pass

        def __init__(self, action: Action, filename: str):
            self.action = action
            self.filename = filename
            self.callbacks: list[Controller.Command.ICallback] = []

        def add_callback(self, callback: ICallback):
            self.callbacks.append(callback)

    class CommandProcessWrapper:
        """
        Wraps any one-shot command processes launched by the controller
        """

        def __init__(self, process: AppOneShotProcess, post_callback: Callable):
            self.process = process
            self.post_callback = post_callback

    def __init__(self, context: Context, persist: ControllerPersist):
        self.__context = context
        self.__persist = persist
        self.logger = context.logger.getChild("Controller")

        # Decide the password here
        self.__password = context.config.lftp.remote_password if not context.config.lftp.use_ssh_key else None

        # The command queue
        self.__command_queue: Queue[Controller.Command] = Queue()

        # The model
        self.__model = Model()
        self.__model.set_base_logger(self.logger)
        # Lock for the model
        # Note: While the scanners are in a separate process, the rest of the application
        #       is threaded in a single process. (The webserver is bottle+paste which is
        #       multi-threaded). Therefore it is safe to use a threading Lock for the model
        #       (the scanner processes never try to access the model)
        self.__model_lock = Lock()

        # Model builder
        self.__model_builder = ModelBuilder()
        self.__model_builder.set_base_logger(self.logger)
        self.__model_builder.set_downloaded_files(self.__persist.downloaded_file_names)
        self.__model_builder.set_extracted_files(self.__persist.extracted_file_names)

        # Lftp
        self.__lftp = Lftp(
            address=self.__context.config.lftp.remote_address,
            port=self.__context.config.lftp.remote_port,
            user=self.__context.config.lftp.remote_username,
            password=self.__password,
        )
        self.__lftp.set_base_logger(self.logger)
        self.__lftp.set_base_remote_dir_path(self.__context.config.lftp.remote_path)
        self.__lftp.set_base_local_dir_path(self.__context.config.lftp.local_path)
        # Configure Lftp
        self.__lftp.num_parallel_jobs = self.__context.config.lftp.num_max_parallel_downloads
        self.__lftp.num_parallel_files = self.__context.config.lftp.num_max_parallel_files_per_download
        self.__lftp.num_connections_per_root_file = self.__context.config.lftp.num_max_connections_per_root_file
        self.__lftp.num_connections_per_dir_file = self.__context.config.lftp.num_max_connections_per_dir_file
        self.__lftp.num_max_total_connections = self.__context.config.lftp.num_max_total_connections
        self.__lftp.use_temp_file = self.__context.config.lftp.use_temp_file
        # Set rate limit if configured (format: "0" for unlimited, "1M" for 1 MB/s, "500K" for 500 KB/s)
        if self.__context.config.lftp.rate_limit:
            self.__lftp.rate_limit = self.__context.config.lftp.rate_limit
        self.__lftp.temp_file_name = "*" + Constants.LFTP_TEMP_FILE_SUFFIX
        self.__lftp.set_verbose_logging(self.__context.config.general.verbose)

        # Setup the scanners and scanner processes
        # Check if path pairs are available for multi-path support
        path_pairs = []
        if self.__context.path_pair_manager:
            path_pairs = self.__context.path_pair_manager.get_enabled_pairs()

        if path_pairs:
            # Multi-path mode: create scanners for each path pair
            local_scanners = []
            remote_scanners = []
            path_pair_local_paths = {}  # Map path_pair_id -> local_path

            for pair in path_pairs:
                local_scanners.append(
                    LocalScanner(
                        local_path=pair.local_path,
                        use_temp_file=self.__context.config.lftp.use_temp_file,
                        path_pair_id=pair.id,
                        path_pair_name=pair.name,
                    )
                )
                remote_scanners.append(
                    RemoteScanner(
                        remote_address=self.__context.config.lftp.remote_address,
                        remote_username=self.__context.config.lftp.remote_username,
                        remote_password=self.__password,
                        remote_port=self.__context.config.lftp.remote_port,
                        remote_path_to_scan=pair.remote_path,
                        local_path_to_scan_script=self.__context.args.local_path_to_scanfs,
                        remote_path_to_scan_script=self.__context.config.lftp.remote_path_to_scan_script,
                        path_pair_id=pair.id,
                        path_pair_name=pair.name,
                    )
                )
                path_pair_local_paths[pair.id] = pair.local_path

            self.__local_scanner = MultiPathLocalScanner(local_scanners)
            self.__remote_scanner = MultiPathRemoteScanner(remote_scanners)
            # Multi-path active scanner: routes files to correct path pair
            self.__active_scanner = MultiPathActiveScanner(path_pair_local_paths)
            self.__is_multi_path_mode = True

            # Store path pairs for later use (e.g., queuing)
            self.__path_pairs = {pair.id: pair for pair in path_pairs}
        else:
            # Legacy single-path mode
            self.__active_scanner = ActiveScanner(self.__context.config.lftp.local_path)
            self.__local_scanner = LocalScanner(
                local_path=self.__context.config.lftp.local_path, use_temp_file=self.__context.config.lftp.use_temp_file
            )
            self.__remote_scanner = RemoteScanner(
                remote_address=self.__context.config.lftp.remote_address,
                remote_username=self.__context.config.lftp.remote_username,
                remote_password=self.__password,
                remote_port=self.__context.config.lftp.remote_port,
                remote_path_to_scan=self.__context.config.lftp.remote_path,
                local_path_to_scan_script=self.__context.args.local_path_to_scanfs,
                remote_path_to_scan_script=self.__context.config.lftp.remote_path_to_scan_script,
            )
            self.__is_multi_path_mode = False
            self.__path_pairs = {}

        self.__active_scan_process = ScannerProcess(
            scanner=self.__active_scanner,
            interval_in_ms=self.__context.config.controller.interval_ms_downloading_scan,
            verbose=False,
        )
        self.__local_scan_process = ScannerProcess(
            scanner=self.__local_scanner,
            interval_in_ms=self.__context.config.controller.interval_ms_local_scan,
        )
        self.__remote_scan_process = ScannerProcess(
            scanner=self.__remote_scanner,
            interval_in_ms=self.__context.config.controller.interval_ms_remote_scan,
        )

        # Setup extract process
        if self.__context.config.controller.use_local_path_as_extract_path:
            out_dir_path = self.__context.config.lftp.local_path
        else:
            out_dir_path = self.__context.config.controller.extract_path
        self.__extract_process = ExtractProcess(
            out_dir_path=out_dir_path, local_path=self.__context.config.lftp.local_path
        )

        # Setup validation process
        validation_cfg = self.__context.config.validation
        self.__validation_config = ValidationConfig(
            enabled=validation_cfg.enabled or False,
            algorithm=ValidationAlgorithm(validation_cfg.algorithm or "md5"),
            default_chunk_size=validation_cfg.default_chunk_size or 52428800,
            min_chunk_size=validation_cfg.min_chunk_size or 1048576,
            max_chunk_size=validation_cfg.max_chunk_size or 104857600,
            validate_after_chunk=validation_cfg.validate_after_chunk or False,
            validate_after_file=validation_cfg.validate_after_file
            if validation_cfg.validate_after_file is not None
            else True,
            max_retries=validation_cfg.max_retries or 3,
            retry_delay_ms=validation_cfg.retry_delay_ms or 1000,
            enable_adaptive_sizing=validation_cfg.enable_adaptive_sizing
            if validation_cfg.enable_adaptive_sizing is not None
            else True,
        )
        self.__validation_process = ValidationProcess(
            config=self.__validation_config,
            ssh_host=self.__context.config.lftp.remote_address,
            ssh_port=self.__context.config.lftp.remote_port,
            ssh_user=self.__context.config.lftp.remote_username,
            ssh_password=self.__password,
            local_base_path=self.__context.config.lftp.local_path,
            remote_base_path=self.__context.config.lftp.remote_path,
        )

        # Setup multiprocess logging
        self.__mp_logger = MultiprocessingLogger(self.logger)
        self.__active_scan_process.set_multiprocessing_logger(self.__mp_logger)
        self.__local_scan_process.set_multiprocessing_logger(self.__mp_logger)
        self.__remote_scan_process.set_multiprocessing_logger(self.__mp_logger)
        self.__extract_process.set_multiprocessing_logger(self.__mp_logger)
        self.__validation_process.set_multiprocessing_logger(self.__mp_logger)

        # Keep track of active files
        self.__active_downloading_file_names: list[str] = []
        self.__active_extracting_file_names: list[str] = []
        self.__active_validating_file_names: list[str] = []

        # Keep track of active command processes
        self.__active_command_processes: list[Controller.CommandProcessWrapper] = []

        self.__started = False

    def start(self):
        """
        Start the controller
        Must be called after ctor and before process()
        :return:
        """
        self.logger.debug("Starting controller")
        self.__active_scan_process.start()
        self.__local_scan_process.start()
        self.__remote_scan_process.start()
        self.__extract_process.start()
        if self.__validation_config.enabled:
            self.__validation_process.start()
        self.__mp_logger.start()
        self.__started = True

    def process(self):
        """
        Advance the controller state
        This method should return relatively quickly as the heavy lifting is done by concurrent tasks
        :return:
        """
        if not self.__started:
            raise ControllerError("Cannot process, controller is not started")
        self.__propagate_exceptions()
        self.__cleanup_commands()
        self.__process_commands()
        self.__update_model()

    def exit(self):
        self.logger.debug("Exiting controller")
        if self.__started:
            self.__lftp.exit()
            self.__active_scan_process.terminate()
            self.__local_scan_process.terminate()
            self.__remote_scan_process.terminate()
            self.__extract_process.terminate()
            if self.__validation_config.enabled:
                self.__validation_process.terminate()
            self.__active_scan_process.join()
            self.__local_scan_process.join()
            self.__remote_scan_process.join()
            self.__extract_process.join()
            if self.__validation_config.enabled:
                self.__validation_process.join()
            self.__mp_logger.stop()
            self.__started = False
            self.logger.info("Exited controller")

    def get_model_files(self) -> List[ModelFile]:
        """
        Returns a copy of all the model files
        :return:
        """
        with self.__model_lock:
            model_files = self.__get_model_files()
        return model_files

    def add_model_listener(self, listener: IModelListener):
        """
        Adds a listener to the controller's model
        :param listener:
        :return:
        """
        with self.__model_lock:
            self.__model.add_listener(listener)

    def remove_model_listener(self, listener: IModelListener):
        """
        Removes a listener from the controller's model
        :param listener:
        :return:
        """
        with self.__model_lock:
            self.__model.remove_listener(listener)

    def get_model_files_and_add_listener(self, listener: IModelListener):
        """
        Adds a listener and returns the current state of model files in one atomic operation
        This guarantees that model update events are not missed or duplicated for the clients
        Without an atomic operation, the following scenarios can happen:
            1. get_model() -> model updated -> add_listener()
               The model update never propagates to client
            2. add_listener() -> model updated -> get_model()
               The model update is duplicated on client side (once through listener, and once
               through the model).
        :param listener:
        :return:
        """
        with self.__model_lock:
            self.__model.add_listener(listener)
            model_files = self.__get_model_files()
        return model_files

    def queue_command(self, command: Command):
        self.__command_queue.put(command)

    def __get_model_files(self) -> List[ModelFile]:
        model_files = []
        for filename in self.__model.get_file_names():
            model_files.append(copy.deepcopy(self.__model.get_file(filename)))
        return model_files

    def __update_model(self):
        # Grab the latest scan results
        latest_remote_scan = self.__remote_scan_process.pop_latest_result()
        latest_local_scan = self.__local_scan_process.pop_latest_result()
        latest_active_scan = self.__active_scan_process.pop_latest_result()

        # Grab the Lftp status
        lftp_statuses = None
        try:
            lftp_statuses = self.__lftp.status()
        except LftpError as e:
            self.logger.warning("Caught lftp error: {}".format(str(e)))

        # Grab the latest extract results
        latest_extract_statuses = self.__extract_process.pop_latest_statuses()

        # Grab the latest extracted file names
        latest_extracted_results = self.__extract_process.pop_completed()

        # Update list of active file names
        if lftp_statuses is not None:
            self.__active_downloading_file_names = [
                s.name for s in lftp_statuses if s.state == LftpJobStatus.State.RUNNING
            ]
        if latest_extract_statuses is not None:
            self.__active_extracting_file_names = [
                s.name for s in latest_extract_statuses.statuses if s.state == ExtractStatus.State.EXTRACTING
            ]

        # Update the active scanner's state
        if self.__is_multi_path_mode:
            # Multi-path mode: pass (filename, path_pair_id) tuples
            active_files_with_pairs = []
            for name in self.__active_downloading_file_names + self.__active_extracting_file_names:
                path_pair_id = self.__get_path_pair_id_for_file(name)
                active_files_with_pairs.append((name, path_pair_id))
            self.__active_scanner.set_active_files(active_files_with_pairs)
        else:
            # Single-path mode: pass plain filenames
            self.__active_scanner.set_active_files(
                self.__active_downloading_file_names + self.__active_extracting_file_names
            )

        # Update model builder state
        if latest_remote_scan is not None:
            self.__model_builder.set_remote_files(latest_remote_scan.files)
        if latest_local_scan is not None:
            self.__model_builder.set_local_files(latest_local_scan.files)
        if latest_active_scan is not None:
            self.__model_builder.set_active_files(latest_active_scan.files)
        if lftp_statuses is not None:
            self.__model_builder.set_lftp_statuses(lftp_statuses)
        if latest_extract_statuses is not None:
            self.__model_builder.set_extract_statuses(latest_extract_statuses.statuses)
        if latest_extracted_results:
            for result in latest_extracted_results:
                self.__persist.extracted_file_names.add(result.name)
            self.__model_builder.set_extracted_files(self.__persist.extracted_file_names)

        # Build the new model, if needed
        if self.__model_builder.has_changes():
            new_model = self.__model_builder.build_model()

            with self.__model_lock:
                # Preserve validation states from the current model.
                # The model builder doesn't know about validation states (VALIDATING,
                # VALIDATED, CORRUPT) — those are applied by __process_validation_results.
                # Without this, every model rebuild would generate spurious UPDATED diffs
                # (e.g. VALIDATED→DOWNLOADED→VALIDATED) causing the UI to refresh all files.
                _VALIDATION_STATES = (
                    ModelFile.State.VALIDATING,
                    ModelFile.State.VALIDATED,
                    ModelFile.State.CORRUPT,
                )
                for file_name in new_model.get_file_names():
                    if file_name in self.__model.get_file_names():
                        old_file = self.__model.get_file(file_name)
                        if old_file.state in _VALIDATION_STATES:
                            new_file = new_model.get_file(file_name)
                            # Only carry over if the new model has it as DOWNLOADED
                            # (i.e. the model builder hasn't moved it to a different state)
                            if new_file.state == ModelFile.State.DOWNLOADED:
                                new_file.state = old_file.state
                                new_file.validation_progress = old_file.validation_progress
                                new_file.validation_error = old_file.validation_error
                                new_file.corrupt_chunks = old_file.corrupt_chunks

                # Diff the new model with old model
                model_diff = ModelDiffUtil.diff_models(self.__model, new_model)

                # Apply changes to the new model
                for diff in model_diff:
                    if diff.change == ModelDiff.Change.ADDED:
                        self.__model.add_file(diff.new_file)
                    elif diff.change == ModelDiff.Change.REMOVED:
                        self.__model.remove_file(diff.old_file.name)
                    elif diff.change == ModelDiff.Change.UPDATED:
                        self.__model.update_file(diff.new_file)

                    # Detect if a file was just Downloaded
                    #   an Added file in Downloaded state
                    #   an Updated file transitioning to Downloaded state
                    # If so, update the persist state
                    # Note: This step is done after the new model is build because
                    #       model_builder is the one that discovers when a file is Downloaded
                    downloaded = False
                    if (
                        diff.change == ModelDiff.Change.ADDED
                        and diff.new_file.state == ModelFile.State.DOWNLOADED
                        or diff.change == ModelDiff.Change.UPDATED
                        and diff.new_file.state == ModelFile.State.DOWNLOADED
                        and diff.old_file.state != ModelFile.State.DOWNLOADED
                    ):
                        downloaded = True
                    if downloaded:
                        self.__persist.downloaded_file_names.add(diff.new_file.name)
                        self.__model_builder.set_downloaded_files(self.__persist.downloaded_file_names)

                        # Auto-trigger validation if enabled
                        if (
                            self.__validation_config.enabled
                            and self.__validation_config.validate_after_file
                            and diff.new_file.local_size is not None
                            and diff.new_file.remote_size is not None
                        ):
                            self.__validation_process.validate(
                                file=diff.new_file,
                                local_path=diff.new_file.name,
                                remote_path=diff.new_file.name,
                                file_size=diff.new_file.local_size,
                            )
                            self.logger.info(
                                "Auto-queued '{}' for validation after download".format(diff.new_file.name)
                            )

                # Prune the extracted files list of any files that were deleted locally
                # This prevents these files from going to EXTRACTED state if they are re-downloaded
                remove_extracted_file_names = set()
                existing_file_names = self.__model.get_file_names()
                for extracted_file_name in self.__persist.extracted_file_names:
                    if extracted_file_name in existing_file_names:
                        file = self.__model.get_file(extracted_file_name)
                        if file.state == ModelFile.State.DELETED:
                            # Deleted locally, remove
                            remove_extracted_file_names.add(extracted_file_name)
                    else:
                        # Not in the model at all
                        # This could be because local and remote scans are not yet available
                        pass
                if remove_extracted_file_names:
                    self.logger.info("Removing from extracted list: {}".format(remove_extracted_file_names))
                    self.__persist.extracted_file_names.difference_update(remove_extracted_file_names)
                    self.__model_builder.set_extracted_files(self.__persist.extracted_file_names)

        # Update the controller status
        if latest_remote_scan is not None:
            self.__context.status.controller.latest_remote_scan_time = latest_remote_scan.timestamp
            self.__context.status.controller.latest_remote_scan_failed = latest_remote_scan.failed
            self.__context.status.controller.latest_remote_scan_error = latest_remote_scan.error_message
        if latest_local_scan is not None:
            self.__context.status.controller.latest_local_scan_time = latest_local_scan.timestamp

        # Process validation results (if validation is enabled)
        if self.__validation_config.enabled:
            self.__process_validation_results()

    def __process_commands(self):
        def _notify_failure(_command: Controller.Command, _msg: str):
            self.logger.warning("Command failed. {}".format(_msg))
            for _callback in _command.callbacks:
                _callback.on_failure(_msg)

        while not self.__command_queue.empty():
            command = self.__command_queue.get()
            self.logger.info("Received command {} for file {}".format(str(command.action), command.filename))
            try:
                file = self.__model.get_file(command.filename)
            except ModelError:
                _notify_failure(command, "File '{}' not found".format(command.filename))
                continue

            if command.action == Controller.Command.Action.QUEUE:
                if file.remote_size is None:
                    _notify_failure(command, "File '{}' does not exist remotely".format(command.filename))
                    continue
                try:
                    # Use path pair paths if available
                    remote_path = None
                    local_path = None
                    if file.path_pair_id and file.path_pair_id in self.__path_pairs:
                        pair = self.__path_pairs[file.path_pair_id]
                        remote_path = pair.remote_path
                        local_path = pair.local_path
                    self.__lftp.queue(file.name, file.is_dir, remote_path=remote_path, local_path=local_path)
                except LftpError as e:
                    _notify_failure(command, "Lftp error: {}".format(str(e)))
                    continue

            elif command.action == Controller.Command.Action.STOP:
                if file.state not in (ModelFile.State.DOWNLOADING, ModelFile.State.QUEUED):
                    _notify_failure(command, "File '{}' is not Queued or Downloading".format(command.filename))
                    continue
                try:
                    self.__lftp.kill(file.name)
                except LftpError as e:
                    _notify_failure(command, "Lftp error: {}".format(str(e)))
                    continue

            elif command.action == Controller.Command.Action.EXTRACT:
                # Note: We don't check the is_extractable flag because it's just a guess
                if file.state not in (ModelFile.State.DEFAULT, ModelFile.State.DOWNLOADED, ModelFile.State.EXTRACTED):
                    _notify_failure(
                        command, "File '{}' in state {} cannot be extracted".format(command.filename, str(file.state))
                    )
                    continue
                elif file.local_size is None:
                    _notify_failure(command, "File '{}' does not exist locally".format(command.filename))
                    continue
                else:
                    self.__extract_process.extract(file)

            elif command.action == Controller.Command.Action.DELETE_LOCAL:
                if file.state not in (ModelFile.State.DEFAULT, ModelFile.State.DOWNLOADED, ModelFile.State.EXTRACTED):
                    _notify_failure(
                        command,
                        "Local file '{}' cannot be deleted in state {}".format(command.filename, str(file.state)),
                    )
                    continue
                elif file.local_size is None:
                    _notify_failure(command, "File '{}' does not exist locally".format(command.filename))
                    continue
                else:
                    # Use path pair local_path if available
                    local_path = self.__context.config.lftp.local_path
                    if file.path_pair_id and file.path_pair_id in self.__path_pairs:
                        local_path = self.__path_pairs[file.path_pair_id].local_path
                    process = DeleteLocalProcess(local_path=local_path, file_name=file.name)
                    process.set_multiprocessing_logger(self.__mp_logger)
                    post_callback = self.__local_scan_process.force_scan
                    command_wrapper = Controller.CommandProcessWrapper(process=process, post_callback=post_callback)
                    self.__active_command_processes.append(command_wrapper)
                    command_wrapper.process.start()

            elif command.action == Controller.Command.Action.DELETE_REMOTE:
                if file.state not in (
                    ModelFile.State.DEFAULT,
                    ModelFile.State.DOWNLOADED,
                    ModelFile.State.EXTRACTED,
                    ModelFile.State.DELETED,
                ):
                    _notify_failure(
                        command,
                        "Remote file '{}' cannot be deleted in state {}".format(command.filename, str(file.state)),
                    )
                    continue
                elif file.remote_size is None:
                    _notify_failure(command, "File '{}' does not exist remotely".format(command.filename))
                    continue
                else:
                    # Use path pair remote_path if available
                    remote_path = self.__context.config.lftp.remote_path
                    if file.path_pair_id and file.path_pair_id in self.__path_pairs:
                        remote_path = self.__path_pairs[file.path_pair_id].remote_path
                    process = DeleteRemoteProcess(
                        remote_address=self.__context.config.lftp.remote_address,
                        remote_username=self.__context.config.lftp.remote_username,
                        remote_password=self.__password,
                        remote_port=self.__context.config.lftp.remote_port,
                        remote_path=remote_path,
                        file_name=file.name,
                    )
                    process.set_multiprocessing_logger(self.__mp_logger)
                    post_callback = self.__remote_scan_process.force_scan
                    command_wrapper = Controller.CommandProcessWrapper(process=process, post_callback=post_callback)
                    self.__active_command_processes.append(command_wrapper)
                    command_wrapper.process.start()

            elif command.action == Controller.Command.Action.VALIDATE:
                if not self.__validation_config.enabled:
                    _notify_failure(command, "Validation is not enabled in configuration")
                    continue
                if file.state not in (
                    ModelFile.State.DEFAULT,
                    ModelFile.State.DOWNLOADED,
                    ModelFile.State.EXTRACTED,
                    ModelFile.State.VALIDATED,
                    ModelFile.State.CORRUPT,
                ):
                    _notify_failure(
                        command,
                        "File '{}' in state {} cannot be validated".format(command.filename, str(file.state)),
                    )
                    continue
                elif file.local_size is None:
                    _notify_failure(command, "File '{}' does not exist locally".format(command.filename))
                    continue
                elif file.remote_size is None:
                    _notify_failure(
                        command,
                        "File '{}' does not exist remotely (needed for checksum comparison)".format(command.filename),
                    )
                    continue
                else:
                    # Determine local and remote paths
                    local_path = file.name
                    remote_path = file.name
                    file_size = file.local_size

                    # Queue for validation
                    self.__validation_process.validate(
                        file=file,
                        local_path=local_path,
                        remote_path=remote_path,
                        file_size=file_size,
                    )
                    self.logger.info("Queued '{}' for validation".format(file.name))

            # If we get here, it was a success
            for callback in command.callbacks:
                callback.on_success()

    def __propagate_exceptions(self):
        """
        Propagate any exceptions from child processes/threads to this thread
        :return:
        """
        self.__lftp.raise_pending_error()
        self.__active_scan_process.propagate_exception()
        self.__local_scan_process.propagate_exception()
        self.__remote_scan_process.propagate_exception()
        self.__mp_logger.propagate_exception()
        self.__extract_process.propagate_exception()
        if self.__validation_config.enabled:
            self.__validation_process.propagate_exception()

    def __cleanup_commands(self):
        """
        Cleanup the list of active commands and do any callbacks
        :return:
        """
        still_active_processes = []
        for command_process in self.__active_command_processes:
            if command_process.process.is_alive():
                still_active_processes.append(command_process)
            else:
                # Do the post callback
                command_process.post_callback()
                # Propagate the exception
                command_process.process.propagate_exception()
        self.__active_command_processes = still_active_processes

    def __process_validation_results(self):
        """
        Process validation results from the validation process.
        Updates model file states based on validation outcomes.
        """
        # Get latest validation statuses for progress updates
        latest_validation_statuses = self.__validation_process.pop_latest_statuses()

        # Get completed validations
        completed_validations = self.__validation_process.pop_completed()

        # Update list of active validating file names from statuses
        if latest_validation_statuses is not None:
            self.__active_validating_file_names = list(latest_validation_statuses.file_statuses.keys())

            # Update validation progress on model files
            with self.__model_lock:
                for file_path, validation_info in latest_validation_statuses.file_statuses.items():
                    # Extract filename from full path
                    file_name = self.__extract_filename_from_path(file_path)
                    if file_name and file_name in self.__model.get_file_names():
                        file = self.__model.get_file(file_name)
                        # Calculate progress from chunks
                        if validation_info.chunks:
                            validated_chunks = sum(
                                1 for chunk in validation_info.chunks if chunk.status.name in ("VALID", "CORRUPT")
                            )
                            progress = validated_chunks / len(validation_info.chunks)
                            # Only transition DOWNLOADED -> VALIDATING for this specific file
                            # Guard: do not touch files in terminal states (VALIDATED, CORRUPT)
                            # or files that are being re-downloaded (QUEUED, DOWNLOADING)
                            if file.state == ModelFile.State.DOWNLOADED:
                                file.state = ModelFile.State.VALIDATING
                                file.validation_progress = progress
                                self.__model.update_file(file)
                            elif file.state == ModelFile.State.VALIDATING:
                                file.validation_progress = progress
                                self.__model.update_file(file)

        # Process completed validations
        if completed_validations:
            with self.__model_lock:
                for result in completed_validations:
                    file_name = result.name
                    self.logger.info(
                        "Validation completed for '{}': {}".format(file_name, "VALID" if result.is_valid else "CORRUPT")
                    )

                    if file_name in self.__model.get_file_names():
                        file = self.__model.get_file(file_name)

                        # Only apply validation results if the file is still in a
                        # validation-related state. If it was re-queued for download
                        # while validation was running, don't overwrite its state.
                        if file.state not in (
                            ModelFile.State.VALIDATING,
                            ModelFile.State.DOWNLOADED,
                            ModelFile.State.CORRUPT,
                        ):
                            self.logger.debug(
                                "Skipping validation result for '{}' - file state is {}".format(
                                    file_name, file.state
                                )
                            )
                            continue

                        if result.is_valid:
                            # File passed validation
                            file.state = ModelFile.State.VALIDATED
                            file.validation_progress = 1.0
                            file.validation_error = None
                            file.corrupt_chunks = None
                        else:
                            # File failed validation
                            file.state = ModelFile.State.CORRUPT
                            file.validation_progress = None
                            file.corrupt_chunks = result.corrupt_chunks if result.corrupt_chunks else None
                            if result.corrupt_chunks:
                                file.validation_error = "Corrupt chunks: {}".format(result.corrupt_chunks)
                            else:
                                file.validation_error = "Validation failed"

                        self.__model.update_file(file)

                        # Remove from active validating list
                        if file_name in self.__active_validating_file_names:
                            self.__active_validating_file_names.remove(file_name)

    def __extract_filename_from_path(self, file_path: str) -> str | None:
        """
        Extract the root filename from a full file path.
        Handles paths relative to local_base_path.
        """
        import os

        local_base = self.__context.config.lftp.local_path
        if file_path.startswith(local_base):
            rel_path = file_path[len(local_base) :].lstrip(os.sep)
            # Get the root component (first part of the relative path)
            parts = rel_path.split(os.sep)
            if parts:
                return parts[0]
        # Fallback: just use the basename
        return os.path.basename(file_path)

    def __get_path_pair_id_for_file(self, filename: str) -> str | None:
        """
        Look up the path_pair_id from the model for a given filename.

        Args:
            filename: The name of the file to look up

        Returns:
            The path_pair_id if found, or None if not found or error
        """
        try:
            file = self.__model.get_file(filename)
            return file.path_pair_id
        except ModelError:
            return None
