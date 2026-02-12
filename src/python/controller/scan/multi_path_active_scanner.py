# Copyright 2024, RapidCopy Contributors, All rights reserved.

"""
Multi-path active scanner implementation that routes active file scans
to the appropriate path pair scanner.
"""

import logging
import multiprocessing
import queue
from typing import List, Dict, Tuple

from .scanner_process import IScanner
from common import overrides
from system import SystemScanner, SystemScannerError, SystemFile


class MultiPathActiveScanner(IScanner):
    """
    Scanner implementation to scan active files across multiple path pairs.

    Unlike the single-path ActiveScanner, this scanner maintains separate
    SystemScanner instances for each path pair. Active files are routed
    to the appropriate scanner based on their path_pair_id.

    A multiprocessing.Queue is used to store the active files because the set
    and scan methods are called by different processes.
    """

    def __init__(self, path_pairs: Dict[str, str]):
        """
        Initialize with a mapping of path_pair_id to local_path.

        Args:
            path_pairs: Dict mapping path_pair_id to local_path
        """
        self.__scanners: Dict[str, SystemScanner] = {}
        for pair_id, local_path in path_pairs.items():
            self.__scanners[pair_id] = SystemScanner(local_path)

        # Queue stores list of (filename, path_pair_id) tuples
        self.__active_files_queue: multiprocessing.Queue[List[Tuple[str, str | None]]] = multiprocessing.Queue()
        self.__active_files: List[Tuple[str, str | None]] = []  # latest state
        self.logger = logging.getLogger(self.__class__.__name__)

        # Store path pairs for fallback
        self.__path_pairs = path_pairs
        # Default scanner for files without path_pair_id (uses first path)
        self.__default_scanner: SystemScanner | None = None
        if path_pairs:
            first_path = next(iter(path_pairs.values()))
            self.__default_scanner = SystemScanner(first_path)

    @overrides(IScanner)
    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild(self.__class__.__name__)

    def set_active_files(self, files: List[Tuple[str, str | None]]):
        """
        Set the list of active files to scan.

        Args:
            files: List of (filename, path_pair_id) tuples.
                   path_pair_id can be None for legacy single-path files.
        """
        self.__active_files_queue.put(files)

    @overrides(IScanner)
    def scan(self) -> List[SystemFile]:
        # Grab the latest list of active files, if any
        try:
            while True:
                self.__active_files = self.__active_files_queue.get(block=False)
        except queue.Empty:
            pass

        # Do the scan, routing each file to the appropriate scanner
        result: List[SystemFile] = []
        for file_name, path_pair_id in self.__active_files:
            scanner = self.__get_scanner_for_path_pair(path_pair_id)
            if scanner is None:
                self.logger.warning(f"No scanner found for path_pair_id '{path_pair_id}', skipping file '{file_name}'")
                continue

            try:
                sys_file = scanner.scan_single(file_name)
                # Tag the file with its path pair ID
                if path_pair_id:
                    sys_file.path_pair_id = path_pair_id
                result.append(sys_file)
            except SystemScannerError as ex:
                # Ignore errors here, file may have been deleted
                self.logger.warning(str(ex))

        return result

    def __get_scanner_for_path_pair(self, path_pair_id: str | None) -> SystemScanner | None:
        """
        Get the appropriate scanner for a path pair ID.

        Args:
            path_pair_id: The path pair ID, or None for default

        Returns:
            The SystemScanner for the path pair, or None if not found
        """
        if path_pair_id and path_pair_id in self.__scanners:
            return self.__scanners[path_pair_id]
        elif self.__default_scanner:
            return self.__default_scanner
        return None
