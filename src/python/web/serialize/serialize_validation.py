# Copyright 2024, RapidCopy Contributors, All rights reserved.

"""
Serialization for validation data.

Provides JSON serialization for validation status and configuration.
"""

import json
from typing import Any


class SerializeValidation:
    """
    Serializes validation-related data to JSON.
    """

    # Status keys
    __KEY_FILES = "files"
    __KEY_NAME = "name"
    __KEY_STATE = "state"
    __KEY_PROGRESS = "progress"
    __KEY_ERROR = "error"
    __KEY_CORRUPT_CHUNKS = "corrupt_chunks"

    # Config keys
    __KEY_VALIDATING_COUNT = "validating_count"
    __KEY_VALIDATED_COUNT = "validated_count"
    __KEY_CORRUPT_COUNT = "corrupt_count"

    @staticmethod
    def validation_status(file_statuses: list[dict[str, Any]]) -> str:
        """
        Serialize validation status for multiple files.

        Args:
            file_statuses: List of dicts with file validation info

        Returns:
            JSON string
        """
        json_dict: dict[str, Any] = {SerializeValidation.__KEY_FILES: []}

        for status in file_statuses:
            file_dict = {
                SerializeValidation.__KEY_NAME: status.get("name"),
                SerializeValidation.__KEY_STATE: status.get("state"),
                SerializeValidation.__KEY_PROGRESS: status.get("progress"),
                SerializeValidation.__KEY_ERROR: status.get("error"),
                SerializeValidation.__KEY_CORRUPT_CHUNKS: status.get("corrupt_chunks"),
            }
            json_dict[SerializeValidation.__KEY_FILES].append(file_dict)

        return json.dumps(json_dict)

    @staticmethod
    def validation_config(config_info: dict[str, Any]) -> str:
        """
        Serialize validation configuration/summary.

        Args:
            config_info: Dict with validation configuration info

        Returns:
            JSON string
        """
        json_dict: dict[str, Any] = {
            SerializeValidation.__KEY_VALIDATING_COUNT: config_info.get("validating_count", 0),
            SerializeValidation.__KEY_VALIDATED_COUNT: config_info.get("validated_count", 0),
            SerializeValidation.__KEY_CORRUPT_COUNT: config_info.get("corrupt_count", 0),
        }

        return json.dumps(json_dict)
