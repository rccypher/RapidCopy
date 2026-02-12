# Copyright 2024, RapidCopy Contributors, All rights reserved.

"""
Adaptive chunk sizing for file validation.

This module provides intelligent chunk size calculation based on:
- File size
- Network conditions
- Historical failure rates
- Transfer speed
"""

import logging
from typing import Optional

from common import ValidationConfig, NetworkStats


class AdaptiveChunkSizer:
    """
    Calculates optimal chunk sizes based on various factors.

    The algorithm considers:
    - File size: Larger files can use larger chunks
    - Network speed: Slower connections benefit from smaller chunks
    - Failure rate: Higher failure rates mean smaller chunks
    - Configuration bounds: min/max chunk size constraints
    """

    # Thresholds for file size-based adjustments
    SMALL_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB
    MEDIUM_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB
    LARGE_FILE_THRESHOLD = 1024 * 1024 * 1024  # 1GB

    # Network speed thresholds (bytes/sec)
    SLOW_NETWORK_THRESHOLD = 1 * 1024 * 1024  # 1 MB/s
    FAST_NETWORK_THRESHOLD = 10 * 1024 * 1024  # 10 MB/s

    # Failure rate thresholds
    LOW_FAILURE_THRESHOLD = 0.01  # 1%
    HIGH_FAILURE_THRESHOLD = 0.05  # 5%

    def __init__(self, config: ValidationConfig, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._network_stats = NetworkStats()

    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild(self.__class__.__name__)

    @property
    def network_stats(self) -> NetworkStats:
        """Get current network statistics."""
        return self._network_stats

    def update_network_stats(self, avg_speed: Optional[float] = None, chunk_success: Optional[bool] = None):
        """
        Update network statistics.

        Args:
            avg_speed: Average transfer speed in bytes/sec
            chunk_success: Whether the last chunk validation succeeded
        """
        if avg_speed is not None:
            self._network_stats.avg_speed_bytes_per_sec = avg_speed
        if chunk_success is not None:
            self._network_stats.record_chunk_result(chunk_success)

    def calculate_chunk_size(self, file_size: int, network_stats: Optional[NetworkStats] = None) -> int:
        """
        Calculate optimal chunk size for a file.

        Args:
            file_size: Size of the file in bytes
            network_stats: Optional network statistics (uses internal if None)

        Returns:
            Recommended chunk size in bytes
        """
        if not self.config.enable_adaptive_sizing:
            return self.config.default_chunk_size

        stats = network_stats or self._network_stats

        # Start with default chunk size
        chunk_size = self.config.default_chunk_size

        # Adjust based on file size
        chunk_size = self._adjust_for_file_size(chunk_size, file_size)

        # Adjust based on network speed
        chunk_size = self._adjust_for_network_speed(chunk_size, stats)

        # Adjust based on failure rate
        chunk_size = self._adjust_for_failure_rate(chunk_size, stats)

        # Ensure bounds
        chunk_size = max(self.config.min_chunk_size, min(chunk_size, self.config.max_chunk_size))

        # Ensure chunk size doesn't exceed file size
        chunk_size = min(chunk_size, file_size)

        self.logger.debug(
            f"Calculated chunk size: {chunk_size} bytes "
            f"(file_size={file_size}, speed={stats.avg_speed_bytes_per_sec:.0f}, "
            f"failure_rate={stats.recent_failure_rate:.2%})"
        )

        return chunk_size

    def _adjust_for_file_size(self, chunk_size: int, file_size: int) -> int:
        """
        Adjust chunk size based on file size.

        - Small files: Use smaller chunks (more granular validation)
        - Large files: Use larger chunks (fewer SSH calls)
        """
        if file_size < self.SMALL_FILE_THRESHOLD:
            # Small files: use 1/4 of default or file size / 4
            return min(chunk_size // 4, file_size // 4) or chunk_size
        elif file_size < self.MEDIUM_FILE_THRESHOLD:
            # Medium files: use default
            return chunk_size
        elif file_size < self.LARGE_FILE_THRESHOLD:
            # Large files: increase by 50%
            return int(chunk_size * 1.5)
        else:
            # Very large files: double the chunk size
            return chunk_size * 2

    def _adjust_for_network_speed(self, chunk_size: int, stats: NetworkStats) -> int:
        """
        Adjust chunk size based on network speed.

        - Slow networks: Use smaller chunks (less data to re-download on failure)
        - Fast networks: Use larger chunks (more efficient)
        """
        speed = stats.avg_speed_bytes_per_sec

        if speed <= 0:
            # No speed data, use default
            return chunk_size

        if speed < self.SLOW_NETWORK_THRESHOLD:
            # Slow network: reduce chunk size by 50%
            return chunk_size // 2
        elif speed > self.FAST_NETWORK_THRESHOLD:
            # Fast network: increase chunk size by 50%
            return int(chunk_size * 1.5)

        return chunk_size

    def _adjust_for_failure_rate(self, chunk_size: int, stats: NetworkStats) -> int:
        """
        Adjust chunk size based on recent failure rate.

        - Low failure rate: Can use larger chunks
        - High failure rate: Use smaller chunks to minimize re-downloads
        """
        failure_rate = stats.recent_failure_rate

        if failure_rate < self.LOW_FAILURE_THRESHOLD:
            # Very low failure rate, can increase chunk size
            return int(chunk_size * 1.25)
        elif failure_rate > self.HIGH_FAILURE_THRESHOLD:
            # High failure rate, significantly reduce chunk size
            # The higher the failure rate, the smaller the chunks
            reduction_factor = min(0.5, 1 - failure_rate)
            return int(chunk_size * reduction_factor)

        return chunk_size

    def calculate_target_chunks(self, file_size: int, target_chunk_count: int = 10) -> int:
        """
        Calculate chunk size to achieve a target number of chunks.

        Useful for UI purposes where you want consistent progress updates.

        Args:
            file_size: Size of the file in bytes
            target_chunk_count: Desired number of chunks

        Returns:
            Chunk size in bytes
        """
        if target_chunk_count <= 0:
            target_chunk_count = 1

        chunk_size = file_size // target_chunk_count

        # Ensure bounds
        return max(self.config.min_chunk_size, min(chunk_size, self.config.max_chunk_size))

    def recommend_validation_strategy(self, file_size: int, network_stats: Optional[NetworkStats] = None) -> dict:
        """
        Recommend a validation strategy based on conditions.

        Args:
            file_size: Size of the file in bytes
            network_stats: Optional network statistics

        Returns:
            Dictionary with recommended settings:
            - chunk_size: Recommended chunk size
            - validate_after_chunk: Whether to validate after each chunk
            - validate_after_file: Whether to validate after full file
            - estimated_chunks: Number of chunks
        """
        stats = network_stats or self._network_stats
        chunk_size = self.calculate_chunk_size(file_size, stats)
        estimated_chunks = (file_size + chunk_size - 1) // chunk_size

        # Determine validation timing based on conditions
        high_failure_rate = stats.recent_failure_rate > self.HIGH_FAILURE_THRESHOLD
        slow_network = stats.avg_speed_bytes_per_sec < self.SLOW_NETWORK_THRESHOLD
        large_file = file_size > self.LARGE_FILE_THRESHOLD

        # Validate after each chunk if:
        # - High failure rate (catch errors early)
        # - Very large file (don't wait until end)
        # - Slow network AND high failure (minimize wasted bandwidth)
        validate_after_chunk = (
            high_failure_rate or large_file or (slow_network and stats.recent_failure_rate > self.LOW_FAILURE_THRESHOLD)
        )

        # Always validate after file for final confirmation
        validate_after_file = True

        return {
            "chunk_size": chunk_size,
            "validate_after_chunk": validate_after_chunk,
            "validate_after_file": validate_after_file,
            "estimated_chunks": estimated_chunks,
        }

    def reset_stats(self):
        """Reset network statistics."""
        self._network_stats.reset_window()
        self.logger.debug("Network statistics reset")
