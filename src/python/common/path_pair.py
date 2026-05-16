# Copyright 2024, RapidCopy Contributors, All rights reserved.

"""
PathPair model and manager for multiple source/destination directory support.

This module provides:
- PathPair: A data class representing a remote->local path mapping
- PathPairManager: Handles CRUD operations and persistence for path pairs
"""

import json
import os
import shutil
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Tuple
from pathlib import Path

from .error import AppError
from .persist import Persist, PersistError


# Docker container expected base directory for downloads
DOCKER_DOWNLOADS_BASE = "/downloads"

# Docker container expected base directory for network mounts
DOCKER_MOUNTS_BASE = "/mounts"


class PathPairError(AppError):
    """Exception indicating a path pair error"""

    pass


def is_running_in_docker() -> bool:
    """
    Detect if we're running inside a Docker container.

    Returns:
        True if running in Docker, False otherwise
    """
    # Check for /.dockerenv file (most reliable)
    if os.path.exists("/.dockerenv"):
        return True

    # Check for docker in cgroup (fallback for some environments)
    try:
        with open("/proc/1/cgroup", "r") as f:
            return "docker" in f.read()
    except (FileNotFoundError, PermissionError):
        pass

    return False


@dataclass
class PathPair:
    """
    Represents a single source (remote) to destination (local) path mapping.

    Attributes:
        id: Unique identifier for this path pair
        name: Human-readable name for this path pair (e.g., "Movies", "TV Shows")
        remote_path: Path on the remote server to sync from
        local_path: Local path to sync to
        enabled: Whether this path pair is active
        auto_queue: Whether to auto-queue new files for this path pair
    """

    remote_path: str
    local_path: str
    name: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enabled: bool = True
    auto_queue: bool = True

    def __post_init__(self):
        # Generate a default name if not provided
        if not self.name:
            # Use the last directory component of remote_path as default name
            self.name = os.path.basename(self.remote_path.rstrip("/")) or "Default"

    def validate(self) -> List[str]:
        """
        Validate the path pair configuration.

        Returns:
            List of warning messages (empty if no warnings)

        Raises:
            PathPairError: If the path pair has invalid/missing required fields
        """
        if not self.remote_path or not self.remote_path.strip():
            raise PathPairError(f"Path pair '{self.name}': remote_path cannot be empty")
        if not self.local_path or not self.local_path.strip():
            raise PathPairError(f"Path pair '{self.name}': local_path cannot be empty")
        if not self.id:
            raise PathPairError(f"Path pair '{self.name}': id cannot be empty")

        warnings: List[str] = []

        # Docker-specific validation: warn if local_path is not under /downloads or /mounts
        if is_running_in_docker():
            local_path_normalized = os.path.normpath(self.local_path)
            downloads_base = os.path.normpath(DOCKER_DOWNLOADS_BASE)
            mounts_base = os.path.normpath(DOCKER_MOUNTS_BASE)

            # Check if local_path is a subdirectory of /downloads or /mounts
            is_under_downloads = local_path_normalized == downloads_base or local_path_normalized.startswith(
                downloads_base + os.sep
            )
            is_under_mounts = local_path_normalized == mounts_base or local_path_normalized.startswith(
                mounts_base + os.sep
            )

            if not is_under_downloads and not is_under_mounts:
                warnings.append(
                    f"Path pair '{self.name}': Local path '{self.local_path}' is not under "
                    f"'{DOCKER_DOWNLOADS_BASE}' or '{DOCKER_MOUNTS_BASE}'. In Docker, all local paths should be "
                    f"subdirectories of '{DOCKER_DOWNLOADS_BASE}' for local storage or "
                    f"'{DOCKER_MOUNTS_BASE}' for network mounts (e.g., "
                    f"'{DOCKER_DOWNLOADS_BASE}/movies' or '{DOCKER_MOUNTS_BASE}/nas/media')."
                )

        return warnings


@dataclass
class PathPairCollection:
    """
    Collection of path pairs with metadata.
    """

    path_pairs: list[PathPair] = field(default_factory=list)
    version: int = 1  # Schema version for future migrations

    def get_enabled_pairs(self) -> list[PathPair]:
        """Return only enabled path pairs."""
        return [p for p in self.path_pairs if p.enabled]

    def get_pair_by_id(self, pair_id: str) -> Optional[PathPair]:
        """Find a path pair by its ID."""
        for pair in self.path_pairs:
            if pair.id == pair_id:
                return pair
        return None

    def add_pair(self, pair: PathPair) -> List[str]:
        """
        Add a new path pair.

        Returns:
            List of warning messages from validation

        Raises:
            PathPairError: If validation fails or duplicate ID exists
        """
        warnings = pair.validate()
        # Check for duplicate IDs
        if self.get_pair_by_id(pair.id):
            raise PathPairError(f"Path pair with id '{pair.id}' already exists")
        self.path_pairs.append(pair)
        return warnings

    def update_pair(self, pair: PathPair) -> List[str]:
        """
        Update an existing path pair.

        Returns:
            List of warning messages from validation

        Raises:
            PathPairError: If validation fails or pair not found
        """
        warnings = pair.validate()
        for i, existing in enumerate(self.path_pairs):
            if existing.id == pair.id:
                self.path_pairs[i] = pair
                return warnings
        raise PathPairError(f"Path pair with id '{pair.id}' not found")

    def remove_pair(self, pair_id: str) -> None:
        """Remove a path pair by ID."""
        for i, pair in enumerate(self.path_pairs):
            if pair.id == pair_id:
                del self.path_pairs[i]
                return
        raise PathPairError(f"Path pair with id '{pair_id}' not found")

    def reorder_pairs(self, pair_ids: list[str]) -> None:
        """Reorder path pairs according to the given ID list."""
        if set(pair_ids) != {p.id for p in self.path_pairs}:
            raise PathPairError("Reorder list must contain all existing path pair IDs")

        id_to_pair = {p.id: p for p in self.path_pairs}
        self.path_pairs = [id_to_pair[pid] for pid in pair_ids]


class PathPairManager:
    """
    Manages persistence and operations for path pairs.

    Path pairs are stored in a JSON file separate from the main config.
    This allows for more flexible data structures and easier migration.
    """

    FILENAME = "path_pairs.json"

    def __init__(self, config_dir: str):
        """
        Initialize the PathPairManager.

        Args:
            config_dir: Directory where the path_pairs.json file is stored
        """
        self._config_dir = config_dir
        self._file_path = os.path.join(config_dir, self.FILENAME)
        self._collection: Optional[PathPairCollection] = None

    @property
    def file_path(self) -> str:
        """Return the full path to the path pairs file."""
        return self._file_path

    def load(self) -> PathPairCollection:
        """
        Load path pairs from the JSON file.
        Creates an empty collection if the file doesn't exist.
        """
        if not os.path.exists(self._file_path):
            self._collection = PathPairCollection()
            return self._collection

        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self._collection = PathPairManager.parse_collection(content)
            return self._collection
        except (IOError, json.JSONDecodeError) as e:
            raise PersistError(f"Failed to load path pairs: {e}") from e

    def save(self) -> None:
        """Save the current path pairs to the JSON file."""
        if self._collection is None:
            raise PathPairError("No path pair collection loaded")

        try:
            # Ensure directory exists
            os.makedirs(self._config_dir, exist_ok=True)

            # Backup before overwriting
            if os.path.isfile(self._file_path):
                backup_dir = os.path.join(self._config_dir, "backups")
                os.makedirs(backup_dir, exist_ok=True)
                file_name = os.path.basename(self._file_path)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(backup_dir, f"{file_name}.{timestamp}.bak")
                shutil.copy(self._file_path, backup_path)
                # Rotate: keep only the 10 most recent backups for this file
                prefix = file_name + "."
                existing = sorted(
                    [f for f in os.listdir(backup_dir) if f.startswith(prefix) and f.endswith(".bak")]
                )
                for old in existing[:-10]:
                    os.remove(os.path.join(backup_dir, old))

            content = self.to_str()
            with open(self._file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except IOError as e:
            raise PersistError(f"Failed to save path pairs: {e}") from e

    @property
    def collection(self) -> PathPairCollection:
        """Get the current collection, loading if necessary."""
        if self._collection is None:
            self._collection = self.load()
        return self._collection

    def get_all_pairs(self) -> list[PathPair]:
        """Get all path pairs."""
        return self.collection.path_pairs

    def get_enabled_pairs(self) -> list[PathPair]:
        """Get only enabled path pairs."""
        return self.collection.get_enabled_pairs()

    def get_pair_by_id(self, pair_id: str) -> Optional[PathPair]:
        """Get a path pair by ID."""
        return self.collection.get_pair_by_id(pair_id)

    def add_pair(self, pair: PathPair) -> None:
        """Add a new path pair and save."""
        self.collection.add_pair(pair)
        self.save()

    def update_pair(self, pair: PathPair) -> None:
        """Update an existing path pair and save."""
        self.collection.update_pair(pair)
        self.save()

    def remove_pair(self, pair_id: str) -> None:
        """Remove a path pair and save."""
        self.collection.remove_pair(pair_id)
        self.save()

    def reorder_pairs(self, pair_ids: list[str]) -> None:
        """Reorder path pairs and save."""
        self.collection.reorder_pairs(pair_ids)
        self.save()

    @classmethod
    def parse_collection(cls, content: str) -> "PathPairCollection":
        """
        Parse a JSON string into a PathPairCollection.
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise PersistError(f"Invalid JSON: {e}") from e

        version = data.get("version", 1)
        path_pairs_data = data.get("path_pairs", [])

        path_pairs = []
        for pair_data in path_pairs_data:
            try:
                pair = PathPair(
                    id=pair_data.get("id", str(uuid.uuid4())),
                    name=pair_data.get("name", ""),
                    remote_path=pair_data["remote_path"],
                    local_path=pair_data["local_path"],
                    enabled=pair_data.get("enabled", True),
                    auto_queue=pair_data.get("auto_queue", True),
                )
                path_pairs.append(pair)
            except KeyError as e:
                raise PersistError(f"Missing required field in path pair: {e}") from e

        return PathPairCollection(path_pairs=path_pairs, version=version)

    def to_str(self) -> str:
        """
        Serialize the PathPairCollection to a JSON string.
        """
        if self._collection is None:
            raise PathPairError("No path pair collection loaded")

        data = {
            "version": self._collection.version,
            "path_pairs": [asdict(pair) for pair in self._collection.path_pairs],
        }
        return json.dumps(data, indent=2)

    def migrate_from_config(self, remote_path: str, local_path: str) -> bool:
        """
        Migrate legacy single-path config to path pairs.

        If no path pairs exist and legacy paths are provided,
        creates a default path pair from the legacy config.

        Args:
            remote_path: Legacy remote_path from config
            local_path: Legacy local_path from config

        Returns:
            True if migration was performed, False otherwise
        """
        # Only migrate if we have no path pairs and valid legacy paths
        if self.collection.path_pairs:
            return False

        if not remote_path or not local_path:
            return False

        # Skip placeholder values
        if remote_path.startswith("<") or local_path.startswith("<"):
            return False

        # Create default path pair from legacy config
        default_pair = PathPair(
            name="Default",
            remote_path=remote_path,
            local_path=local_path,
            enabled=True,
            auto_queue=True,
        )

        self.collection.add_pair(default_pair)
        self.save()
        return True
