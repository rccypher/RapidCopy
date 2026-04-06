# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
from typing import List, Optional

from .scanner_process import IScanner, ScannerError
from common import overrides, Localization, Constants
from system import SystemScanner, SystemFile, SystemScannerError


class LocalScanner(IScanner):
    """
    Scanner implementation to scan the local filesystem.
    Scans both staging_path (in-progress downloads) and local_path (completed downloads).
    Results are merged: local_path takes precedence if the same name appears in both.
    """

    def __init__(
        self,
        local_path: str,
        use_temp_file: bool,
        path_pair_id: str | None = None,
        path_pair_name: str | None = None,
        staging_path: str | None = None,
    ):
        self.__local_path = local_path
        self.__staging_path = staging_path
        self.__scanner = SystemScanner(local_path)
        if use_temp_file:
            self.__scanner.set_lftp_temp_suffix(Constants.LFTP_TEMP_FILE_SUFFIX)
        self.__staging_scanner: SystemScanner | None
        if staging_path:
            self.__staging_scanner = SystemScanner(staging_path)
            if use_temp_file:
                self.__staging_scanner.set_lftp_temp_suffix(Constants.LFTP_TEMP_FILE_SUFFIX)
        else:
            self.__staging_scanner = None
        self.logger = logging.getLogger("LocalScanner")
        self.__path_pair_id = path_pair_id
        self.__path_pair_name = path_pair_name

    @property
    def path_pair_id(self) -> str | None:
        return self.__path_pair_id

    @property
    def path_pair_name(self) -> str | None:
        return self.__path_pair_name

    @property
    def local_path(self) -> str:
        return self.__local_path

    @overrides(IScanner)
    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild("LocalScanner")

    @overrides(IScanner)
    def scan(self) -> List[SystemFile]:
        # Scan staging_path (in-progress) first
        staging_result: List[SystemFile] = []
        if self.__staging_scanner:
            try:
                staging_result = self.__staging_scanner.scan()
            except SystemScannerError as e:
                self.logger.exception("Caught SystemScannerError from staging path")
                raise ScannerError(Localization.Error.LOCAL_SERVER_SCAN, recoverable=False) from e

        # Scan local_path (completed downloads)
        try:
            local_result = self.__scanner.scan()
        except SystemScannerError as e:
            self.logger.exception("Caught SystemScannerError")
            raise ScannerError(Localization.Error.LOCAL_SERVER_SCAN, recoverable=False) from e

        # Exclude the staging directory from local results (it's a child of local_path)
        if self.__staging_path:
            import os
            staging_basename = os.path.basename(self.__staging_path.rstrip("/"))
            local_result = [f for f in local_result if f.name != staging_basename]

        # Merge: local_path wins if same name appears in both (file was just moved)
        local_names = {f.name for f in local_result}
        for staging_file in staging_result:
            if staging_file.name not in local_names:
                local_result.append(staging_file)

        return local_result
