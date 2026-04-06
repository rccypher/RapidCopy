# Abstract base class for transfer backends (lftp, rclone, etc.)

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from .job_status import JobStatus


class TransferBackend(ABC):
    """
    Defines the contract for a file transfer backend.
    The controller interacts with this interface exclusively.
    """

    @abstractmethod
    def set_base_logger(self, base_logger: logging.Logger) -> None:
        ...

    @abstractmethod
    def set_base_remote_dir_path(self, base_remote_dir_path: str) -> None:
        ...

    @abstractmethod
    def set_base_local_dir_path(self, base_local_dir_path: str) -> None:
        ...

    @abstractmethod
    def set_verbose_logging(self, verbose: bool) -> None:
        ...

    @abstractmethod
    def queue(
        self,
        name: str,
        is_dir: bool,
        remote_path: Optional[str] = None,
        local_path: Optional[str] = None,
    ) -> None:
        """
        Queue a file or directory for download. Must be non-blocking.
        """
        ...

    @abstractmethod
    def status(self) -> List[JobStatus]:
        """
        Return a snapshot of all queued and running jobs.
        Must be non-blocking and thread-safe.
        """
        ...

    @abstractmethod
    def kill(self, name: str) -> bool:
        """
        Kill a queued or running job by name.
        Returns True if the job was found and killed.
        """
        ...

    @abstractmethod
    def kill_all(self) -> None:
        """Kill all queued and running jobs."""
        ...

    @abstractmethod
    def prioritize(self, name: str) -> bool:
        """
        Move a queued job to the front of the queue.
        Returns True if the job was found and moved.
        """
        ...

    @abstractmethod
    def pget_range(
        self,
        remote_path: str,
        local_path: str,
        offset: int,
        end_offset: int,
    ) -> None:
        """
        Download a byte range and overwrite that range in the local file.
        Must be non-blocking (start in background, return immediately).
        """
        ...

    @abstractmethod
    def exit(self) -> None:
        """Shut down the backend. Kill all jobs and release resources."""
        ...

    @abstractmethod
    def raise_pending_error(self) -> None:
        """
        Raise any errors from recently completed/failed jobs.
        Called by the controller on each process() cycle to surface errors.
        """
        ...

    # -- Properties that control transfer behavior --
    # Subclasses must implement these as @property with getter/setter.

    @property
    @abstractmethod
    def num_parallel_jobs(self) -> int:
        ...

    @num_parallel_jobs.setter
    @abstractmethod
    def num_parallel_jobs(self, value: int) -> None:
        ...

    @property
    @abstractmethod
    def num_parallel_files(self) -> int:
        ...

    @num_parallel_files.setter
    @abstractmethod
    def num_parallel_files(self, value: int) -> None:
        ...

    @property
    @abstractmethod
    def num_connections_per_root_file(self) -> int:
        ...

    @num_connections_per_root_file.setter
    @abstractmethod
    def num_connections_per_root_file(self, value: int) -> None:
        ...

    @property
    @abstractmethod
    def num_connections_per_dir_file(self) -> int:
        ...

    @num_connections_per_dir_file.setter
    @abstractmethod
    def num_connections_per_dir_file(self, value: int) -> None:
        ...

    @property
    @abstractmethod
    def num_max_total_connections(self) -> int:
        ...

    @num_max_total_connections.setter
    @abstractmethod
    def num_max_total_connections(self, value: int) -> None:
        ...

    @property
    @abstractmethod
    def rate_limit(self) -> str:
        ...

    @rate_limit.setter
    @abstractmethod
    def rate_limit(self, value: int | str) -> None:
        ...

    @property
    @abstractmethod
    def min_chunk_size(self) -> str:
        ...

    @min_chunk_size.setter
    @abstractmethod
    def min_chunk_size(self, value: int | str) -> None:
        ...

    @property
    @abstractmethod
    def use_temp_file(self) -> bool:
        ...

    @use_temp_file.setter
    @abstractmethod
    def use_temp_file(self, value: bool) -> None:
        ...

    @property
    @abstractmethod
    def temp_file_name(self) -> str:
        ...

    @temp_file_name.setter
    @abstractmethod
    def temp_file_name(self, value: str) -> None:
        ...
