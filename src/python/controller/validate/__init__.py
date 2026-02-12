# Copyright 2024, RapidCopy Contributors, All rights reserved.

"""
Validation module for download integrity verification.

This module provides:
- Checksum generation (local and remote via SSH)
- Chunk-based file validation
- Adaptive chunk sizing based on network conditions
- Async validation process for non-blocking operation
"""

from .checksum import ChecksumGenerator, RemoteChecksumGenerator, LocalChecksumGenerator
from .chunk_manager import ChunkManager
from .adaptive_sizing import AdaptiveChunkSizer
from .validation_process import ValidationProcess, ValidationStatusResult, ValidationCompletedResult

__all__ = [
    "ChecksumGenerator",
    "RemoteChecksumGenerator",
    "LocalChecksumGenerator",
    "ChunkManager",
    "AdaptiveChunkSizer",
    "ValidationProcess",
    "ValidationStatusResult",
    "ValidationCompletedResult",
]
