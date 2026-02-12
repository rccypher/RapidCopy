# Copyright 2024, RapidCopy Contributors, All rights reserved.

"""
Multi-path scanner implementations that aggregate results from multiple path pairs.
"""

import logging
from typing import List

from .scanner_process import IScanner, ScannerError
from .local_scanner import LocalScanner
from .remote_scanner import RemoteScanner
from common import overrides
from system import SystemFile


class MultiPathLocalScanner(IScanner):
    """
    Scanner that aggregates local scan results from multiple path pairs.

    Each file is tagged with the path_pair_id it belongs to via a custom attribute.
    """

    def __init__(self, scanners: List[LocalScanner]):
        """
        Initialize with a list of LocalScanner instances, one per path pair.

        Args:
            scanners: List of LocalScanner instances configured for each path pair
        """
        self.logger = logging.getLogger("MultiPathLocalScanner")
        self.__scanners = scanners

    @overrides(IScanner)
    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild("MultiPathLocalScanner")
        for scanner in self.__scanners:
            scanner.set_base_logger(self.logger)

    @overrides(IScanner)
    def scan(self) -> List[SystemFile]:
        """
        Scan all configured local paths and aggregate results.

        Files are tagged with path_pair metadata via custom attributes.
        """
        all_files: List[SystemFile] = []

        for scanner in self.__scanners:
            try:
                files = scanner.scan()
                # Tag each file with path pair info
                for file in files:
                    file.path_pair_id = scanner.path_pair_id
                    file.path_pair_name = scanner.path_pair_name
                all_files.extend(files)
            except ScannerError as e:
                # Log but continue with other scanners
                self.logger.warning(f"Failed to scan local path for pair '{scanner.path_pair_name}': {e}")
                # Re-raise if it's not recoverable
                if not e.recoverable:
                    raise

        return all_files


class MultiPathRemoteScanner(IScanner):
    """
    Scanner that aggregates remote scan results from multiple path pairs.

    Each file is tagged with the path_pair_id it belongs to via a custom attribute.
    """

    def __init__(self, scanners: List[RemoteScanner]):
        """
        Initialize with a list of RemoteScanner instances, one per path pair.

        Args:
            scanners: List of RemoteScanner instances configured for each path pair
        """
        self.logger = logging.getLogger("MultiPathRemoteScanner")
        self.__scanners = scanners

    @overrides(IScanner)
    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild("MultiPathRemoteScanner")
        for scanner in self.__scanners:
            scanner.set_base_logger(self.logger)

    @overrides(IScanner)
    def scan(self) -> List[SystemFile]:
        """
        Scan all configured remote paths and aggregate results.

        Files are tagged with path_pair metadata via custom attributes.
        """
        all_files: List[SystemFile] = []

        for scanner in self.__scanners:
            try:
                files = scanner.scan()
                # Tag each file with path pair info
                for file in files:
                    file.path_pair_id = scanner.path_pair_id
                    file.path_pair_name = scanner.path_pair_name
                all_files.extend(files)
            except ScannerError as e:
                # Log but continue with other scanners
                self.logger.warning(f"Failed to scan remote path for pair '{scanner.path_pair_name}': {e}")
                # Re-raise if it's not recoverable
                if not e.recoverable:
                    raise

        return all_files
