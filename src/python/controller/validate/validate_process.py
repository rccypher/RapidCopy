import hashlib
import logging
import os
import tempfile
from enum import Enum
from typing import Optional, List, Dict, Tuple
from multiprocessing import Queue
import queue

from common import AppOneShotProcess
from ssh import Sshcp, SshcpError


class ChunkFailure:
    """
    Describes a single chunk that failed validation
    """
    def __init__(self, file_path: str, chunk_index: int, chunk_offset: int, chunk_size: int):
        self.file_path = file_path  # absolute local file path
        self.remote_file_path = None  # set by caller
        self.chunk_index = chunk_index
        self.chunk_offset = chunk_offset
        self.chunk_size = chunk_size


class ValidationResult:
    """
    Result of a validation check for a single file
    """
    class Status(Enum):
        PASSED = 0
        FAILED = 1
        ERROR = 2

    def __init__(self, file_name: str, is_dir: bool, status: "ValidationResult.Status",
                 error_message: Optional[str] = None,
                 failed_chunks: Optional[List[ChunkFailure]] = None,
                 chunks_repaired: int = 0):
        self.file_name = file_name
        self.is_dir = is_dir
        self.status = status
        self.error_message = error_message
        self.failed_chunks = failed_chunks or []
        self.chunks_repaired = chunks_repaired


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

    Supports two modes:
    - Whole-file: computes a single SHA256 per file
    - Chunked: splits files into fixed-size chunks, hashes each chunk,
               and selectively re-downloads only corrupted chunks
    """
    def __init__(self,
                 local_path: str,
                 remote_path: str,
                 file_name: str,
                 is_dir: bool,
                 remote_address: str,
                 remote_username: str,
                 remote_password: Optional[str],
                 remote_port: int,
                 use_chunked: bool = False,
                 chunk_size_bytes: int = 4 * 1024 * 1024):
        super().__init__(name=self.__class__.__name__)
        self.__local_path = local_path
        self.__remote_path = remote_path
        self.__file_name = file_name
        self.__is_dir = is_dir
        self.__remote_address = remote_address
        self.__remote_username = remote_username
        self.__remote_password = remote_password
        self.__remote_port = remote_port
        self.__use_chunked = use_chunked
        self.__chunk_size_bytes = chunk_size_bytes
        self.__result_queue = Queue()

    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild("ValidateProcess")

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
        self.logger.info("Starting {} validation for: {}".format(
            "chunked" if self.__use_chunked else "whole-file", self.__file_name))

        ssh = Sshcp(host=self.__remote_address,
                     port=self.__remote_port,
                     user=self.__remote_username,
                     password=self.__remote_password)
        ssh.set_base_logger(self.logger)

        try:
            if self.__use_chunked:
                if self.__is_dir:
                    result = self._validate_directory_chunked(ssh)
                else:
                    result = self._validate_file_chunked(ssh)
            else:
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

    # =========================================================================
    # Whole-file validation
    # =========================================================================

    def _validate_file(self, ssh: Sshcp) -> ValidationResult:
        """Validate a single file by comparing SHA256 checksums"""
        local_file_path = os.path.join(self.__local_path, self.__file_name)
        remote_file_path = os.path.join(self.__remote_path, self.__file_name)

        self.logger.debug("Computing local SHA256 for: {}".format(local_file_path))
        local_hash = self._compute_local_sha256(local_file_path)
        if local_hash is None:
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.ERROR,
                error_message="Local file not found: {}".format(local_file_path)
            )

        self.logger.debug("Computing remote SHA256 for: {}".format(remote_file_path))
        try:
            remote_hash = self._compute_remote_sha256(ssh, remote_file_path)
        except SshcpError as e:
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.ERROR,
                error_message="Failed to compute remote SHA256: {}".format(str(e))
            )

        if local_hash == remote_hash:
            self.logger.info("Validation PASSED for {}".format(self.__file_name))
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.PASSED
            )
        else:
            self.logger.warning("Validation FAILED for {}: local={} remote={}".format(
                self.__file_name, local_hash, remote_hash))
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.FAILED,
                error_message="Checksum mismatch: local={} remote={}".format(local_hash, remote_hash)
            )

    def _validate_directory(self, ssh: Sshcp) -> ValidationResult:
        """Validate a directory by comparing SHA256 checksums of all files within it"""
        local_dir_path = os.path.join(self.__local_path, self.__file_name)
        remote_dir_path = os.path.join(self.__remote_path, self.__file_name)

        if not os.path.isdir(local_dir_path):
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.ERROR,
                error_message="Local directory not found: {}".format(local_dir_path)
            )

        local_files = self._collect_local_files(local_dir_path)
        if not local_files:
            self.logger.warning("No files found in directory: {}".format(local_dir_path))
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.PASSED
            )

        for rel_path in local_files:
            local_file_path = os.path.join(local_dir_path, rel_path)
            remote_file_path = os.path.join(remote_dir_path, rel_path)

            self.logger.debug("Validating file in directory: {}".format(rel_path))

            local_hash = self._compute_local_sha256(local_file_path)
            if local_hash is None:
                return ValidationResult(
                    file_name=self.__file_name,
                    is_dir=self.__is_dir,
                    status=ValidationResult.Status.ERROR,
                    error_message="Local file not found: {}".format(local_file_path)
                )

            try:
                remote_hash = self._compute_remote_sha256(ssh, remote_file_path)
            except SshcpError as e:
                return ValidationResult(
                    file_name=self.__file_name,
                    is_dir=self.__is_dir,
                    status=ValidationResult.Status.ERROR,
                    error_message="Failed to compute remote SHA256 for {}: {}".format(rel_path, str(e))
                )

            if local_hash != remote_hash:
                self.logger.warning("Validation FAILED for {}/{}: local={} remote={}".format(
                    self.__file_name, rel_path, local_hash, remote_hash))
                return ValidationResult(
                    file_name=self.__file_name,
                    is_dir=self.__is_dir,
                    status=ValidationResult.Status.FAILED,
                    error_message="Checksum mismatch in {}: local={} remote={}".format(
                        rel_path, local_hash, remote_hash)
                )

        self.logger.info("Validation PASSED for directory: {} ({} files checked)".format(
            self.__file_name, len(local_files)))
        return ValidationResult(
            file_name=self.__file_name,
            is_dir=self.__is_dir,
            status=ValidationResult.Status.PASSED
        )

    # =========================================================================
    # Chunked validation with selective re-download
    # =========================================================================

    def _validate_file_chunked(self, ssh: Sshcp) -> ValidationResult:
        """Validate a single file using per-chunk SHA256 and repair bad chunks"""
        local_file_path = os.path.join(self.__local_path, self.__file_name)
        remote_file_path = os.path.join(self.__remote_path, self.__file_name)

        if not os.path.isfile(local_file_path):
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.ERROR,
                error_message="Local file not found: {}".format(local_file_path)
            )

        failed_chunks = self._find_failed_chunks(ssh, local_file_path, remote_file_path)
        if failed_chunks is None:
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.ERROR,
                error_message="Failed to compute chunk hashes"
            )

        if not failed_chunks:
            self.logger.info("Chunked validation PASSED for {}".format(self.__file_name))
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.PASSED
            )

        # Attempt repair
        self.logger.info("Found {} bad chunks in {}, attempting repair".format(
            len(failed_chunks), self.__file_name))
        repaired = self._repair_chunks(ssh, failed_chunks)

        if repaired < len(failed_chunks):
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.FAILED,
                error_message="Repaired {}/{} chunks, some repairs failed".format(
                    repaired, len(failed_chunks)),
                failed_chunks=failed_chunks,
                chunks_repaired=repaired
            )

        # Re-verify the repaired chunks
        re_failed = self._find_failed_chunks(ssh, local_file_path, remote_file_path)
        if re_failed is None:
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.ERROR,
                error_message="Failed to re-verify after repair"
            )

        if not re_failed:
            self.logger.info("Chunked validation PASSED for {} after repairing {} chunks".format(
                self.__file_name, repaired))
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.PASSED,
                chunks_repaired=repaired
            )
        else:
            self.logger.warning("Chunked validation FAILED for {} after repair: {} chunks still bad".format(
                self.__file_name, len(re_failed)))
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.FAILED,
                error_message="{} chunks still corrupted after repair".format(len(re_failed)),
                failed_chunks=re_failed,
                chunks_repaired=repaired
            )

    def _validate_directory_chunked(self, ssh: Sshcp) -> ValidationResult:
        """Validate a directory using per-chunk SHA256 and repair bad chunks"""
        local_dir_path = os.path.join(self.__local_path, self.__file_name)
        remote_dir_path = os.path.join(self.__remote_path, self.__file_name)

        if not os.path.isdir(local_dir_path):
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.ERROR,
                error_message="Local directory not found: {}".format(local_dir_path)
            )

        local_files = self._collect_local_files(local_dir_path)
        if not local_files:
            self.logger.warning("No files found in directory: {}".format(local_dir_path))
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.PASSED
            )

        # Collect all failed chunks across all files
        all_failed_chunks = []
        for rel_path in local_files:
            local_file_path = os.path.join(local_dir_path, rel_path)
            remote_file_path = os.path.join(remote_dir_path, rel_path)

            self.logger.debug("Chunked validation for: {}".format(rel_path))
            failed = self._find_failed_chunks(ssh, local_file_path, remote_file_path)
            if failed is None:
                return ValidationResult(
                    file_name=self.__file_name,
                    is_dir=self.__is_dir,
                    status=ValidationResult.Status.ERROR,
                    error_message="Failed to compute chunk hashes for {}".format(rel_path)
                )
            all_failed_chunks.extend(failed)

        if not all_failed_chunks:
            self.logger.info("Chunked validation PASSED for directory: {} ({} files checked)".format(
                self.__file_name, len(local_files)))
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.PASSED
            )

        # Attempt repair of all failed chunks
        self.logger.info("Found {} bad chunks across directory {}, attempting repair".format(
            len(all_failed_chunks), self.__file_name))
        repaired = self._repair_chunks(ssh, all_failed_chunks)

        if repaired < len(all_failed_chunks):
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.FAILED,
                error_message="Repaired {}/{} chunks in directory, some repairs failed".format(
                    repaired, len(all_failed_chunks)),
                failed_chunks=all_failed_chunks,
                chunks_repaired=repaired
            )

        # Re-verify all files
        re_all_failed = []
        for rel_path in local_files:
            local_file_path = os.path.join(local_dir_path, rel_path)
            remote_file_path = os.path.join(remote_dir_path, rel_path)
            re_failed = self._find_failed_chunks(ssh, local_file_path, remote_file_path)
            if re_failed is None:
                return ValidationResult(
                    file_name=self.__file_name,
                    is_dir=self.__is_dir,
                    status=ValidationResult.Status.ERROR,
                    error_message="Failed to re-verify {} after repair".format(rel_path)
                )
            re_all_failed.extend(re_failed)

        if not re_all_failed:
            self.logger.info("Chunked validation PASSED for directory {} after repairing {} chunks".format(
                self.__file_name, repaired))
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.PASSED,
                chunks_repaired=repaired
            )
        else:
            self.logger.warning("Chunked validation FAILED for directory {} after repair: "
                                "{} chunks still bad".format(self.__file_name, len(re_all_failed)))
            return ValidationResult(
                file_name=self.__file_name,
                is_dir=self.__is_dir,
                status=ValidationResult.Status.FAILED,
                error_message="{} chunks still corrupted after repair in directory".format(len(re_all_failed)),
                failed_chunks=re_all_failed,
                chunks_repaired=repaired
            )

    def _find_failed_chunks(self, ssh: Sshcp,
                            local_file_path: str,
                            remote_file_path: str) -> Optional[List[ChunkFailure]]:
        """
        Compare per-chunk hashes between local and remote file.
        Returns list of ChunkFailure for mismatched chunks, or None on error.
        """
        local_hashes = self._compute_local_chunk_hashes(local_file_path)
        if local_hashes is None:
            return None

        try:
            remote_hashes = self._compute_remote_chunk_hashes(ssh, remote_file_path)
        except SshcpError as e:
            self.logger.error("Failed to compute remote chunk hashes for {}: {}".format(
                remote_file_path, str(e)))
            return None

        failed = []
        # Check all chunks that exist on either side
        all_indices = set(local_hashes.keys()) | set(remote_hashes.keys())
        for idx in sorted(all_indices):
            local_h = local_hashes.get(idx)
            remote_h = remote_hashes.get(idx)
            if local_h != remote_h:
                chunk_offset = idx * self.__chunk_size_bytes
                # Determine actual chunk size (last chunk may be smaller)
                file_size = os.path.getsize(local_file_path)
                actual_size = min(self.__chunk_size_bytes, file_size - chunk_offset)
                if actual_size <= 0:
                    actual_size = self.__chunk_size_bytes
                failure = ChunkFailure(
                    file_path=local_file_path,
                    chunk_index=idx,
                    chunk_offset=chunk_offset,
                    chunk_size=actual_size
                )
                failure.remote_file_path = remote_file_path
                failed.append(failure)
                self.logger.debug("Chunk {} mismatch: local={} remote={}".format(idx, local_h, remote_h))

        return failed

    def _repair_chunks(self, ssh: Sshcp, failed_chunks: List[ChunkFailure]) -> int:
        """
        Repair failed chunks by fetching them from the remote server via SCP.
        For each failed chunk:
          1. Extract the chunk on remote to a temp file using dd
          2. SCP the temp file to local
          3. Write the chunk data at the correct offset in the local file
          4. Clean up temp files
        Returns the number of successfully repaired chunks.
        """
        repaired = 0
        remote_tmp = "/tmp/.seedsync_chunk_repair"

        for chunk in failed_chunks:
            try:
                self.logger.info("Repairing chunk {} of {} (offset={}, size={})".format(
                    chunk.chunk_index, chunk.file_path, chunk.chunk_offset, chunk.chunk_size))

                # Extract chunk on remote to temp file
                dd_cmd = (
                    "dd if='{}' bs={} skip={} count=1 of='{}' 2>/dev/null"
                ).format(chunk.remote_file_path, self.__chunk_size_bytes,
                         chunk.chunk_index, remote_tmp)
                ssh.shell(dd_cmd)

                # SCP the chunk to a local temp file
                local_tmp_fd, local_tmp_path = tempfile.mkstemp(prefix="seedsync_chunk_")
                os.close(local_tmp_fd)
                try:
                    ssh.copy_from_remote(remote_tmp, local_tmp_path)

                    # Read the chunk data and patch the local file
                    with open(local_tmp_path, 'rb') as tmp_f:
                        chunk_data = tmp_f.read()

                    with open(chunk.file_path, 'r+b') as target_f:
                        target_f.seek(chunk.chunk_offset)
                        target_f.write(chunk_data)

                    repaired += 1
                    self.logger.debug("Successfully repaired chunk {}".format(chunk.chunk_index))
                finally:
                    # Clean up local temp
                    if os.path.exists(local_tmp_path):
                        os.remove(local_tmp_path)

                # Clean up remote temp
                try:
                    ssh.shell("rm -f '{}'".format(remote_tmp))
                except SshcpError:
                    pass  # best-effort cleanup

            except (SshcpError, OSError) as e:
                self.logger.error("Failed to repair chunk {} of {}: {}".format(
                    chunk.chunk_index, chunk.file_path, str(e)))

        self.logger.info("Repaired {}/{} chunks".format(repaired, len(failed_chunks)))
        return repaired

    # =========================================================================
    # Hash computation helpers
    # =========================================================================

    def _compute_local_chunk_hashes(self, file_path: str) -> Optional[Dict[int, str]]:
        """Compute SHA256 hash for each chunk of a local file. Returns {chunk_index: hash}."""
        if not os.path.isfile(file_path):
            return None
        hashes = {}
        with open(file_path, 'rb') as f:
            idx = 0
            while True:
                data = f.read(self.__chunk_size_bytes)
                if not data:
                    break
                hashes[idx] = hashlib.sha256(data).hexdigest()
                idx += 1
        return hashes

    def _compute_remote_chunk_hashes(self, ssh: Sshcp, remote_file_path: str) -> Dict[int, str]:
        """
        Compute SHA256 hash for each chunk of a remote file via a single SSH command.
        Returns {chunk_index: hash}.
        """
        # Single shell command that hashes all chunks and outputs "index hash" per line
        script = (
            "file='{file}'; cs={cs}; "
            "sz=$(stat -c%s \"$file\" 2>/dev/null || stat -f%z \"$file\" 2>/dev/null); "
            "n=$(( (sz + cs - 1) / cs )); "
            "i=0; while [ $i -lt $n ]; do "
            "h=$(dd if=\"$file\" bs=$cs skip=$i count=1 2>/dev/null | sha256sum | awk '{{print $1}}'); "
            "echo \"$i $h\"; "
            "i=$((i+1)); done"
        ).format(file=remote_file_path, cs=self.__chunk_size_bytes)

        out = ssh.shell(script)
        output = out.decode().strip()

        hashes = {}
        if not output:
            return hashes
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    idx = int(parts[0])
                    h = parts[1]
                    if len(h) == 64:
                        hashes[idx] = h
                except (ValueError, IndexError):
                    self.logger.warning("Skipping unparseable chunk hash line: {}".format(line))
        return hashes

    @staticmethod
    def _compute_local_sha256(file_path: str) -> Optional[str]:
        """Compute SHA256 hash of a local file"""
        if not os.path.isfile(file_path):
            return None
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def _compute_remote_sha256(ssh: Sshcp, remote_file_path: str) -> str:
        """Compute SHA256 hash of a remote file via SSH"""
        out = ssh.shell("sha256sum '{}' | awk '{{print $1}}'".format(remote_file_path))
        sha256_hash = out.decode().strip()
        if not sha256_hash or len(sha256_hash) != 64:
            raise SshcpError("Invalid SHA256 output for {}: {}".format(remote_file_path, sha256_hash))
        return sha256_hash

    # =========================================================================
    # Utility helpers
    # =========================================================================

    @staticmethod
    def _collect_local_files(dir_path: str) -> List[str]:
        """Walk a local directory and return relative paths of all non-temp files"""
        local_files = []
        for root, dirs, files in os.walk(dir_path):
            for f in files:
                if f.endswith(".lftp") or f.endswith(".lftp-pget-status"):
                    continue
                abs_path = os.path.join(root, f)
                rel_path = os.path.relpath(abs_path, dir_path)
                local_files.append(rel_path)
        return local_files
