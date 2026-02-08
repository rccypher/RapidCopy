import hashlib
import os
from enum import Enum
from typing import Optional
from multiprocessing import Queue
import queue

from common import AppOneShotProcess
from ssh import Sshcp, SshcpError


class ValidationResult:
    """
    Result of a validation check for a single file
    """
    class Status(Enum):
        PASSED = 0
        FAILED = 1
        ERROR = 2

    def __init__(self, file_name: str, is_dir: bool, status: "ValidationResult.Status",
                 error_message: Optional[str] = None):
        self.file_name = file_name
        self.is_dir = is_dir
        self.status = status
        self.error_message = error_message


class ValidationStatus:
    """
    Status of a currently-running validation
    """
    class State(Enum):
        VALIDATING = 0

    def __init__(self, name: str, is_dir: bool):
        self.name = name
        self.is_dir = is_dir
        self.state = ValidationStatus.State.VALIDATING


class ValidateProcess(AppOneShotProcess):
    """
    Process that validates a downloaded file by comparing checksums
    between the local and remote copies.

    For single files: computes MD5 hash locally and remotely, compares them.
    For directories: computes MD5 hash for each file in the directory tree,
                     compares each pair.
    """
    def __init__(self,
                 local_path: str,
                 remote_path: str,
                 file_name: str,
                 is_dir: bool,
                 remote_address: str,
                 remote_username: str,
                 remote_password: Optional[str],
                 remote_port: int):
        super().__init__(name=self.__class__.__name__)
        self.__local_path = local_path
        self.__remote_path = remote_path
        self.__file_name = file_name
        self.__is_dir = is_dir
        self.__remote_address = remote_address
        self.__remote_username = remote_username
        self.__remote_password = remote_password
        self.__remote_port = remote_port
        self.__result_queue = Queue()

    @property
    def file_name(self) -> str:
        return self.__file_name

    @property
    def is_dir(self) -> bool:
        return self.__is_dir

    def pop_result(self) -> Optional[ValidationResult]:
        """
        Pop the validation result if available
        :return: ValidationResult or None
        """
        try:
            return self.__result_queue.get(block=False)
        except queue.Empty:
            return None

    def run_once(self):
        self.logger.info("Starting validation for: {}".format(self.__file_name))

        ssh = Sshcp(host=self.__remote_address,
                     port=self.__remote_port,
                     user=self.__remote_username,
                     password=self.__remote_password)
        ssh.set_base_logger(self.logger)

        try:
            if self.__is_dir:
                result = self._validate_directory(ssh)
            else:
                result = self._validate_file(ssh)
        except Exception as e:
            self.logger.error("Validation error for {}: {}".format(self.__file_name, str(e)))
            result = ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.ERROR,
                error_message=str(e)
            )

        self.__result_queue.put(result)

    def _validate_file(self, ssh: Sshcp) -> ValidationResult:
        """Validate a single file by comparing MD5 checksums"""
        local_file_path = os.path.join(self.__local_path, self.__file_name)
        remote_file_path = os.path.join(self.__remote_path, self.__file_name)

        # Compute local MD5
        self.logger.debug("Computing local MD5 for: {}".format(local_file_path))
        local_md5 = self._compute_local_md5(local_file_path)
        if local_md5 is None:
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.ERROR,
                error_message="Local file not found: {}".format(local_file_path)
            )

        # Compute remote MD5
        self.logger.debug("Computing remote MD5 for: {}".format(remote_file_path))
        try:
            remote_md5 = self._compute_remote_md5(ssh, remote_file_path)
        except SshcpError as e:
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.ERROR,
                error_message="Failed to compute remote MD5: {}".format(str(e))
            )

        # Compare
        if local_md5 == remote_md5:
            self.logger.info("Validation PASSED for {}: {} == {}".format(
                self.__file_name, local_md5, remote_md5))
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.PASSED
            )
        else:
            self.logger.warning("Validation FAILED for {}: local={} remote={}".format(
                self.__file_name, local_md5, remote_md5))
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.FAILED,
                error_message="Checksum mismatch: local={} remote={}".format(local_md5, remote_md5)
            )

    def _validate_directory(self, ssh: Sshcp) -> ValidationResult:
        """Validate a directory by comparing MD5 checksums of all files within it"""
        local_dir_path = os.path.join(self.__local_path, self.__file_name)
        remote_dir_path = os.path.join(self.__remote_path, self.__file_name)

        if not os.path.isdir(local_dir_path):
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.ERROR,
                error_message="Local directory not found: {}".format(local_dir_path)
            )

        # Walk local directory and collect all file paths (relative to the dir)
        local_files = []
        for root, dirs, files in os.walk(local_dir_path):
            for f in files:
                # Skip lftp temp files
                if f.endswith(".lftp") or f.endswith(".lftp-pget-status"):
                    continue
                abs_path = os.path.join(root, f)
                rel_path = os.path.relpath(abs_path, local_dir_path)
                local_files.append(rel_path)

        if not local_files:
            self.logger.warning("No files found in directory: {}".format(local_dir_path))
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.PASSED
            )

        # Validate each file
        for rel_path in local_files:
            local_file_path = os.path.join(local_dir_path, rel_path)
            remote_file_path = os.path.join(remote_dir_path, rel_path)

            self.logger.debug("Validating file in directory: {}".format(rel_path))

            local_md5 = self._compute_local_md5(local_file_path)
            if local_md5 is None:
                return ValidationResult(
                    file_name=self.__file_name,
                    is_dir=self.__is_dir,
                    status=ValidationResult.Status.ERROR,
                    error_message="Local file not found: {}".format(local_file_path)
                )

            try:
                remote_md5 = self._compute_remote_md5(ssh, remote_file_path)
            except SshcpError as e:
                return ValidationResult(
                    file_name=self.__file_name,
                    is_dir=self.__is_dir,
                    status=ValidationResult.Status.ERROR,
                    error_message="Failed to compute remote MD5 for {}: {}".format(rel_path, str(e))
                )

            if local_md5 != remote_md5:
                self.logger.warning("Validation FAILED for {}/{}: local={} remote={}".format(
                    self.__file_name, rel_path, local_md5, remote_md5))
                return ValidationResult(
                    file_name=self.__file_name,
                    is_dir=self.__is_dir,
                    status=ValidationResult.Status.FAILED,
                    error_message="Checksum mismatch in {}: local={} remote={}".format(
                        rel_path, local_md5, remote_md5)
                )

        self.logger.info("Validation PASSED for directory: {} ({} files checked)".format(
            self.__file_name, len(local_files)))
        return ValidationResult(
            file_name=self.__file_name,
            is_dir=self.__is_dir,
            status=ValidationResult.Status.PASSED
        )

    @staticmethod
    def _compute_local_md5(file_path: str) -> Optional[str]:
        """Compute MD5 hash of a local file"""
        if not os.path.isfile(file_path):
            return None
        md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
        return md5.hexdigest()

    @staticmethod
    def _compute_remote_md5(ssh: Sshcp, remote_file_path: str) -> str:
        """Compute MD5 hash of a remote file via SSH"""
        out = ssh.shell("md5sum '{}' | awk '{{print $1}}'".format(remote_file_path))
        md5_hash = out.decode().strip()
        if not md5_hash or len(md5_hash) != 32:
            raise SshcpError("Invalid MD5 output for {}: {}".format(remote_file_path, md5_hash))
        return md5_hash
