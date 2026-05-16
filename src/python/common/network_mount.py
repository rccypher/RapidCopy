# Copyright 2025, RapidCopy Contributors, All rights reserved.

"""
NetworkMount model and manager for network share mounting support.

This module provides:
- NetworkMount: A data class representing a network mount configuration
- NetworkMountCollection: Collection of network mounts with metadata
- NetworkMountManager: Handles CRUD operations and persistence for network mounts
"""

import json
import os
import uuid
import re
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from enum import Enum

from .error import AppError
from .persist import Persist, PersistError


# Mount point base directory inside the container
MOUNTS_BASE_DIR = "/mounts"


class NetworkMountError(AppError):
    """Exception indicating a network mount error"""

    pass


class MountType(str, Enum):
    """Supported mount types"""

    NFS = "nfs"
    CIFS = "cifs"
    LOCAL = "local"


class MountStatus(str, Enum):
    """Mount status values"""

    MOUNTED = "mounted"
    UNMOUNTED = "unmounted"
    ERROR = "error"
    UNKNOWN = "unknown"


def sanitize_mount_id(name: str) -> str:
    """
    Generate a filesystem-safe ID from a name.

    Args:
        name: Human-readable name

    Returns:
        Sanitized string safe for use as a directory name
    """
    # Convert to lowercase, replace spaces with hyphens
    safe_name = name.lower().strip()
    safe_name = re.sub(r"\s+", "-", safe_name)
    # Remove any characters that aren't alphanumeric, hyphen, or underscore
    safe_name = re.sub(r"[^a-z0-9\-_]", "", safe_name)
    # Ensure it doesn't start with a hyphen or underscore
    safe_name = safe_name.lstrip("-_")
    # If empty after sanitization, use a UUID
    if not safe_name:
        safe_name = str(uuid.uuid4())[:8]
    return safe_name


@dataclass
class NetworkMount:
    """
    Represents a network mount configuration.

    Attributes:
        id: Unique identifier (also used as mount point name)
        name: Human-readable name for this mount (e.g., "NAS Movies")
        mount_type: Type of mount (nfs, cifs, local)
        enabled: Whether to auto-mount on startup
        server: Server address (e.g., "192.168.1.100")
        share_path: Remote share path (e.g., "/volume1/media" for NFS, "media_share" for CIFS)
        username: Username for CIFS authentication (optional)
        password: Encrypted password for CIFS authentication (optional)
        domain: Domain for CIFS authentication (optional)
        mount_options: Additional mount options (e.g., "vers=3.0,uid=1000")
    """

    name: str
    mount_type: str  # "nfs", "cifs", or "local"
    server: str = ""
    share_path: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    enabled: bool = True
    username: Optional[str] = None
    password: Optional[str] = None  # Stored encrypted
    domain: Optional[str] = None
    mount_options: str = ""

    def __post_init__(self):
        # Normalize mount_type to lowercase
        self.mount_type = self.mount_type.lower()

        # Generate ID from name if not provided or if it's a full UUID
        if not self.id or len(self.id) > 16:
            self.id = sanitize_mount_id(self.name)

    @property
    def mount_point(self) -> str:
        """Return the full mount point path."""
        return os.path.join(MOUNTS_BASE_DIR, self.id)

    @property
    def mount_source(self) -> str:
        """Return the mount source string based on mount type."""
        if self.mount_type == MountType.NFS.value:
            return f"{self.server}:{self.share_path}"
        elif self.mount_type == MountType.CIFS.value:
            return f"//{self.server}/{self.share_path}"
        elif self.mount_type == MountType.LOCAL.value:
            return self.share_path
        else:
            return ""

    def validate(self) -> List[str]:
        """
        Validate the network mount configuration.

        Returns:
            List of warning messages (empty if no warnings)

        Raises:
            NetworkMountError: If the mount has invalid/missing required fields
        """
        if not self.name or not self.name.strip():
            raise NetworkMountError("Mount name cannot be empty")
        if not self.id:
            raise NetworkMountError("Mount ID cannot be empty")
        if self.mount_type not in [t.value for t in MountType]:
            raise NetworkMountError(
                f"Invalid mount type '{self.mount_type}'. Must be one of: {', '.join(t.value for t in MountType)}"
            )

        # Type-specific validation
        if self.mount_type in [MountType.NFS.value, MountType.CIFS.value]:
            if not self.server or not self.server.strip():
                raise NetworkMountError(f"Server address is required for {self.mount_type.upper()} mounts")
            if not self.share_path or not self.share_path.strip():
                raise NetworkMountError(f"Share path is required for {self.mount_type.upper()} mounts")

        if self.mount_type == MountType.LOCAL.value:
            if not self.share_path or not self.share_path.strip():
                raise NetworkMountError("Local path is required for local mounts")
            if not os.path.isabs(self.share_path):
                raise NetworkMountError("Local path must be an absolute path")

        warnings: List[str] = []

        # Warn about missing credentials for CIFS
        if self.mount_type == MountType.CIFS.value:
            if not self.username:
                warnings.append(f"Mount '{self.name}': No username specified. Anonymous access will be attempted.")

        return warnings

    def to_dict_safe(self) -> dict:
        """
        Return a dictionary representation safe for API responses.
        Excludes the password field.
        """
        data = asdict(self)
        # Don't expose the encrypted password in API responses
        data["password"] = "***" if self.password else None
        # Add computed fields
        data["mount_point"] = self.mount_point
        data["mount_source"] = self.mount_source
        return data


@dataclass
class NetworkMountCollection:
    """
    Collection of network mounts with metadata.
    """

    mounts: list[NetworkMount] = field(default_factory=list)
    version: int = 1  # Schema version for future migrations

    def get_enabled_mounts(self) -> list[NetworkMount]:
        """Return only enabled mounts."""
        return [m for m in self.mounts if m.enabled]

    def get_mount_by_id(self, mount_id: str) -> Optional[NetworkMount]:
        """Find a mount by its ID."""
        for mount in self.mounts:
            if mount.id == mount_id:
                return mount
        return None

    def add_mount(self, mount: NetworkMount) -> List[str]:
        """
        Add a new mount.

        Returns:
            List of warning messages from validation

        Raises:
            NetworkMountError: If validation fails or duplicate ID exists
        """
        warnings = mount.validate()
        # Check for duplicate IDs
        if self.get_mount_by_id(mount.id):
            raise NetworkMountError(f"Mount with id '{mount.id}' already exists")
        self.mounts.append(mount)
        return warnings

    def update_mount(self, mount: NetworkMount) -> List[str]:
        """
        Update an existing mount.

        Returns:
            List of warning messages from validation

        Raises:
            NetworkMountError: If validation fails or mount not found
        """
        warnings = mount.validate()
        for i, existing in enumerate(self.mounts):
            if existing.id == mount.id:
                self.mounts[i] = mount
                return warnings
        raise NetworkMountError(f"Mount with id '{mount.id}' not found")

    def remove_mount(self, mount_id: str) -> None:
        """Remove a mount by ID."""
        for i, mount in enumerate(self.mounts):
            if mount.id == mount_id:
                del self.mounts[i]
                return
        raise NetworkMountError(f"Mount with id '{mount_id}' not found")


class NetworkMountManager:
    """
    Manages persistence and operations for network mounts.

    Network mounts are stored in a JSON file separate from the main config.
    """

    FILENAME = "network_mounts.json"

    def __init__(self, config_dir: str):
        """
        Initialize the NetworkMountManager.

        Args:
            config_dir: Directory where the network_mounts.json file is stored
        """
        self._config_dir = config_dir
        self._file_path = os.path.join(config_dir, self.FILENAME)
        self._collection: Optional[NetworkMountCollection] = None

    @property
    def file_path(self) -> str:
        """Return the full path to the mounts file."""
        return self._file_path

    @property
    def config_dir(self) -> str:
        """Return the config directory."""
        return self._config_dir

    def load(self) -> NetworkMountCollection:
        """
        Load mounts from the JSON file.
        Creates an empty collection if the file doesn't exist.
        """
        if not os.path.exists(self._file_path):
            self._collection = NetworkMountCollection()
            return self._collection

        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self._collection = NetworkMountManager.parse_collection(content)
            return self._collection
        except (IOError, json.JSONDecodeError) as e:
            raise PersistError(f"Failed to load network mounts: {e}") from e

    def save(self) -> None:
        """Save the current mounts to the JSON file."""
        if self._collection is None:
            raise NetworkMountError("No mount collection loaded")

        try:
            # Ensure directory exists
            os.makedirs(self._config_dir, exist_ok=True)

            content = self.to_str()
            with open(self._file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except IOError as e:
            raise PersistError(f"Failed to save network mounts: {e}") from e

    @property
    def collection(self) -> NetworkMountCollection:
        """Get the current collection, loading if necessary."""
        if self._collection is None:
            self._collection = self.load()
        return self._collection

    def get_all_mounts(self) -> list[NetworkMount]:
        """Get all mounts."""
        return self.collection.mounts

    def get_enabled_mounts(self) -> list[NetworkMount]:
        """Get only enabled mounts."""
        return self.collection.get_enabled_mounts()

    def get_mount_by_id(self, mount_id: str) -> Optional[NetworkMount]:
        """Get a mount by ID."""
        return self.collection.get_mount_by_id(mount_id)

    def add_mount(self, mount: NetworkMount) -> List[str]:
        """Add a new mount and save."""
        warnings = self.collection.add_mount(mount)
        self.save()
        return warnings

    def update_mount(self, mount: NetworkMount) -> List[str]:
        """Update an existing mount and save."""
        warnings = self.collection.update_mount(mount)
        self.save()
        return warnings

    def remove_mount(self, mount_id: str) -> None:
        """Remove a mount and save."""
        self.collection.remove_mount(mount_id)
        self.save()

    @classmethod
    def parse_collection(cls, content: str) -> NetworkMountCollection:
        """
        Parse a JSON string into a NetworkMountCollection.
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise PersistError(f"Invalid JSON: {e}") from e

        version = data.get("version", 1)
        mounts_data = data.get("mounts", [])

        mounts = []
        for mount_data in mounts_data:
            try:
                mount = NetworkMount(
                    id=mount_data.get("id", str(uuid.uuid4())[:8]),
                    name=mount_data["name"],
                    mount_type=mount_data["mount_type"],
                    enabled=mount_data.get("enabled", True),
                    server=mount_data.get("server", ""),
                    share_path=mount_data.get("share_path", ""),
                    username=mount_data.get("username"),
                    password=mount_data.get("password"),
                    domain=mount_data.get("domain"),
                    mount_options=mount_data.get("mount_options", ""),
                )
                mounts.append(mount)
            except KeyError as e:
                raise PersistError(f"Missing required field in mount: {e}") from e

        return NetworkMountCollection(mounts=mounts, version=version)

    def to_str(self) -> str:
        """
        Serialize the NetworkMountCollection to a JSON string.
        """
        if self._collection is None:
            raise NetworkMountError("No mount collection loaded")

        data = {
            "version": self._collection.version,
            "mounts": [asdict(mount) for mount in self._collection.mounts],
        }
        return json.dumps(data, indent=2)
