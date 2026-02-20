# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import json
from typing import List
import os
from typing import Optional
import hashlib

from .scanner_process import IScanner, ScannerError
from common import overrides, Localization
from ssh import Sshcp, SshcpError
from system import SystemFile


class RemoteScanner(IScanner):
    """
    Scanner implementation to scan the remote filesystem
    """

    def __init__(
        self,
        remote_address: str,
        remote_username: str,
        remote_password: str | None,
        remote_port: int,
        remote_path_to_scan: str,
        local_path_to_scan_script: str,
        remote_path_to_scan_script: str,
        path_pair_id: str | None = None,
        path_pair_name: str | None = None,
    ):
        self.logger = logging.getLogger("RemoteScanner")
        self.__remote_path_to_scan = remote_path_to_scan
        self.__local_path_to_scan_script = local_path_to_scan_script
        self.__remote_path_to_scan_script = remote_path_to_scan_script
        self.__ssh = Sshcp(host=remote_address, port=remote_port, user=remote_username, password=remote_password)
        self.__first_run = True
        self.__path_pair_id = path_pair_id
        self.__path_pair_name = path_pair_name

        # Append scan script name to remote path if not there already
        script_name = os.path.basename(self.__local_path_to_scan_script)
        if os.path.basename(self.__remote_path_to_scan_script) != script_name:
            self.__remote_path_to_scan_script = os.path.join(self.__remote_path_to_scan_script, script_name)

    @property
    def path_pair_id(self) -> str | None:
        return self.__path_pair_id

    @property
    def path_pair_name(self) -> str | None:
        return self.__path_pair_name

    @property
    def remote_path(self) -> str:
        return self.__remote_path_to_scan

    @overrides(IScanner)
    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild("RemoteScanner")
        self.__ssh.set_base_logger(self.logger)

    @overrides(IScanner)
    def scan(self) -> List[SystemFile]:
        if self.__first_run:
            self._install_scanfs()

        try:
            out = self.__ssh.shell("'{}' '{}'".format(self.__remote_path_to_scan_script, self.__remote_path_to_scan))
        except SshcpError as e:
            self.logger.warning("Caught an SshcpError: {}".format(str(e)))
            recoverable = True
            # Any scanner errors are fatal
            if "SystemScannerError" in str(e):
                recoverable = False
            # First time errors are fatal
            # User should be prompted to correct these
            if self.__first_run:
                recoverable = False
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_SCAN.format(str(e).strip()), recoverable=recoverable
            ) from e

        try:
            # SECURITY: Use JSON instead of pickle to prevent RCE attacks
            # The remote scanner script must output JSON-formatted data
            remote_files = self._parse_scan_output(out)
        except (json.JSONDecodeError, KeyError, TypeError) as err:
            self.logger.error("JSON parsing error: {}\n{}".format(str(err), out.decode("utf-8", "replace")))
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_SCAN.format("Invalid scan data format"), recoverable=False
            ) from err

        self.__first_run = False
        return remote_files

    def _install_scanfs(self):
        # Check md5sum on remote to see if we can skip installation
        with open(self.__local_path_to_scan_script, "rb") as f:
            local_md5sum = hashlib.md5(f.read()).hexdigest()
        self.logger.debug("Local scanfs md5sum = {}".format(local_md5sum))
        try:
            out = self.__ssh.shell("md5sum {} | awk '{{print $1}}' || echo".format(self.__remote_path_to_scan_script))
            out = out.decode()
            if out == local_md5sum:
                self.logger.info("Skipping remote scanfs installation: already installed")
                return
        except SshcpError as e:
            self.logger.exception("Caught scp exception")
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_INSTALL.format(str(e).strip()), recoverable=False
            ) from e

        # Go ahead and install
        self.logger.info(
            "Installing local:{} to remote:{}".format(
                self.__local_path_to_scan_script, self.__remote_path_to_scan_script
            )
        )
        if not os.path.isfile(self.__local_path_to_scan_script):
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_SCAN.format(
                    "Failed to find scanfs executable at {}".format(self.__local_path_to_scan_script)
                ),
                recoverable=False,
            )
        try:
            self.__ssh.copy(local_path=self.__local_path_to_scan_script, remote_path=self.__remote_path_to_scan_script)
        except SshcpError as e:
            self.logger.exception("Caught scp exception")
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_INSTALL.format(str(e).strip()), recoverable=False
            ) from e

    def _parse_scan_output(self, out: bytes) -> List[SystemFile]:
        """
        Parse scan output and convert to SystemFile objects.

        JSON is the only supported format. Pickle support was removed due to
        Remote Code Execution (RCE) risk - pickle can deserialize arbitrary Python
        objects, enabling RCE if an attacker controls the remote server.

        Expected JSON format:
        [
            {
                "name": "filename",
                "size": 1234,
                "is_dir": false,
                "timestamp_created": 1234567890.0,  // optional, Unix timestamp
                "timestamp_modified": 1234567890.0,  // optional, Unix timestamp
                "children": []  // optional, for directories
            },
            ...
        ]
        """
        from datetime import datetime

        # JSON is the only supported format - pickle was removed for security (RCE risk)
        try:
            data = json.loads(out.decode("utf-8"))
            return self._parse_json_files(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        # Pickle support removed - JSON is required. Update scanfs binary if needed.
        raise json.JSONDecodeError("Scan output is not valid JSON. Ensure scanfs binary is up to date.", "", 0)

    def _parse_json_files(self, data: list) -> List[SystemFile]:
        """Parse JSON file data into SystemFile objects."""
        from datetime import datetime

        def _parse_file(file_dict: dict) -> SystemFile:
            """Recursively parse a file dictionary into a SystemFile object."""
            name = file_dict["name"]
            size = file_dict["size"]
            is_dir = file_dict.get("is_dir", False)

            # Parse timestamps (optional)
            time_created = None
            time_modified = None
            if "timestamp_created" in file_dict and file_dict["timestamp_created"] is not None:
                time_created = datetime.fromtimestamp(file_dict["timestamp_created"])
            if "timestamp_modified" in file_dict and file_dict["timestamp_modified"] is not None:
                time_modified = datetime.fromtimestamp(file_dict["timestamp_modified"])

            system_file = SystemFile(
                name=name, size=size, is_dir=is_dir, time_created=time_created, time_modified=time_modified
            )

            # Parse children for directories
            if is_dir and "children" in file_dict:
                for child_dict in file_dict["children"]:
                    child_file = _parse_file(child_dict)
                    system_file.add_child(child_file)

            return system_file

        return [_parse_file(f) for f in data]
