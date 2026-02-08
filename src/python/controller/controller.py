# Copyright 2017, Inderpreet Singh, All rights reserved.

from abc import ABC, abstractmethod
from typing import List, Callable
from threading import Lock
from queue import Queue
from enum import Enum
import copy
import os
import shutil

# my libs
from .scan import ScannerProcess, ActiveScanner, LocalScanner, RemoteScanner
from .extract import ExtractProcess, ExtractStatus
from .model_builder import ModelBuilder
from common import Context, AppError, MultiprocessingLogger, AppOneShotProcess, Constants
from model import ModelError, ModelFile, Model, ModelDiff, ModelDiffUtil, IModelListener
from lftp import Lftp, LftpError, LftpJobStatus
from .controller_persist import ControllerPersist
from .delete import DeleteLocalProcess, DeleteRemoteProcess
from .validate import ValidateProcess, ValidationResult, ValidationStatus


class ControllerError(AppError):
    """
    Exception indicating a controller error
    """
    pass


class Controller:
    """
    Top-level class that controls the behaviour of the app
    """
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
            self.callbacks = []

        def add_callback(self, callback: ICallback):
            self.callbacks.append(callback)

    class CommandProcessWrapper:
        """
        Wraps any one-shot command processes launched by the controller
        """
        def __init__(self, process: AppOneShotProcess, post_callback: Callable):
            self.process = process
            self.post_callback = post_callback

    def __init__(self,
                 context: Context,
                 persist: ControllerPersist):
        self.__context = context
        self.__persist = persist
        self.logger = context.logger.getChild("Controller")

        # Decide the password here
        self.__password = context.config.lftp.remote_password if not context.config.lftp.use_ssh_key else None

        # The command queue
        self.__command_queue = Queue()

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
        self.__lftp = Lftp(address=self.__context.config.lftp.remote_address,
                           port=self.__context.config.lftp.remote_port,
                           user=self.__context.config.lftp.remote_username,
                           password=self.__password)
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
        self.__lftp.temp_file_name = "*" + Constants.LFTP_TEMP_FILE_SUFFIX
        self.__lftp.set_verbose_logging(self.__context.config.general.verbose)

        # Setup the scanners and scanner processes
        self.__active_scanner = ActiveScanner(self.__context.config.lftp.local_path)
        self.__local_scanner = LocalScanner(
            local_path=self.__context.config.lftp.local_path,
            use_temp_file=self.__context.config.lftp.use_temp_file
        )
        self.__remote_scanner = RemoteScanner(
            remote_address=self.__context.config.lftp.remote_address,
            remote_username=self.__context.config.lftp.remote_username,
            remote_password=self.__password,
            remote_port=self.__context.config.lftp.remote_port,
            remote_path_to_scan=self.__context.config.lftp.remote_path,
            local_path_to_scan_script=self.__context.args.local_path_to_scanfs,
            remote_path_to_scan_script=self.__context.config.lftp.remote_path_to_scan_script
        )

        self.__active_scan_process = ScannerProcess(
            scanner=self.__active_scanner,
            interval_in_ms=self.__context.config.controller.interval_ms_downloading_scan,
            verbose=False
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
            out_dir_path=out_dir_path,
            local_path=self.__context.config.lftp.local_path
        )

        # Setup multiprocess logging
        self.__mp_logger = MultiprocessingLogger(self.logger)
        self.__active_scan_process.set_multiprocessing_logger(self.__mp_logger)
        self.__local_scan_process.set_multiprocessing_logger(self.__mp_logger)
        self.__remote_scan_process.set_multiprocessing_logger(self.__mp_logger)
        self.__extract_process.set_multiprocessing_logger(self.__mp_logger)

        # Keep track of active files
        self.__active_downloading_file_names = []
        self.__active_extracting_file_names = []
        self.__active_validating_file_names = []

        # Keep track of active command processes
        self.__active_command_processes = []

        # Keep track of active validation processes
        # Maps file_name -> ValidateProcess
        self.__active_validation_processes = {}

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
        self.__check_validation_results()
        self.__update_model()

    def exit(self):
        self.logger.debug("Exiting controller")
        if self.__started:
            self.__lftp.exit()
            self.__active_scan_process.terminate()
            self.__local_scan_process.terminate()
            self.__remote_scan_process.terminate()
            self.__extract_process.terminate()
            # Terminate any active validation processes
            for process in self.__active_validation_processes.values():
                process.terminate()
            self.__active_scan_process.join()
            self.__local_scan_process.join()
            self.__remote_scan_process.join()
            self.__extract_process.join()
            for process in self.__active_validation_processes.values():
                process.join()
            self.__active_validation_processes.clear()
            self.__mp_logger.stop()
            self.__started = False
            self.logger.info("Exited controller")

    def get_model_files(self) -> List[ModelFile]:
        """
        Returns a copy of all the model files
        :return:
        """
        # Lock the model
        self.__model_lock.acquire()
        model_files = self.__get_model_files()
        # Release the model
        self.__model_lock.release()
        return model_files

    def add_model_listener(self, listener: IModelListener):
        """
        Adds a listener to the controller's model
        :param listener:
        :return:
        """
        # Lock the model
        self.__model_lock.acquire()
        self.__model.add_listener(listener)
        # Release the model
        self.__model_lock.release()

    def remove_model_listener(self, listener: IModelListener):
        """
        Removes a listener from the controller's model
        :param listener:
        :return:
        """
        # Lock the model
        self.__model_lock.acquire()
        self.__model.remove_listener(listener)
        # Release the model
        self.__model_lock.release()

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
        # Lock the model
        self.__model_lock.acquire()
        self.__model.add_listener(listener)
        model_files = self.__get_model_files()
        # Release the model
        self.__model_lock.release()
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
        self.__active_validating_file_names = list(self.__active_validation_processes.keys())

        # Update the active scanner's state
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

        # Update model builder with validation statuses
        validation_statuses = [
            ValidationStatus(name=name, is_dir=proc.is_dir)
            for name, proc in self.__active_validation_processes.items()
        ]
        self.__model_builder.set_validation_statuses(validation_statuses)

        # Build the new model, if needed
        if self.__model_builder.has_changes():
            new_model = self.__model_builder.build_model()

            # Lock the model
            self.__model_lock.acquire()

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
                if diff.change == ModelDiff.Change.ADDED and \
                        diff.new_file.state == ModelFile.State.DOWNLOADED:
                    downloaded = True
                elif diff.change == ModelDiff.Change.UPDATED and \
                        diff.new_file.state == ModelFile.State.DOWNLOADED and \
                        diff.old_file.state != ModelFile.State.DOWNLOADED:
                    downloaded = True
                if downloaded:
                    self.__persist.downloaded_file_names.add(diff.new_file.name)
                    self.__model_builder.set_downloaded_files(self.__persist.downloaded_file_names)

                    # Trigger validation if enabled and not already validating
                    if self.__context.config.controller.enable_download_validation and \
                            diff.new_file.name not in self.__active_validation_processes:
                        self.__start_validation(diff.new_file.name, diff.new_file.is_dir)

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

            # Release the model
            self.__model_lock.release()

        # Update the controller status
        if latest_remote_scan is not None:
            self.__context.status.controller.latest_remote_scan_time = latest_remote_scan.timestamp
            self.__context.status.controller.latest_remote_scan_failed = latest_remote_scan.failed
            self.__context.status.controller.latest_remote_scan_error = latest_remote_scan.error_message
        if latest_local_scan is not None:
            self.__context.status.controller.latest_local_scan_time = latest_local_scan.timestamp

    def __start_validation(self, file_name: str, is_dir: bool):
        """
        Start a validation process for the given file
        """
        self.logger.info("Starting download validation for: {}".format(file_name))
        process = ValidateProcess(
            local_path=self.__context.config.lftp.local_path,
            remote_path=self.__context.config.lftp.remote_path,
            file_name=file_name,
            is_dir=is_dir,
            remote_address=self.__context.config.lftp.remote_address,
            remote_username=self.__context.config.lftp.remote_username,
            remote_password=self.__password,
            remote_port=self.__context.config.lftp.remote_port,
            use_chunked=self.__context.config.controller.use_chunked_validation,
            chunk_size_bytes=self.__context.config.controller.validation_chunk_size_mb * 1024 * 1024
        )
        process.set_multiprocessing_logger(self.__mp_logger)
        self.__active_validation_processes[file_name] = process
        process.start()

    def __check_validation_results(self):
        """
        Check for completed validation processes and handle results
        """
        completed = []
        for file_name, process in self.__active_validation_processes.items():
            if not process.is_alive():
                result = process.pop_result()
                if result is not None:
                    completed.append((file_name, result))
                else:
                    # Process died without producing a result
                    self.logger.error("Validation process for {} died without result".format(file_name))
                    completed.append((file_name, ValidationResult(
                        file_name=file_name,
                        is_dir=False,
                        status=ValidationResult.Status.ERROR,
                        error_message="Validation process terminated unexpectedly"
                    )))
                # Propagate any exceptions
                process.propagate_exception()

        for file_name, result in completed:
            del self.__active_validation_processes[file_name]

            if result.status == ValidationResult.Status.PASSED:
                self.logger.info("Validation passed for: {}".format(file_name))
                # Clear retry count on success
                if file_name in self.__persist.validation_retry_counts:
                    del self.__persist.validation_retry_counts[file_name]

            elif result.status == ValidationResult.Status.FAILED:
                retry_count = self.__persist.validation_retry_counts.get(file_name, 0)
                max_retries = self.__context.config.controller.download_validation_max_retries

                if retry_count < max_retries:
                    self.__persist.validation_retry_counts[file_name] = retry_count + 1
                    self.logger.warning(
                        "Validation failed for {} (attempt {}/{}): {}. "
                        "Deleting local copy and re-queuing.".format(
                            file_name, retry_count + 1, max_retries, result.error_message
                        ))
                    # Remove from downloaded set so it can be re-downloaded
                    self.__persist.downloaded_file_names.discard(file_name)
                    self.__model_builder.set_downloaded_files(self.__persist.downloaded_file_names)
                    # Delete local file and re-queue
                    self.__delete_local_and_requeue(file_name, result.is_dir)
                else:
                    self.logger.error(
                        "Validation failed for {} after {} retries: {}. Giving up.".format(
                            file_name, max_retries, result.error_message
                        ))
                    # Clear retry count
                    del self.__persist.validation_retry_counts[file_name]

            elif result.status == ValidationResult.Status.ERROR:
                self.logger.error("Validation error for {}: {}".format(
                    file_name, result.error_message))
                # On error, don't retry - just log and move on

    def __delete_local_and_requeue(self, file_name: str, is_dir: bool):
        """
        Delete the local copy of a file and re-queue it for download
        """
        local_file_path = os.path.join(self.__context.config.lftp.local_path, file_name)
        self.logger.info("Deleting local file for re-download: {}".format(file_name))
        try:
            if os.path.isfile(local_file_path):
                os.remove(local_file_path)
            elif os.path.isdir(local_file_path):
                shutil.rmtree(local_file_path, ignore_errors=True)
        except OSError as e:
            self.logger.error("Failed to delete local file {}: {}".format(file_name, str(e)))
            return

        # Force a local scan to pick up the deletion
        self.__local_scan_process.force_scan()

        # Re-queue the file for download
        try:
            self.__lftp.queue(file_name, is_dir)
            self.logger.info("Re-queued {} for download after validation failure".format(file_name))
        except LftpError as e:
            self.logger.error("Failed to re-queue {}: {}".format(file_name, str(e)))

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
                    self.__lftp.queue(file.name, file.is_dir)
                except LftpError as e:
                    _notify_failure(command, "Lftp error: ".format(str(e)))
                    continue

            elif command.action == Controller.Command.Action.STOP:
                if file.state not in (ModelFile.State.DOWNLOADING, ModelFile.State.QUEUED):
                    _notify_failure(command, "File '{}' is not Queued or Downloading".format(command.filename))
                    continue
                try:
                    self.__lftp.kill(file.name)
                except LftpError as e:
                    _notify_failure(command, "Lftp error: ".format(str(e)))
                    continue

            elif command.action == Controller.Command.Action.EXTRACT:
                # Note: We don't check the is_extractable flag because it's just a guess
                if file.state not in (
                        ModelFile.State.DEFAULT,
                        ModelFile.State.DOWNLOADED,
                        ModelFile.State.EXTRACTED
                ):
                    _notify_failure(command, "File '{}' in state {} cannot be extracted".format(
                        command.filename, str(file.state)
                    ))
                    continue
                elif file.local_size is None:
                    _notify_failure(command, "File '{}' does not exist locally".format(command.filename))
                    continue
                else:
                    self.__extract_process.extract(file)

            elif command.action == Controller.Command.Action.DELETE_LOCAL:
                if file.state not in (
                    ModelFile.State.DEFAULT,
                    ModelFile.State.DOWNLOADED,
                    ModelFile.State.EXTRACTED
                ):
                    _notify_failure(command, "Local file '{}' cannot be deleted in state {}".format(
                        command.filename, str(file.state)
                    ))
                    continue
                elif file.local_size is None:
                    _notify_failure(command, "File '{}' does not exist locally".format(command.filename))
                    continue
                else:
                    process = DeleteLocalProcess(
                        local_path=self.__context.config.lftp.local_path,
                        file_name=file.name
                    )
                    process.set_multiprocessing_logger(self.__mp_logger)
                    post_callback = self.__local_scan_process.force_scan
                    command_wrapper = Controller.CommandProcessWrapper(
                        process=process,
                        post_callback=post_callback
                    )
                    self.__active_command_processes.append(command_wrapper)
                    command_wrapper.process.start()

            elif command.action == Controller.Command.Action.DELETE_REMOTE:
                if file.state not in (
                    ModelFile.State.DEFAULT,
                    ModelFile.State.DOWNLOADED,
                    ModelFile.State.EXTRACTED,
                    ModelFile.State.DELETED
                ):
                    _notify_failure(command, "Remote file '{}' cannot be deleted in state {}".format(
                        command.filename, str(file.state)
                    ))
                    continue
                elif file.remote_size is None:
                    _notify_failure(command, "File '{}' does not exist remotely".format(command.filename))
                    continue
                else:
                    process = DeleteRemoteProcess(
                        remote_address=self.__context.config.lftp.remote_address,
                        remote_username=self.__context.config.lftp.remote_username,
                        remote_password=self.__password,
                        remote_port=self.__context.config.lftp.remote_port,
                        remote_path=self.__context.config.lftp.remote_path,
                        file_name=file.name
                    )
                    process.set_multiprocessing_logger(self.__mp_logger)
                    post_callback = self.__remote_scan_process.force_scan
                    command_wrapper = Controller.CommandProcessWrapper(
                        process=process,
                        post_callback=post_callback
                    )
                    self.__active_command_processes.append(command_wrapper)
                    command_wrapper.process.start()

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
