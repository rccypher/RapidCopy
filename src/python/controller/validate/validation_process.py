# Copyright 2024, RapidCopy Contributors, All rights reserved.

"""
Validation process for async file validation.

This module provides an async validation worker that runs in a separate
process to avoid blocking the main controller thread.
"""

import multiprocessing
import os
import queue
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from common import (
    AppProcess,
    overrides,
    ValidationConfig,
    FileValidationInfo,
    ChunkStatus,
)
from model import ModelFile
from ssh import Sshcp

from .checksum import LocalChecksumGenerator, RemoteChecksumGenerator, ChecksumError
from .chunk_manager import ChunkManager
from .adaptive_sizing import AdaptiveChunkSizer


@dataclass
class ValidationStatusResult:
    """Result containing current validation status."""

    timestamp: datetime
    file_statuses: dict[str, FileValidationInfo]


@dataclass
class ValidationCompletedResult:
    """Result when a file validation completes."""

    timestamp: datetime
    name: str
    file_path: str
    is_valid: bool
    corrupt_chunks: list[int]


@dataclass
class ValidationCommand:
    """Command to validate a file."""

    file: ModelFile
    local_path: str
    remote_path: str
    file_size: int
    inline: bool = False  # True = start validating chunks while file is still downloading


@dataclass
class LocalSizeUpdate:
    """Update the known local size for an inline-validated file."""

    local_path: str  # Relative path (same as ValidationCommand.local_path)
    local_size: int  # Current bytes on disk


@dataclass
class RetryCommand:
    """Command to retry validation for a file."""

    file_path: str


@dataclass
class CorruptChunkRedownload:
    """
    Emitted by the validation process when a chunk is corrupt and needs re-downloading.

    The controller should issue a partial pget for this byte range, then call
    resume_chunk() once the bytes are confirmed on disk.
    """

    local_path: str  # Absolute path of the local file
    remote_path: str  # Absolute path of the remote file
    chunk_index: int
    offset: int
    size: int  # Number of bytes to re-download

    @property
    def end_offset(self) -> int:
        return self.offset + self.size


@dataclass
class ResumeChunkCommand:
    """
    Command sent by the controller to resume validation of a chunk after re-download.
    """

    local_path: str  # Relative path (same as ValidationCommand.local_path)
    chunk_index: int


class ValidationDispatch:
    """
    Handles the actual validation logic.

    This class is created inside the process and manages:
    - Checksum generation (local and remote)
    - Chunk management
    - Validation coordination
    """

    def __init__(self, config: ValidationConfig, sshcp: Sshcp, local_base_path: str, remote_base_path: str):
        self.config = config
        self._local_base_path = local_base_path
        self._remote_base_path = remote_base_path

        # Initialize components
        self._local_checksum = LocalChecksumGenerator(algorithm=config.algorithm)
        self._remote_checksum = RemoteChecksumGenerator(sshcp, algorithm=config.algorithm)
        self._chunk_manager = ChunkManager(config)
        self._adaptive_sizer = AdaptiveChunkSizer(config)

        # Track pending and active validations
        self._pending_files: list[ValidationCommand] = []
        self._active_file: str | None = None
        self._active_remote_path: str | None = None
        self._active_inline: bool = False  # Whether active file is being inline-validated
        self._inline_local_sizes: dict[str, int] = {}  # local_path -> current bytes on disk

        # Redownload requests emitted when a corrupt chunk needs a partial re-fetch
        self._pending_redownloads: list[CorruptChunkRedownload] = []

    def set_base_logger(self, base_logger):
        """Set the base logger for all components."""
        self._local_checksum.set_base_logger(base_logger)
        self._remote_checksum.set_base_logger(base_logger)
        self._chunk_manager.set_base_logger(base_logger)
        self._adaptive_sizer.set_base_logger(base_logger)

    def queue_validation(self, command: ValidationCommand):
        """Queue a file for validation."""
        if command.inline:
            # Seed initial local size (may be 0 at queue time; updated by update_local_size())
            local_path = os.path.join(self._local_base_path, command.local_path)
            self._inline_local_sizes[local_path] = 0
        self._pending_files.append(command)

    def update_local_size(self, local_path: str, local_size: int):
        """Update the known local bytes-on-disk for an inline-validated file."""
        abs_path = os.path.join(self._local_base_path, local_path)
        if abs_path in self._inline_local_sizes:
            self._inline_local_sizes[abs_path] = local_size

    def process_next(self) -> Optional[ValidationCompletedResult]:
        """
        Process the next validation step.

        Returns:
            ValidationCompletedResult if a file completed validation, None otherwise
        """
        # If no active file, start the next pending one
        if self._active_file is None and self._pending_files:
            command = self._pending_files.pop(0)
            return self._start_validation(command)

        # If we have an active file, continue processing it
        if self._active_file is not None:
            return self._continue_validation()

        return None

    def _start_validation(self, command: ValidationCommand) -> Optional[ValidationCompletedResult]:
        """Start validation for a new file."""
        local_path = os.path.join(self._local_base_path, command.local_path)
        remote_path = os.path.join(self._remote_base_path, command.remote_path)

        # Calculate chunk size using adaptive sizing
        chunk_size = self._adaptive_sizer.calculate_chunk_size(command.file_size)

        # Create chunk definitions
        self._chunk_manager.create_chunks(local_path, command.file_size, chunk_size)
        self._active_file = local_path
        self._active_remote_path = remote_path
        self._active_inline = command.inline

        # Get remote checksums first (batched for efficiency)
        validation_info = self._chunk_manager.get_validation_info(local_path)
        if validation_info:
            try:
                remote_checksums = self._remote_checksum.compute_chunk_checksums(remote_path, validation_info.chunks)
                for i, checksum in enumerate(remote_checksums):
                    self._chunk_manager.update_chunk_checksum(local_path, i, remote_checksum=checksum)
            except ChecksumError as e:
                # Remote checksum failed, fall back to full file validation
                try:
                    full_checksum = self._remote_checksum.compute_file_checksum(remote_path)
                    self._chunk_manager.set_full_file_checksums(local_path, remote_checksum=full_checksum)
                except ChecksumError:
                    # Complete failure, mark as invalid
                    self._chunk_manager.remove_file(local_path)
                    self._active_file = None
                    return ValidationCompletedResult(
                        timestamp=datetime.now(),
                        name=command.file.name,
                        file_path=local_path,
                        is_valid=False,
                        corrupt_chunks=[],
                    )

        return self._continue_validation()

    def _continue_validation(self) -> Optional[ValidationCompletedResult]:
        """Continue validation for the active file."""
        if self._active_file is None:
            return None

        local_path = self._active_file
        validation_info = self._chunk_manager.get_validation_info(local_path)

        if not validation_info:
            self._active_file = None
            return None

        # Check if we have full file checksums to validate
        if validation_info.full_file_checksum and not validation_info.local_full_checksum:
            try:
                local_checksum = self._local_checksum.compute_file_checksum(local_path)
                self._chunk_manager.set_full_file_checksums(local_path, local_checksum=local_checksum)
                is_valid = self._chunk_manager.validate_full_file(local_path)
                self._chunk_manager.remove_file(local_path)
                self._active_file = None

                return ValidationCompletedResult(
                    timestamp=datetime.now(),
                    name=os.path.basename(local_path),
                    file_path=local_path,
                    is_valid=is_valid or False,
                    corrupt_chunks=[],
                )
            except ChecksumError:
                self._chunk_manager.remove_file(local_path)
                self._active_file = None
                return ValidationCompletedResult(
                    timestamp=datetime.now(),
                    name=os.path.basename(local_path),
                    file_path=local_path,
                    is_valid=False,
                    corrupt_chunks=[],
                )

        # Process chunks
        pending_chunks = self._chunk_manager.get_pending_chunks(local_path)

        if self._active_inline and pending_chunks:
            # In inline mode, only validate chunks whose bytes are fully on disk.
            current_local_size = self._inline_local_sizes.get(local_path, 0)
            pending_chunks = [c for c in pending_chunks if c.end_offset <= current_local_size]

        if pending_chunks:
            # Validate next pending chunk
            chunk = pending_chunks[0]
            try:
                local_checksum = self._local_checksum.compute_chunk_checksum(local_path, chunk.offset, chunk.size)
                self._chunk_manager.update_chunk_checksum(local_path, chunk.index, local_checksum=local_checksum)
                self._chunk_manager.validate_chunk(local_path, chunk.index)

                # Update adaptive sizer with result
                chunk_info = validation_info.chunks[chunk.index]
                self._adaptive_sizer.update_network_stats(chunk_success=(chunk_info.status == ChunkStatus.VALID))
            except ChecksumError:
                # Mark chunk as corrupt if we can't read it
                validation_info.chunks[chunk.index].mark_corrupt()

            return None

        # No pending chunks available right now.
        # In inline mode, there may be chunks waiting for the download to catch up —
        # check if any non-terminal chunks still exist before declaring completion.
        if self._active_inline:
            all_pending = self._chunk_manager.get_pending_chunks(local_path)
            if all_pending:
                # Download hasn't reached these chunks yet; wait
                return None

        # All chunks processed, check results
        corrupt_chunks = self._chunk_manager.get_corrupt_chunks(local_path)

        if corrupt_chunks:
            # Check if we can retry
            retryable = [c for c in corrupt_chunks if self._chunk_manager.can_retry_chunk(local_path, c.index)]

            if not retryable:
                # No more retries, validation failed
                self._chunk_manager.mark_file_complete(local_path, False)
                self._chunk_manager.remove_file(local_path)
                self._active_file = None
                self._active_remote_path = None
                self._inline_local_sizes.pop(local_path, None)

                return ValidationCompletedResult(
                    timestamp=datetime.now(),
                    name=os.path.basename(local_path),
                    file_path=local_path,
                    is_valid=False,
                    corrupt_chunks=[c.index for c in corrupt_chunks],
                )

            # Mark retryable chunks as DOWNLOADING and queue redownload requests.
            # The controller will issue a partial pget for each byte range and call
            # resume_chunk() once the bytes land on disk.
            for chunk in retryable:
                self._chunk_manager.mark_chunk_downloading(local_path, chunk.index)
                if self._active_remote_path is not None:
                    self._pending_redownloads.append(
                        CorruptChunkRedownload(
                            local_path=local_path,
                            remote_path=self._active_remote_path,
                            chunk_index=chunk.index,
                            offset=chunk.offset,
                            size=chunk.size,
                        )
                    )
            return None

        # All chunks valid!
        self._chunk_manager.mark_file_complete(local_path, True)
        self._chunk_manager.remove_file(local_path)
        self._active_file = None
        self._active_remote_path = None
        self._inline_local_sizes.pop(local_path, None)

        return ValidationCompletedResult(
            timestamp=datetime.now(),
            name=os.path.basename(local_path),
            file_path=local_path,
            is_valid=True,
            corrupt_chunks=[],
        )

    def pop_redownloads(self) -> list[CorruptChunkRedownload]:
        """
        Return and clear any pending chunk redownload requests.

        Called by ValidationProcess.run_loop() each cycle to relay requests to the controller.
        """
        redownloads = self._pending_redownloads[:]
        self._pending_redownloads.clear()
        return redownloads

    def resume_chunk(self, local_path: str, chunk_index: int):
        """
        Called after a partial re-download completes; resets the chunk to PENDING for re-hashing.

        Args:
            local_path: Relative local path (same as ValidationCommand.local_path)
            chunk_index: Index of the chunk that was re-downloaded
        """
        abs_path = os.path.join(self._local_base_path, local_path)
        self._chunk_manager.reset_chunk(abs_path, chunk_index)

    def get_status(self) -> dict[str, FileValidationInfo]:
        """Get current validation status for in-progress files only."""
        result = {}
        for file_path in self._chunk_manager.get_all_files():
            info = self._chunk_manager.get_validation_info(file_path)
            if info and not info.is_complete:
                result[file_path] = info
        return result

    def get_stats(self) -> dict:
        """Get overall validation statistics."""
        return self._chunk_manager.get_overall_stats()


class ValidationProcess(AppProcess):
    """
    Process that handles file validation in the background.

    Similar to ExtractProcess, this runs validation in a separate process
    to avoid blocking the main controller thread.
    """

    __DEFAULT_SLEEP_INTERVAL_IN_SECS = 0.5

    def __init__(
        self,
        config: ValidationConfig,
        ssh_host: str,
        ssh_port: int,
        ssh_user: str,
        ssh_password: Optional[str],
        local_base_path: str,
        remote_base_path: str,
    ):
        super().__init__(name=self.__class__.__name__)

        # Store SSH config for creating connection in subprocess
        self._ssh_host = ssh_host
        self._ssh_port = ssh_port
        self._ssh_user = ssh_user
        self._ssh_password = ssh_password

        self._config = config
        self._local_base_path = local_base_path
        self._remote_base_path = remote_base_path

        # Inter-process communication queues
        self._command_queue: multiprocessing.Queue[ValidationCommand] = multiprocessing.Queue()
        self._local_size_queue: multiprocessing.Queue[LocalSizeUpdate] = multiprocessing.Queue()
        self._resume_chunk_queue: multiprocessing.Queue[ResumeChunkCommand] = multiprocessing.Queue()
        self._status_result_queue: multiprocessing.Queue[ValidationStatusResult] = multiprocessing.Queue()
        self._completed_result_queue: multiprocessing.Queue[ValidationCompletedResult] = multiprocessing.Queue()
        self._redownload_result_queue: multiprocessing.Queue[CorruptChunkRedownload] = multiprocessing.Queue()

        # Dispatch is created in the subprocess
        self._dispatch: ValidationDispatch | None = None

    @overrides(AppProcess)
    def run_init(self):
        """Initialize the validation dispatch in the subprocess."""
        # Create SSH connection in subprocess
        sshcp = Sshcp(host=self._ssh_host, port=self._ssh_port, user=self._ssh_user, password=self._ssh_password)
        sshcp.set_base_logger(self.logger)

        # Create dispatch
        self._dispatch = ValidationDispatch(
            config=self._config,
            sshcp=sshcp,
            local_base_path=self._local_base_path,
            remote_base_path=self._remote_base_path,
        )
        self._dispatch.set_base_logger(self.logger)

        self.logger.info("Validation process initialized")

    @overrides(AppProcess)
    def run_cleanup(self):
        """Cleanup when process exits."""
        self.logger.info("Validation process shutting down")

    @overrides(AppProcess)
    def run_loop(self):
        """Main processing loop."""
        # Process incoming commands
        try:
            while True:
                command = self._command_queue.get(block=False)
                self._dispatch.queue_validation(command)
                self.logger.debug(f"Queued {'inline ' if command.inline else ''}validation for {command.file.name}")
        except queue.Empty:
            pass

        # Process local-size updates (for inline validation)
        try:
            while True:
                update = self._local_size_queue.get(block=False)
                self._dispatch.update_local_size(update.local_path, update.local_size)
        except queue.Empty:
            pass

        # Process resume-chunk commands (chunk re-download completed, re-hash it)
        try:
            while True:
                cmd = self._resume_chunk_queue.get(block=False)
                self._dispatch.resume_chunk(cmd.local_path, cmd.chunk_index)
                self.logger.debug(f"Resuming chunk {cmd.chunk_index} of {cmd.local_path} after re-download")
        except queue.Empty:
            pass

        # Process validations
        result = self._dispatch.process_next()
        if result:
            self._completed_result_queue.put(result)
            self.logger.info(f"Validation completed for {result.name}: {'VALID' if result.is_valid else 'CORRUPT'}")

        # Relay any redownload requests emitted by the dispatch
        for redownload in self._dispatch.pop_redownloads():
            self._redownload_result_queue.put(redownload)
            self.logger.info(
                f"Chunk {redownload.chunk_index} of {os.path.basename(redownload.local_path)} "
                f"is corrupt — requesting re-download of bytes {redownload.offset}-{redownload.end_offset}"
            )

        # Queue status update
        status = ValidationStatusResult(timestamp=datetime.now(), file_statuses=self._dispatch.get_status())
        self._status_result_queue.put(status)

        time.sleep(self.__DEFAULT_SLEEP_INTERVAL_IN_SECS)

    def validate(self, file: ModelFile, local_path: str, remote_path: str, file_size: int, inline: bool = False):
        """
        Process-safe method to queue a file for validation.

        Args:
            file: ModelFile to validate
            local_path: Relative local path
            remote_path: Relative remote path
            file_size: Total size of the file in bytes
            inline: If True, start validating chunks as they arrive (file still downloading)
        """
        command = ValidationCommand(
            file=file, local_path=local_path, remote_path=remote_path, file_size=file_size, inline=inline
        )
        self._command_queue.put(command)

    def update_local_size(self, local_path: str, local_size: int):
        """
        Process-safe method to report current bytes-on-disk for an inline-validated file.

        Call this on each controller cycle while the file is still downloading so the
        validation process can advance to newly-available chunks.

        Args:
            local_path: Relative local path (same as passed to validate())
            local_size: Current number of bytes present on disk
        """
        self._local_size_queue.put(LocalSizeUpdate(local_path=local_path, local_size=local_size))

    def pop_latest_statuses(self) -> Optional[ValidationStatusResult]:
        """
        Process-safe method to retrieve latest validation status.

        Returns:
            Latest status or None if no new status available
        """
        latest_result = None
        try:
            while True:
                latest_result = self._status_result_queue.get(block=False)
        except queue.Empty:
            pass
        return latest_result

    def pop_completed(self) -> list[ValidationCompletedResult]:
        """
        Process-safe method to retrieve list of newly completed validations.

        Returns:
            List of completed validation results
        """
        completed = []
        try:
            while True:
                result = self._completed_result_queue.get(block=False)
                completed.append(result)
        except queue.Empty:
            pass
        return completed

    def pop_redownloads(self) -> list[CorruptChunkRedownload]:
        """
        Process-safe method to retrieve pending corrupt-chunk redownload requests.

        The controller should issue a partial pget for each returned request and then
        call resume_chunk() once the bytes are confirmed on disk.

        Returns:
            List of CorruptChunkRedownload requests (may be empty)
        """
        redownloads = []
        try:
            while True:
                redownload = self._redownload_result_queue.get(block=False)
                redownloads.append(redownload)
        except queue.Empty:
            pass
        return redownloads

    def resume_chunk(self, local_path: str, chunk_index: int):
        """
        Process-safe method to signal that a partial re-download has completed.

        Call this after the pget_range() download finishes so the validation process
        resets the chunk to PENDING and re-hashes it.

        Args:
            local_path: Relative local path (same as passed to validate())
            chunk_index: Index of the chunk that was re-downloaded
        """
        self._resume_chunk_queue.put(ResumeChunkCommand(local_path=local_path, chunk_index=chunk_index))
