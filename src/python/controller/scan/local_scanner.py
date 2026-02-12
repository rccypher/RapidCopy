# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
from typing import List

from .scanner_process import IScanner, ScannerError
from common import overrides, Localization, Constants
from system import SystemScanner, SystemFile, SystemScannerError


class LocalScanner(IScanner):
    """
    Scanner implementation to scan the local filesystem
    """

    def __init__(
        self,
        local_path: str,
        use_temp_file: bool,
        path_pair_id: str | None = None,
        path_pair_name: str | None = None,
    ):
        self.__scanner = SystemScanner(local_path)
        self.__local_path = local_path
        if use_temp_file:
            self.__scanner.set_lftp_temp_suffix(Constants.LFTP_TEMP_FILE_SUFFIX)
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
        try:
            result = self.__scanner.scan()
        except SystemScannerError as e:
            self.logger.exception("Caught SystemScannerError")
            raise ScannerError(Localization.Error.LOCAL_SERVER_SCAN, recoverable=False) from e
        return result
