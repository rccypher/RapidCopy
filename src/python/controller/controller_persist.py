# Copyright 2017, Inderpreet Singh, All rights reserved.

import json

from common import overrides, Constants, Persist, PersistError


class ControllerPersist(Persist):
    """
    Persisting state for controller
    """

    # Keys
    __KEY_DOWNLOADED_FILE_NAMES = "downloaded"
    __KEY_EXTRACTED_FILE_NAMES = "extracted"
    __KEY_VALIDATION_RETRY_COUNTS = "validation_retry_counts"
    __KEY_VALIDATED_FILE_NAMES = "validated"

    def __init__(self):
        self.downloaded_file_names = set()
        self.extracted_file_names = set()
        # Maps file_name -> number of validation retries attempted
        self.validation_retry_counts = dict()
        # Set of file names that have passed validation
        self.validated_file_names = set()

    @classmethod
    @overrides(Persist)
    def from_str(cls: "ControllerPersist", content: str) -> "ControllerPersist":
        persist = ControllerPersist()
        try:
            dct = json.loads(content)
            persist.downloaded_file_names = set(dct[ControllerPersist.__KEY_DOWNLOADED_FILE_NAMES])
            persist.extracted_file_names = set(dct[ControllerPersist.__KEY_EXTRACTED_FILE_NAMES])
            persist.validation_retry_counts = dict(
                dct.get(ControllerPersist.__KEY_VALIDATION_RETRY_COUNTS, {})
            )
            persist.validated_file_names = set(
                dct.get(ControllerPersist.__KEY_VALIDATED_FILE_NAMES, [])
            )
            return persist
        except (json.decoder.JSONDecodeError, KeyError) as e:
            raise PersistError("Error parsing ControllerPersist - {}: {}".format(
                type(e).__name__, str(e))
            )

    @overrides(Persist)
    def to_str(self) -> str:
        dct = dict()
        dct[ControllerPersist.__KEY_DOWNLOADED_FILE_NAMES] = list(self.downloaded_file_names)
        dct[ControllerPersist.__KEY_EXTRACTED_FILE_NAMES] = list(self.extracted_file_names)
        dct[ControllerPersist.__KEY_VALIDATION_RETRY_COUNTS] = self.validation_retry_counts
        dct[ControllerPersist.__KEY_VALIDATED_FILE_NAMES] = list(self.validated_file_names)
        return json.dumps(dct, indent=Constants.JSON_PRETTY_PRINT_INDENT)
