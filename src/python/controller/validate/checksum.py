# Copyright 2024, RapidCopy Contributors, All rights reserved.

"""
Checksum generation for file validation.

This module provides:
- Local file checksum generation using hashlib
- Remote file checksum generation via SSH commands
- Chunk-level checksum computation
"""

import hashlib
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

from common import ValidationAlgorithm, ChunkInfo, AppError
from ssh import Sshcp, SshcpError


class ChecksumError(AppError):
    """Exception raised when checksum generation fails."""

    pass


class ChecksumGenerator(ABC):
    """Abstract base class for checksum generation."""

    def __init__(self, algorithm: ValidationAlgorithm = ValidationAlgorithm.MD5):
        self.algorithm = algorithm
        self.logger = logging.getLogger(self.__class__.__name__)

    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild(self.__class__.__name__)

    @abstractmethod
    def compute_file_checksum(self, file_path: str) -> str:
        """
        Compute checksum for an entire file.

        Args:
            file_path: Path to the file

        Returns:
            Hexadecimal checksum string
        """
        pass

    @abstractmethod
    def compute_chunk_checksum(self, file_path: str, offset: int, size: int) -> str:
        """
        Compute checksum for a specific chunk of a file.

        Args:
            file_path: Path to the file
            offset: Byte offset where chunk starts
            size: Size of the chunk in bytes

        Returns:
            Hexadecimal checksum string
        """
        pass

    @abstractmethod
    def compute_chunk_checksums(self, file_path: str, chunks: list[ChunkInfo]) -> list[str]:
        """
        Compute checksums for multiple chunks of a file.

        Args:
            file_path: Path to the file
            chunks: List of ChunkInfo objects describing the chunks

        Returns:
            List of hexadecimal checksum strings in chunk order
        """
        pass


class LocalChecksumGenerator(ChecksumGenerator):
    """Generate checksums for local files."""

    def __init__(self, algorithm: ValidationAlgorithm = ValidationAlgorithm.MD5, buffer_size: int = 8192):
        super().__init__(algorithm)
        self.buffer_size = buffer_size

    def _get_hasher(self):
        """Create a new hasher instance based on the algorithm."""
        if self.algorithm == ValidationAlgorithm.MD5:
            return hashlib.md5()
        elif self.algorithm == ValidationAlgorithm.SHA256:
            return hashlib.sha256()
        elif self.algorithm == ValidationAlgorithm.SHA1:
            return hashlib.sha1()
        else:
            raise ChecksumError(f"Unsupported algorithm: {self.algorithm}")

    def compute_file_checksum(self, file_path: str) -> str:
        """Compute checksum for an entire local file."""
        if not os.path.exists(file_path):
            raise ChecksumError(f"File not found: {file_path}")
        if os.path.isdir(file_path):
            raise ChecksumError(f"Cannot compute checksum for directory: {file_path}")

        hasher = self._get_hasher()
        try:
            with open(file_path, "rb") as f:
                while True:
                    data = f.read(self.buffer_size)
                    if not data:
                        break
                    hasher.update(data)
            return hasher.hexdigest()
        except IOError as e:
            raise ChecksumError(f"Error reading file {file_path}: {e}") from e

    def compute_chunk_checksum(self, file_path: str, offset: int, size: int) -> str:
        """Compute checksum for a specific chunk of a local file."""
        if not os.path.exists(file_path):
            raise ChecksumError(f"File not found: {file_path}")
        if os.path.isdir(file_path):
            raise ChecksumError(f"Cannot compute checksum for directory: {file_path}")

        hasher = self._get_hasher()
        try:
            with open(file_path, "rb") as f:
                f.seek(offset)
                remaining = size
                while remaining > 0:
                    to_read = min(self.buffer_size, remaining)
                    data = f.read(to_read)
                    if not data:
                        break
                    hasher.update(data)
                    remaining -= len(data)
            return hasher.hexdigest()
        except IOError as e:
            raise ChecksumError(f"Error reading file {file_path}: {e}") from e

    def compute_chunk_checksums(self, file_path: str, chunks: list[ChunkInfo]) -> list[str]:
        """Compute checksums for multiple chunks of a local file."""
        checksums = []
        for chunk in chunks:
            checksum = self.compute_chunk_checksum(file_path, chunk.offset, chunk.size)
            checksums.append(checksum)
        return checksums


class RemoteChecksumGenerator(ChecksumGenerator):
    """Generate checksums for remote files via SSH."""

    def __init__(self, sshcp: Sshcp, algorithm: ValidationAlgorithm = ValidationAlgorithm.MD5):
        super().__init__(algorithm)
        self._sshcp = sshcp

    def _get_checksum_command(self) -> str:
        """Get the remote command name for the algorithm."""
        if self.algorithm == ValidationAlgorithm.MD5:
            return "md5sum"
        elif self.algorithm == ValidationAlgorithm.SHA256:
            return "sha256sum"
        elif self.algorithm == ValidationAlgorithm.SHA1:
            return "sha1sum"
        else:
            raise ChecksumError(f"Unsupported algorithm: {self.algorithm}")

    def _parse_checksum_output(self, output: bytes) -> str:
        """Parse the output of a checksum command to extract the hash."""
        # Output format: "hash  filename" or just "hash -"
        try:
            decoded = output.decode().strip()
            # Handle output format: "checksum  filename"
            parts = decoded.split()
            if len(parts) >= 1:
                return parts[0]
            raise ChecksumError(f"Unexpected checksum output format: {decoded}")
        except UnicodeDecodeError as e:
            raise ChecksumError(f"Failed to decode checksum output: {e}") from e

    def compute_file_checksum(self, file_path: str) -> str:
        """Compute checksum for an entire remote file."""
        cmd = self._get_checksum_command()
        # Escape the file path for shell
        escaped_path = file_path.replace("'", "'\\''")
        command = f"{cmd} '{escaped_path}'"

        self.logger.debug(f"Remote checksum command: {command}")
        try:
            output = self._sshcp.shell(command)
            return self._parse_checksum_output(output)
        except SshcpError as e:
            raise ChecksumError(f"Remote checksum failed for {file_path}: {e}") from e

    def compute_chunk_checksum(self, file_path: str, offset: int, size: int) -> str:
        """
        Compute checksum for a specific chunk of a remote file.

        Uses dd to extract the chunk and pipes to checksum command.
        """
        cmd = self._get_checksum_command()
        escaped_path = file_path.replace("'", "'\\''")

        # Use dd to extract the specific chunk
        # bs=1 with skip and count for byte-level precision
        # For better performance with large files, we use a larger block size
        # and calculate skip/count accordingly when possible
        if offset % 4096 == 0 and size % 4096 == 0:
            # Can use 4KB blocks for better performance
            block_size = 4096
            skip_blocks = offset // block_size
            count_blocks = size // block_size
            command = (
                f"dd if='{escaped_path}' bs={block_size} skip={skip_blocks} count={count_blocks} 2>/dev/null | {cmd}"
            )
        else:
            # Fall back to byte-level precision
            command = f"dd if='{escaped_path}' bs=1 skip={offset} count={size} 2>/dev/null | {cmd}"

        self.logger.debug(f"Remote chunk checksum command: {command}")
        try:
            output = self._sshcp.shell(command)
            return self._parse_checksum_output(output)
        except SshcpError as e:
            raise ChecksumError(
                f"Remote chunk checksum failed for {file_path} (offset={offset}, size={size}): {e}"
            ) from e

    # Maximum number of chunk checksum commands per SSH call.
    # Each dd|checksum command is ~120 chars. Batching avoids exceeding
    # the OS argument list limit (ARG_MAX, typically 128-256 KB) which
    # causes "OSError: Argument list too long" for large files with
    # thousands of chunks.
    _MAX_CHUNKS_PER_BATCH = 100

    def compute_chunk_checksums(self, file_path: str, chunks: list[ChunkInfo]) -> list[str]:
        """
        Compute checksums for multiple chunks of a remote file.

        Chunks are batched into groups to avoid exceeding the OS
        argument list limit. Each batch is computed in a single SSH
        session for efficiency.
        """
        if not chunks:
            return []

        all_checksums = []
        total_batches = (len(chunks) + self._MAX_CHUNKS_PER_BATCH - 1) // self._MAX_CHUNKS_PER_BATCH
        for batch_num, batch_start in enumerate(range(0, len(chunks), self._MAX_CHUNKS_PER_BATCH), 1):
            batch = chunks[batch_start : batch_start + self._MAX_CHUNKS_PER_BATCH]
            self.logger.debug(
                f"Computing checksums batch {batch_num}/{total_batches} "
                f"({len(batch)} chunks) for {file_path}"
            )
            batch_checksums = self._compute_chunk_batch(file_path, batch)
            all_checksums.extend(batch_checksums)

        return all_checksums

    def _compute_chunk_batch(self, file_path: str, chunks: list[ChunkInfo]) -> list[str]:
        """Compute checksums for a batch of chunks in a single SSH session."""
        cmd = self._get_checksum_command()
        escaped_path = file_path.replace("'", "'\\''")

        # Build a shell script that computes all checksums in this batch
        script_parts = []
        for chunk in chunks:
            if chunk.offset % 4096 == 0 and chunk.size % 4096 == 0:
                block_size = 4096
                skip_blocks = chunk.offset // block_size
                count_blocks = chunk.size // block_size
                part = (
                    f"dd if='{escaped_path}' bs={block_size} "
                    f"skip={skip_blocks} count={count_blocks} 2>/dev/null | {cmd}"
                )
            else:
                part = f"dd if='{escaped_path}' bs=1 skip={chunk.offset} count={chunk.size} 2>/dev/null | {cmd}"
            script_parts.append(part)

        # Join with semicolons to run sequentially
        command = "; ".join(script_parts)

        try:
            output = self._sshcp.shell(command)
            # Parse multiple checksum lines
            lines = output.decode().strip().split("\n")
            checksums = []
            for line in lines:
                parts = line.strip().split()
                if parts:
                    checksums.append(parts[0])

            if len(checksums) != len(chunks):
                raise ChecksumError(f"Expected {len(chunks)} checksums, got {len(checksums)}")
            return checksums
        except SshcpError as e:
            raise ChecksumError(f"Remote batch checksum failed for {file_path}: {e}") from e
        except OSError as e:
            raise ChecksumError(f"Remote batch checksum OS error for {file_path}: {e}") from e

    def check_remote_command_available(self) -> bool:
        """Check if the remote checksum command is available."""
        cmd = self._get_checksum_command()
        try:
            self._sshcp.shell(f"which {cmd}")
            return True
        except SshcpError:
            return False
