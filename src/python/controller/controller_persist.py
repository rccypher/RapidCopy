# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
from typing import Any
from datetime import datetime

from common import overrides, Constants, Persist, PersistError


class ControllerPersist(Persist):
    """
    Persisting state for controller
    """

    # Keys
    __KEY_DOWNLOADED_TIMESTAMPS = "downloaded_timestamps"
    __KEY_EXTRACTED_FILE_NAMES = "extracted"

    def __init__(self):
        # Maps filename -> ISO-format download timestamp string
        self.downloaded_file_timestamps: dict[str, str] = {}
        self.extracted_file_names = set()

    @property
    def downloaded_file_names(self) -> set:
        """Derived set of downloaded file names (for backward-compat read access)."""
        return set(self.downloaded_file_timestamps.keys())

    def record_download(self, name: str):
        """Record that a file was downloaded now (or update timestamp if already present)."""
        self.downloaded_file_timestamps[name] = datetime.now().isoformat()

    def remove_download(self, name: str):
        """Remove a file from the downloaded tracking set."""
        self.downloaded_file_timestamps.pop(name, None)

    @classmethod
    @overrides(Persist)
    def from_str(cls: "ControllerPersist", content: str) -> "ControllerPersist":
        persist = ControllerPersist()
        try:
            dct = json.loads(content)

            # Load timestamps dict (new format)
            if ControllerPersist.__KEY_DOWNLOADED_TIMESTAMPS in dct:
                persist.downloaded_file_timestamps = dict(
                    dct[ControllerPersist.__KEY_DOWNLOADED_TIMESTAMPS]
                )
            else:
                # Backward compat: old format stored a plain list under "downloaded"
                old_names = set(dct.get("downloaded", []))
                # Seed with current time so they start their age-off clock now
                now = datetime.now().isoformat()
                persist.downloaded_file_timestamps = {name: now for name in old_names}

            persist.extracted_file_names = set(dct[ControllerPersist.__KEY_EXTRACTED_FILE_NAMES])
            return persist
        except (json.decoder.JSONDecodeError, KeyError) as e:
            raise PersistError("Error parsing ControllerPersist - {}: {}".format(type(e).__name__, str(e))) from e

    @overrides(Persist)
    def to_str(self) -> str:
        dct: dict[str, Any] = {}
        dct[ControllerPersist.__KEY_DOWNLOADED_TIMESTAMPS] = self.downloaded_file_timestamps
        dct[ControllerPersist.__KEY_EXTRACTED_FILE_NAMES] = list(self.extracted_file_names)
        return json.dumps(dct, indent=Constants.JSON_PRETTY_PRINT_INDENT)
