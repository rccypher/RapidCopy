# Rclone transfer backend: replaces the lftp backend with rclone subprocess management.

import logging
import math
import os
import shlex
import shutil
import subprocess
import threading
from typing import List

from common import AppError
from common.job_status import JobStatus
from common.transfer_backend import TransferBackend

from .job_queue import JobQueue


class RcloneError(AppError):
    """Custom exception for rclone failures."""

    pass


class Rclone(TransferBackend):
    """
    Rclone-based file transfer backend.

    Replaces the Lftp class with rclone subprocess management.
    Each transfer is a separate rclone process managed by a JobQueue.
    """

    def __init__(self, address: str, port: int, user: str, password: str | None):
        # Validate rclone is installed
        if shutil.which("rclone") is None:
            raise RcloneError(
                "rclone binary not found in PATH. "
                "Install: https://rclone.org/install/ "
                "(macOS: brew install rclone, Docker: see Dockerfile)"
            )

        self.__address = address
        self.__port = port
        self.__user = user
        self.__password = password
        self.__base_remote_dir_path = ""
        self.__base_local_dir_path = ""
        self.logger = logging.getLogger("Rclone")
        self.__verbose = False

        # Transfer settings (with defaults matching lftp config defaults)
        self.__num_parallel_jobs = 2
        self.__num_parallel_files = 4
        # Single-stream downloads to prevent corruption from multi-thread reassembly.
        # Multi-thread-streams > 1 causes MD5 mismatches on SFTP transfers.
        self.__num_connections_per_root_file = 1
        self.__num_connections_per_dir_file = 1
        self.__num_max_total_connections = 16
        self.__rate_limit: str = "0"
        self.__min_chunk_size: str = "0"
        self.__use_temp_file = True  # Always use temp files to prevent page-cache corruption
        self.__temp_file_name = ""  # suffix pattern, e.g., "*.lftp"

        # Obscure password for rclone (if password auth is used)
        self.__obscured_password: str | None = None
        if self.__password:
            self.__obscured_password = self._obscure_password(self.__password)

        # Job queue
        self.__job_queue = JobQueue(max_parallel_jobs=self.__num_parallel_jobs)

        # Sshcp instance for pget_range (lazy-initialized)
        self.__sshcp = None
        self.__sshcp_lock = threading.Lock()

    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild("Rclone")
        self.__job_queue.set_base_logger(self.logger)

    def set_base_remote_dir_path(self, base_remote_dir_path: str):
        self.__base_remote_dir_path = base_remote_dir_path

    def set_base_local_dir_path(self, base_local_dir_path: str):
        self.__base_local_dir_path = base_local_dir_path

    def set_verbose_logging(self, verbose: bool):
        self.__verbose = verbose

    def raise_pending_error(self):
        error = self.__job_queue.pop_error()
        if error:
            raise RcloneError(error)

    # -- Properties --

    @property
    def num_parallel_jobs(self) -> int:
        return self.__num_parallel_jobs

    @num_parallel_jobs.setter
    def num_parallel_jobs(self, value: int):
        if value < 1:
            raise ValueError("Number of parallel jobs must be positive")
        self.__num_parallel_jobs = value
        self.__job_queue.set_max_parallel_jobs(value)

    @property
    def num_parallel_files(self) -> int:
        return self.__num_parallel_files

    @num_parallel_files.setter
    def num_parallel_files(self, value: int):
        if value < 1:
            raise ValueError("Number of parallel files must be positive")
        self.__num_parallel_files = value

    @property
    def num_connections_per_root_file(self) -> int:
        return self.__num_connections_per_root_file

    @num_connections_per_root_file.setter
    def num_connections_per_root_file(self, value: int):
        if value < 1:
            raise ValueError("Number of connections must be positive")
        self.__num_connections_per_root_file = value

    @property
    def num_connections_per_dir_file(self) -> int:
        return self.__num_connections_per_dir_file

    @num_connections_per_dir_file.setter
    def num_connections_per_dir_file(self, value: int):
        if value < 1:
            raise ValueError("Number of connections must be positive")
        self.__num_connections_per_dir_file = value

    @property
    def num_max_total_connections(self) -> int:
        return self.__num_max_total_connections

    @num_max_total_connections.setter
    def num_max_total_connections(self, value: int):
        if value < 0:
            raise ValueError("Number of connections must be zero or greater")
        self.__num_max_total_connections = value
        # Log warning if configured parallelism would exceed this limit
        estimated = self.__num_parallel_jobs * max(
            self.__num_connections_per_root_file,
            self.__num_connections_per_dir_file,
        )
        if value > 0 and estimated > value:
            self.logger.warning(
                "Estimated connections (%d) may exceed num_max_total_connections (%d). "
                "rclone cannot enforce a global connection limit. "
                "Consider reducing num_parallel_jobs or multi-thread-streams.",
                estimated,
                value,
            )

    @property
    def rate_limit(self) -> str:
        return self.__rate_limit

    @rate_limit.setter
    def rate_limit(self, value: int | str):
        self.__rate_limit = str(value)

    @property
    def min_chunk_size(self) -> str:
        return self.__min_chunk_size

    @min_chunk_size.setter
    def min_chunk_size(self, value: int | str):
        self.__min_chunk_size = str(value)

    @property
    def use_temp_file(self) -> bool:
        return self.__use_temp_file

    @use_temp_file.setter
    def use_temp_file(self, value: bool):
        self.__use_temp_file = value

    @property
    def temp_file_name(self) -> str:
        return self.__temp_file_name

    @temp_file_name.setter
    def temp_file_name(self, value: str):
        self.__temp_file_name = value

    # -- Core Operations --

    def queue(
        self,
        name: str,
        is_dir: bool,
        remote_path: str | None = None,
        local_path: str | None = None,
    ) -> None:
        remote_dir = remote_path if remote_path is not None else self.__base_remote_dir_path
        local_dir = local_path if local_path is not None else self.__base_local_dir_path

        command, env = self._build_command(name, is_dir, remote_dir, local_dir)

        if self.__verbose:
            self.logger.debug("Queueing rclone command: %s", " ".join(command))

        self.__job_queue.enqueue(name=name, is_dir=is_dir, command=command, env=env)

    def status(self) -> List[JobStatus]:
        return self.__job_queue.get_statuses()

    def kill(self, name: str) -> bool:
        return self.__job_queue.kill_job(name)

    def kill_all(self) -> None:
        self.__job_queue.kill_all()

    def prioritize(self, name: str) -> bool:
        return self.__job_queue.prioritize(name)

    def pget_range(
        self,
        remote_path: str,
        local_path: str,
        offset: int,
        end_offset: int,
    ) -> None:
        """
        Download a byte range of a remote file and overwrite that range in the local file.

        Uses SSH + dd to read the byte range from the remote server. This is run in a
        background thread to maintain the non-blocking contract (matching lftp's behavior
        where pget_range() sends a background command and returns immediately).
        """
        thread = threading.Thread(
            target=self._do_pget_range,
            args=(remote_path, local_path, offset, end_offset),
            daemon=True,
            name=f"pget-range-{os.path.basename(local_path)}",
        )
        thread.start()

    def exit(self) -> None:
        self.__job_queue.shutdown()

    # -- Private Methods --

    def _build_command(
        self, name: str, is_dir: bool, remote_dir: str, local_dir: str
    ) -> tuple[list[str], dict[str, str]]:
        """Build an rclone command and its environment variables."""
        # Build the SFTP remote spec (without password -- that goes in env)
        remote_spec = f":sftp,host={self.__address},port={self.__port},user={self.__user}:"

        if is_dir:
            # Directory: rclone copy remote/dir/ local/dir/
            remote_src = f"{remote_spec}{remote_dir}/{name}/"
            local_dst = f"{local_dir}/{name}/"
            cmd = ["rclone", "copy", remote_src, local_dst]
            cmd += ["--transfers", str(self.__num_parallel_files)]
            cmd += ["--multi-thread-streams", str(self.__num_connections_per_dir_file)]
        else:
            # Single file: rclone copyto remote/dir/file local/dir/file
            remote_src = f"{remote_spec}{remote_dir}/{name}"
            local_dst = f"{local_dir}/{name}"
            cmd = ["rclone", "copyto", remote_src, local_dst]
            cmd += ["--transfers", "1"]
            cmd += ["--multi-thread-streams", str(self.__num_connections_per_root_file)]

        # Always use partial-suffix for atomic rename on completion.
        # This prevents the page-cache false-positive corruption issue:
        # rclone writes to "file.lftp", then renames to "file" when done.
        # The rename guarantees the file is fully flushed to disk before
        # validation reads it.
        suffix = self._extract_suffix()
        if suffix:
            cmd += ["--partial-suffix", suffix]

        # Suppress rclone config file save errors (we use inline backend, no config needed)
        cmd += ["--config", "/dev/null"]

        # Progress reporting
        cmd += ["--use-json-log", "--stats", "1s", "-v"]

        # Rate limiting
        if self.__rate_limit and self.__rate_limit != "0":
            cmd += ["--bwlimit", self.__rate_limit]

        # Retry settings for resilience
        cmd += ["--retries", "3", "--low-level-retries", "10"]

        # Checksum verification (rclone will use remote md5sum/sha1sum if available)
        cmd += ["--checksum"]

        # SSH key auth
        if self.__password is None:
            cmd += ["--sftp-key-file", os.path.expanduser("~/.ssh/id_rsa")]

        # Environment: pass obscured password via env var (not command line)
        env = os.environ.copy()
        if self.__obscured_password:
            env["RCLONE_SFTP_PASS"] = self.__obscured_password

        return cmd, env

    def _extract_suffix(self) -> str:
        """Extract temp file suffix from pattern like '*.lftp' -> '.lftp'."""
        if self.__temp_file_name and "*" in self.__temp_file_name:
            return self.__temp_file_name.replace("*", "")
        return self.__temp_file_name

    def _do_pget_range(
        self, remote_path: str, local_path: str, offset: int, end_offset: int
    ):
        """
        Background thread: download byte range via SSH + dd, write to local file.
        """
        size = end_offset - offset
        block_size = 4096
        skip_blocks = offset // block_size
        # We may need to read a few extra bytes if offset isn't block-aligned
        offset_remainder = offset % block_size
        count_bytes = size + offset_remainder

        try:
            # Build SSH command to read byte range from remote
            dd_cmd = (
                f"dd if={shlex.quote(remote_path)} "
                f"bs={block_size} "
                f"skip={skip_blocks} "
                f"count={math.ceil(count_bytes / block_size)} "
                f"2>/dev/null"
            )

            # Use subprocess directly for SSH (supports both key and password auth)
            ssh_args = [
                "ssh",
                "-p", str(self.__port),
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "LogLevel=error",
            ]
            if self.__password is None:
                ssh_args += ["-o", "PasswordAuthentication=no"]

            ssh_args += [f"{self.__user}@{self.__address}", dd_cmd]

            self.logger.debug(
                "pget_range: fetching bytes %d-%d from %s", offset, end_offset, remote_path
            )

            if self.__password is not None:
                # Password auth: use Sshcp which handles pexpect interaction
                sshcp = self._get_sshcp()
                data = sshcp.shell(dd_cmd)
            else:
                # Key auth: use subprocess directly
                result = subprocess.run(
                    ssh_args, capture_output=True, timeout=300
                )
                if result.returncode != 0:
                    stderr = result.stderr.decode("utf-8", "replace").strip()
                    raise RcloneError(f"SSH dd failed: {stderr}")
                data = result.stdout

            # Trim to exact byte range (if offset wasn't block-aligned)
            if offset_remainder > 0:
                data = data[offset_remainder:]
            data = data[:size]

            if len(data) != size:
                self.logger.warning(
                    "pget_range: expected %d bytes, got %d for %s at offset %d",
                    size, len(data), remote_path, offset,
                )

            # Write to local file at the correct offset
            with open(local_path, "r+b") as f:
                f.seek(offset)
                f.write(data)

            self.logger.debug(
                "pget_range: wrote %d bytes to %s at offset %d", len(data), local_path, offset
            )

        except Exception as e:
            error_msg = f"pget_range failed for {remote_path} [{offset}-{end_offset}]: {e}"
            self.logger.error(error_msg)
            with self.__job_queue._lock:
                self.__job_queue._errors.append(error_msg)

    def _get_sshcp(self):
        """Lazy-initialize and return an Sshcp instance for pget_range."""
        with self.__sshcp_lock:
            if self.__sshcp is None:
                from ssh import Sshcp

                self.__sshcp = Sshcp(
                    host=self.__address,
                    port=self.__port,
                    user=self.__user,
                    password=self.__password,
                )
                self.__sshcp.set_base_logger(self.logger)
            return self.__sshcp

    @staticmethod
    def _obscure_password(password: str) -> str:
        """Use 'rclone obscure' to obscure a password for safe use in env vars."""
        try:
            result = subprocess.run(
                ["rclone", "obscure", password],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RcloneError(f"rclone obscure failed: {result.stderr.strip()}")
            return result.stdout.strip()
        except FileNotFoundError as e:
            raise RcloneError("rclone binary not found") from e
        except subprocess.TimeoutExpired as e:
            raise RcloneError("rclone obscure timed out") from e
