# Copyright 2024, RapidCopy Contributors, All rights reserved.

"""
Chunk manager for file validation.

This module provides functionality for:
- Splitting files into chunks
- Tracking chunk validation state
- Managing chunk re-downloads
"""

import logging
import os
from typing import Optional

from common import (
    ChunkInfo,
    ChunkStatus,
    FileValidationInfo,
    ValidationConfig,
    ValidationAlgorithm,
)


class ChunkManager:
    """
    Manages file chunking and validation state.

    This class is responsible for:
    - Splitting files into appropriately sized chunks
    - Tracking validation state for each chunk
    - Identifying chunks that need re-downloading
    """

    def __init__(self, config: ValidationConfig, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        # Map of file paths to their validation info
        self._file_validations: dict[str, FileValidationInfo] = {}

    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild(self.__class__.__name__)

    def create_chunks(self, file_path: str, file_size: int, chunk_size: Optional[int] = None) -> FileValidationInfo:
        """
        Create chunk definitions for a file.

        Args:
            file_path: Path to the file
            file_size: Size of the file in bytes
            chunk_size: Override chunk size (uses config default if None)

        Returns:
            FileValidationInfo with chunk definitions
        """
        actual_chunk_size = chunk_size or self.config.default_chunk_size

        # Ensure chunk size is within bounds
        actual_chunk_size = max(self.config.min_chunk_size, min(actual_chunk_size, self.config.max_chunk_size))

        chunks = []
        offset = 0
        index = 0

        while offset < file_size:
            # Calculate chunk size (last chunk may be smaller)
            remaining = file_size - offset
            size = min(actual_chunk_size, remaining)

            chunk = ChunkInfo(index=index, offset=offset, size=size, status=ChunkStatus.PENDING)
            chunks.append(chunk)

            offset += size
            index += 1

        validation_info = FileValidationInfo(
            file_path=file_path, file_size=file_size, algorithm=self.config.algorithm, chunks=chunks
        )

        self._file_validations[file_path] = validation_info
        self.logger.debug(
            f"Created {len(chunks)} chunks for {file_path} (size={file_size}, chunk_size={actual_chunk_size})"
        )

        return validation_info

    def get_validation_info(self, file_path: str) -> Optional[FileValidationInfo]:
        """Get validation info for a file."""
        return self._file_validations.get(file_path)

    def get_pending_chunks(self, file_path: str) -> list[ChunkInfo]:
        """Get all pending chunks for a file."""
        info = self._file_validations.get(file_path)
        if not info:
            return []
        return [c for c in info.chunks if c.status == ChunkStatus.PENDING]

    def get_corrupt_chunks(self, file_path: str) -> list[ChunkInfo]:
        """Get all corrupt chunks for a file."""
        info = self._file_validations.get(file_path)
        if not info:
            return []
        return info.corrupt_chunks

    def update_chunk_checksum(
        self,
        file_path: str,
        chunk_index: int,
        local_checksum: Optional[str] = None,
        remote_checksum: Optional[str] = None,
    ) -> Optional[ChunkInfo]:
        """
        Update checksum values for a chunk.

        Args:
            file_path: Path to the file
            chunk_index: Index of the chunk to update
            local_checksum: Local checksum value
            remote_checksum: Remote checksum value

        Returns:
            Updated ChunkInfo or None if not found
        """
        info = self._file_validations.get(file_path)
        if not info or chunk_index >= len(info.chunks):
            return None

        chunk = info.chunks[chunk_index]
        if local_checksum is not None:
            chunk.local_checksum = local_checksum
        if remote_checksum is not None:
            chunk.remote_checksum = remote_checksum

        return chunk

    def validate_chunk(self, file_path: str, chunk_index: int) -> Optional[bool]:
        """
        Validate a single chunk by comparing checksums.

        Args:
            file_path: Path to the file
            chunk_index: Index of the chunk to validate

        Returns:
            True if valid, False if corrupt, None if checksums not available
        """
        info = self._file_validations.get(file_path)
        if not info or chunk_index >= len(info.chunks):
            return None

        chunk = info.chunks[chunk_index]

        if chunk.local_checksum is None or chunk.remote_checksum is None:
            return None

        chunk.status = ChunkStatus.VALIDATING

        if chunk.local_checksum == chunk.remote_checksum:
            chunk.mark_valid()
            self.logger.debug(f"Chunk {chunk_index} of {file_path} validated successfully")
            return True
        else:
            chunk.mark_corrupt()
            self.logger.warning(
                f"Chunk {chunk_index} of {file_path} is corrupt "
                f"(local={chunk.local_checksum[:8]}... "
                f"remote={chunk.remote_checksum[:8]}...)"
            )
            return False

    def validate_all_chunks(self, file_path: str) -> tuple[int, int]:
        """
        Validate all chunks that have both checksums.

        Args:
            file_path: Path to the file

        Returns:
            Tuple of (valid_count, corrupt_count)
        """
        info = self._file_validations.get(file_path)
        if not info:
            return (0, 0)

        valid_count = 0
        corrupt_count = 0

        for i, chunk in enumerate(info.chunks):
            result = self.validate_chunk(file_path, i)
            if result is True:
                valid_count += 1
            elif result is False:
                corrupt_count += 1

        return (valid_count, corrupt_count)

    def mark_file_complete(self, file_path: str, is_valid: bool) -> Optional[FileValidationInfo]:
        """
        Mark a file's validation as complete.

        Args:
            file_path: Path to the file
            is_valid: Whether the file passed validation

        Returns:
            Updated FileValidationInfo or None if not found
        """
        info = self._file_validations.get(file_path)
        if not info:
            return None

        info.is_complete = True
        info.is_valid = is_valid

        self.logger.info(f"Validation complete for {file_path}: {'VALID' if is_valid else 'CORRUPT'}")

        return info

    def set_full_file_checksums(
        self, file_path: str, local_checksum: Optional[str] = None, remote_checksum: Optional[str] = None
    ) -> Optional[FileValidationInfo]:
        """
        Set full file checksums for final validation.

        Args:
            file_path: Path to the file
            local_checksum: Full file local checksum
            remote_checksum: Full file remote checksum

        Returns:
            Updated FileValidationInfo or None if not found
        """
        info = self._file_validations.get(file_path)
        if not info:
            return None

        if local_checksum is not None:
            info.local_full_checksum = local_checksum
        if remote_checksum is not None:
            info.full_file_checksum = remote_checksum

        return info

    def validate_full_file(self, file_path: str) -> Optional[bool]:
        """
        Validate file using full file checksum.

        Args:
            file_path: Path to the file

        Returns:
            True if valid, False if corrupt, None if checksums not available
        """
        info = self._file_validations.get(file_path)
        if not info:
            return None

        if info.local_full_checksum is None or info.full_file_checksum is None:
            return None

        is_valid = info.local_full_checksum == info.full_file_checksum
        self.mark_file_complete(file_path, is_valid)

        return is_valid

    def can_retry_chunk(self, file_path: str, chunk_index: int) -> bool:
        """
        Check if a chunk can be retried based on max_retries config.

        Args:
            file_path: Path to the file
            chunk_index: Index of the chunk

        Returns:
            True if retry is allowed
        """
        info = self._file_validations.get(file_path)
        if not info or chunk_index >= len(info.chunks):
            return False

        chunk = info.chunks[chunk_index]
        return chunk.retry_count < self.config.max_retries

    def mark_chunk_downloading(self, file_path: str, chunk_index: int) -> Optional[ChunkInfo]:
        """
        Mark a chunk as being re-downloaded.

        Args:
            file_path: Path to the file
            chunk_index: Index of the chunk

        Returns:
            Updated ChunkInfo or None if not found
        """
        info = self._file_validations.get(file_path)
        if not info or chunk_index >= len(info.chunks):
            return None

        chunk = info.chunks[chunk_index]
        chunk.mark_downloading()

        return chunk

    def reset_chunk(self, file_path: str, chunk_index: int) -> Optional[ChunkInfo]:
        """
        Reset a chunk to pending state (after re-download).

        Args:
            file_path: Path to the file
            chunk_index: Index of the chunk

        Returns:
            Updated ChunkInfo or None if not found
        """
        info = self._file_validations.get(file_path)
        if not info or chunk_index >= len(info.chunks):
            return None

        chunk = info.chunks[chunk_index]
        chunk.status = ChunkStatus.PENDING
        chunk.local_checksum = None

        return chunk

    def remove_file(self, file_path: str) -> bool:
        """
        Remove a file from tracking.

        Args:
            file_path: Path to the file

        Returns:
            True if file was removed, False if not found
        """
        if file_path in self._file_validations:
            del self._file_validations[file_path]
            return True
        return False

    def get_all_files(self) -> list[str]:
        """Get all tracked file paths."""
        return list(self._file_validations.keys())

    def get_validation_progress(self, file_path: str) -> float:
        """
        Get validation progress for a file.

        Args:
            file_path: Path to the file

        Returns:
            Progress from 0.0 to 1.0
        """
        info = self._file_validations.get(file_path)
        if not info:
            return 0.0
        return info.progress

    def get_overall_stats(self) -> dict:
        """
        Get overall validation statistics.

        Returns:
            Dictionary with total files, completed, valid, corrupt counts
        """
        total_files = len(self._file_validations)
        completed = sum(1 for info in self._file_validations.values() if info.is_complete)
        valid = sum(1 for info in self._file_validations.values() if info.is_valid is True)
        corrupt = sum(1 for info in self._file_validations.values() if info.is_valid is False)
        in_progress = total_files - completed

        return {
            "total_files": total_files,
            "completed": completed,
            "valid": valid,
            "corrupt": corrupt,
            "in_progress": in_progress,
        }
