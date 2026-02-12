# Copyright 2024, RapidCopy Contributors, All rights reserved.

"""
Validation models for download integrity verification.

This module provides data classes for managing file validation,
including chunk-level checksums and adaptive sizing configuration.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ChunkStatus(Enum):
    """Status of a file chunk during validation."""

    PENDING = 0  # Not yet validated
    VALIDATING = 1  # Currently being validated
    VALID = 2  # Checksum matches
    CORRUPT = 3  # Checksum mismatch
    DOWNLOADING = 4  # Re-downloading due to corruption
    SKIPPED = 5  # Skipped (e.g., for directories)


class ValidationAlgorithm(Enum):
    """Supported checksum algorithms."""

    MD5 = "md5"
    SHA256 = "sha256"
    SHA1 = "sha1"


@dataclass
class ChunkInfo:
    """
    Represents a chunk of a file for validation purposes.

    Attributes:
        index: Chunk index (0-based)
        offset: Byte offset in the file
        size: Chunk size in bytes
        remote_checksum: Expected checksum from remote server
        local_checksum: Calculated checksum from local file
        status: Current status of this chunk
        retry_count: Number of times this chunk has been re-downloaded
    """

    index: int
    offset: int
    size: int
    remote_checksum: Optional[str] = None
    local_checksum: Optional[str] = None
    status: ChunkStatus = ChunkStatus.PENDING
    retry_count: int = 0

    @property
    def end_offset(self) -> int:
        """Returns the byte offset where this chunk ends (exclusive)."""
        return self.offset + self.size

    @property
    def is_valid(self) -> bool:
        """Returns True if chunk has matching checksums."""
        return (
            self.remote_checksum is not None
            and self.local_checksum is not None
            and self.remote_checksum == self.local_checksum
        )

    def mark_valid(self):
        """Mark this chunk as valid."""
        self.status = ChunkStatus.VALID

    def mark_corrupt(self):
        """Mark this chunk as corrupt."""
        self.status = ChunkStatus.CORRUPT

    def mark_downloading(self):
        """Mark this chunk as being re-downloaded."""
        self.status = ChunkStatus.DOWNLOADING
        self.retry_count += 1


@dataclass
class FileValidationInfo:
    """
    Tracks validation state for a single file.

    Attributes:
        file_path: Relative path to the file
        file_size: Total size of the file in bytes
        algorithm: Checksum algorithm being used
        chunks: List of chunk information
        full_file_checksum: Optional full-file checksum for final verification
        is_complete: Whether validation has completed
        is_valid: Whether file passed validation (None if incomplete)
    """

    file_path: str
    file_size: int
    algorithm: ValidationAlgorithm = ValidationAlgorithm.MD5
    chunks: list[ChunkInfo] = field(default_factory=list)
    full_file_checksum: Optional[str] = None
    local_full_checksum: Optional[str] = None
    is_complete: bool = False
    is_valid: Optional[bool] = None

    @property
    def total_chunks(self) -> int:
        """Returns the total number of chunks."""
        return len(self.chunks)

    @property
    def validated_chunks(self) -> int:
        """Returns the number of validated chunks."""
        return sum(1 for c in self.chunks if c.status in (ChunkStatus.VALID, ChunkStatus.CORRUPT))

    @property
    def valid_chunks(self) -> int:
        """Returns the number of valid chunks."""
        return sum(1 for c in self.chunks if c.status == ChunkStatus.VALID)

    @property
    def corrupt_chunks(self) -> list[ChunkInfo]:
        """Returns list of corrupt chunks."""
        return [c for c in self.chunks if c.status == ChunkStatus.CORRUPT]

    @property
    def corrupt_chunk_indices(self) -> list[int]:
        """Returns list of corrupt chunk indices."""
        return [c.index for c in self.chunks if c.status == ChunkStatus.CORRUPT]

    @property
    def progress(self) -> float:
        """Returns validation progress from 0.0 to 1.0."""
        if not self.chunks:
            return 0.0
        return self.validated_chunks / self.total_chunks


@dataclass
class ValidationConfig:
    """
    Configuration for download validation.

    Attributes:
        enabled: Whether validation is enabled
        algorithm: Checksum algorithm to use
        default_chunk_size: Default chunk size in bytes (10MB default)
        min_chunk_size: Minimum chunk size in bytes (1MB default)
        max_chunk_size: Maximum chunk size in bytes (100MB default)
        validate_after_chunk: Whether to validate immediately after each chunk downloads
        validate_after_file: Whether to validate after complete file download
        max_retries: Maximum number of retry attempts for corrupt chunks
        retry_delay_ms: Delay between retries in milliseconds
        enable_adaptive_sizing: Whether to use adaptive chunk sizing
        parallel_validation: Number of parallel validation workers (0 = auto)
    """

    enabled: bool = True
    algorithm: ValidationAlgorithm = ValidationAlgorithm.MD5
    default_chunk_size: int = 10 * 1024 * 1024  # 10MB
    min_chunk_size: int = 1 * 1024 * 1024  # 1MB
    max_chunk_size: int = 100 * 1024 * 1024  # 100MB
    validate_after_chunk: bool = False
    validate_after_file: bool = True
    max_retries: int = 3
    retry_delay_ms: int = 1000
    enable_adaptive_sizing: bool = True
    parallel_validation: int = 0  # 0 = auto (use CPU count)

    def __post_init__(self):
        """Validate configuration values."""
        if self.min_chunk_size <= 0:
            raise ValueError("min_chunk_size must be positive")
        if self.max_chunk_size < self.min_chunk_size:
            raise ValueError("max_chunk_size must be >= min_chunk_size")
        if self.default_chunk_size < self.min_chunk_size:
            raise ValueError("default_chunk_size must be >= min_chunk_size")
        if self.default_chunk_size > self.max_chunk_size:
            raise ValueError("default_chunk_size must be <= max_chunk_size")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")

    @classmethod
    def from_dict(cls, config_dict: dict) -> "ValidationConfig":
        """Create ValidationConfig from a dictionary."""
        # Handle algorithm conversion
        if "algorithm" in config_dict:
            algo = config_dict["algorithm"]
            if isinstance(algo, str):
                config_dict = dict(config_dict)  # Make a copy
                config_dict["algorithm"] = ValidationAlgorithm(algo.lower())
        return cls(**config_dict)

    def as_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "enabled": self.enabled,
            "algorithm": self.algorithm.value,
            "default_chunk_size": self.default_chunk_size,
            "min_chunk_size": self.min_chunk_size,
            "max_chunk_size": self.max_chunk_size,
            "validate_after_chunk": self.validate_after_chunk,
            "validate_after_file": self.validate_after_file,
            "max_retries": self.max_retries,
            "retry_delay_ms": self.retry_delay_ms,
            "enable_adaptive_sizing": self.enable_adaptive_sizing,
            "parallel_validation": self.parallel_validation,
        }


@dataclass
class NetworkStats:
    """
    Network statistics for adaptive chunk sizing.

    Attributes:
        avg_speed_bytes_per_sec: Average transfer speed
        recent_failure_rate: Failure rate of recent transfers (0.0 to 1.0)
        recent_chunk_failures: Number of chunk failures in recent window
        recent_chunk_successes: Number of chunk successes in recent window
    """

    avg_speed_bytes_per_sec: float = 0.0
    recent_failure_rate: float = 0.0
    recent_chunk_failures: int = 0
    recent_chunk_successes: int = 0

    def record_chunk_result(self, success: bool):
        """Record the result of a chunk validation."""
        if success:
            self.recent_chunk_successes += 1
        else:
            self.recent_chunk_failures += 1

        total = self.recent_chunk_failures + self.recent_chunk_successes
        if total > 0:
            self.recent_failure_rate = self.recent_chunk_failures / total

    def reset_window(self):
        """Reset the statistics window."""
        self.recent_chunk_failures = 0
        self.recent_chunk_successes = 0
        self.recent_failure_rate = 0.0
