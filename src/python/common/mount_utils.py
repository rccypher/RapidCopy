# Copyright 2025, RapidCopy Contributors, All rights reserved.

"""
Mount utilities for network share operations.

This module provides:
- Password encryption/decryption using Fernet
- Mount/unmount operations for NFS and CIFS
- Mount status checking
- Connection testing
"""

import os
import subprocess
import socket
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Cryptography for password encryption
try:
    from cryptography.fernet import Fernet

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from .network_mount import NetworkMount, MountType, MountStatus, NetworkMountError, MOUNTS_BASE_DIR


# Key file location
MOUNT_KEY_FILENAME = ".mount_key"


class MountResult(Enum):
    """Result of a mount/unmount operation"""

    SUCCESS = "success"
    ALREADY_MOUNTED = "already_mounted"
    ALREADY_UNMOUNTED = "already_unmounted"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class MountOperationResult:
    """Result of a mount operation with details"""

    result: MountResult
    message: str
    exit_code: int = 0


def get_key_file_path(config_dir: str) -> str:
    """Get the path to the encryption key file."""
    return os.path.join(config_dir, MOUNT_KEY_FILENAME)


def generate_or_load_key(config_dir: str) -> bytes:
    """
    Generate a new encryption key or load existing one.

    Args:
        config_dir: Directory where the key file is stored

    Returns:
        The encryption key bytes

    Raises:
        NetworkMountError: If cryptography is not available or key operations fail
    """
    if not CRYPTO_AVAILABLE:
        raise NetworkMountError("cryptography package is required for password encryption")

    key_path = get_key_file_path(config_dir)

    if os.path.exists(key_path):
        try:
            with open(key_path, "rb") as f:
                return f.read()
        except IOError as e:
            raise NetworkMountError(f"Failed to read encryption key: {e}") from e
    else:
        # Generate new key
        key = Fernet.generate_key()
        try:
            # Ensure directory exists
            os.makedirs(config_dir, exist_ok=True)
            # Write key with restricted permissions
            with open(key_path, "wb") as f:
                f.write(key)
            os.chmod(key_path, 0o600)
            return key
        except IOError as e:
            raise NetworkMountError(f"Failed to write encryption key: {e}") from e


def encrypt_password(password: str, config_dir: str) -> str:
    """
    Encrypt a password using Fernet encryption.

    Args:
        password: Plain text password
        config_dir: Directory where the key file is stored

    Returns:
        Base64-encoded encrypted password
    """
    if not password:
        return ""

    if not CRYPTO_AVAILABLE:
        raise NetworkMountError("cryptography package is required for password encryption")

    key = generate_or_load_key(config_dir)
    fernet = Fernet(key)
    encrypted = fernet.encrypt(password.encode())
    return encrypted.decode()


def decrypt_password(encrypted_password: str, config_dir: str) -> str:
    """
    Decrypt a password.

    Args:
        encrypted_password: Base64-encoded encrypted password
        config_dir: Directory where the key file is stored

    Returns:
        Decrypted plain text password
    """
    if not encrypted_password:
        return ""

    if not CRYPTO_AVAILABLE:
        raise NetworkMountError("cryptography package is required for password encryption")

    key = generate_or_load_key(config_dir)
    fernet = Fernet(key)
    try:
        decrypted = fernet.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception as e:
        raise NetworkMountError(f"Failed to decrypt password: {e}") from e


def is_mounted(mount_point: str) -> bool:
    """
    Check if a path is a mount point.

    Args:
        mount_point: Path to check

    Returns:
        True if the path is mounted, False otherwise
    """
    if not os.path.exists(mount_point):
        return False

    try:
        result = subprocess.run(["mountpoint", "-q", mount_point], capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # Fallback: check /proc/mounts
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == mount_point:
                        return True
        except IOError:
            pass
        return False


def get_mount_status(mount: NetworkMount) -> Tuple[MountStatus, str]:
    """
    Get the current status of a mount.

    Args:
        mount: NetworkMount configuration

    Returns:
        Tuple of (MountStatus, status message)
    """
    mount_point = mount.mount_point

    if not os.path.exists(mount_point):
        return MountStatus.UNMOUNTED, "Mount point does not exist"

    if is_mounted(mount_point):
        # Check if we can access it
        try:
            os.listdir(mount_point)
            return MountStatus.MOUNTED, "Mounted and accessible"
        except PermissionError:
            return MountStatus.MOUNTED, "Mounted but permission denied"
        except OSError as e:
            return MountStatus.ERROR, f"Mounted but error accessing: {e}"
    else:
        return MountStatus.UNMOUNTED, "Not mounted"


def ensure_mount_point(mount_point: str) -> None:
    """
    Ensure the mount point directory exists.

    Args:
        mount_point: Path to the mount point

    Raises:
        NetworkMountError: If directory creation fails
    """
    if not os.path.exists(mount_point):
        try:
            os.makedirs(mount_point, mode=0o755, exist_ok=True)
        except OSError as e:
            raise NetworkMountError(f"Failed to create mount point: {e}") from e


def mount_nfs(mount: NetworkMount, logger: Optional[logging.Logger] = None) -> MountOperationResult:
    """
    Mount an NFS share.

    Args:
        mount: NetworkMount configuration
        logger: Optional logger for debug output

    Returns:
        MountOperationResult with status and message
    """
    mount_point = mount.mount_point
    source = mount.mount_source

    # Check if already mounted
    if is_mounted(mount_point):
        return MountOperationResult(MountResult.ALREADY_MOUNTED, "Already mounted")

    # Ensure mount point exists
    try:
        ensure_mount_point(mount_point)
    except NetworkMountError as e:
        return MountOperationResult(MountResult.ERROR, str(e))

    # Build mount command
    cmd = ["mount", "-t", "nfs"]
    if mount.mount_options:
        cmd.extend(["-o", mount.mount_options])
    cmd.extend([source, mount_point])

    if logger:
        logger.debug(f"Mounting NFS: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            return MountOperationResult(MountResult.SUCCESS, "Mount successful", 0)
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            if "permission denied" in error_msg.lower():
                return MountOperationResult(MountResult.PERMISSION_DENIED, error_msg, result.returncode)
            elif "no such file" in error_msg.lower() or "not found" in error_msg.lower():
                return MountOperationResult(MountResult.NOT_FOUND, error_msg, result.returncode)
            else:
                return MountOperationResult(MountResult.ERROR, error_msg, result.returncode)

    except subprocess.TimeoutExpired:
        return MountOperationResult(MountResult.TIMEOUT, "Mount operation timed out")
    except Exception as e:
        return MountOperationResult(MountResult.ERROR, str(e))


def mount_cifs(
    mount: NetworkMount, decrypted_password: str, logger: Optional[logging.Logger] = None
) -> MountOperationResult:
    """
    Mount a CIFS/SMB share.

    Args:
        mount: NetworkMount configuration
        decrypted_password: Decrypted password (empty string for anonymous)
        logger: Optional logger for debug output

    Returns:
        MountOperationResult with status and message
    """
    mount_point = mount.mount_point
    source = mount.mount_source

    # Check if already mounted
    if is_mounted(mount_point):
        return MountOperationResult(MountResult.ALREADY_MOUNTED, "Already mounted")

    # Ensure mount point exists
    try:
        ensure_mount_point(mount_point)
    except NetworkMountError as e:
        return MountOperationResult(MountResult.ERROR, str(e))

    # Build mount options
    options = []

    if mount.username:
        options.append(f"username={mount.username}")
        if decrypted_password:
            options.append(f"password={decrypted_password}")
        if mount.domain:
            options.append(f"domain={mount.domain}")
    else:
        options.append("guest")

    # Add user-specified options
    if mount.mount_options:
        options.append(mount.mount_options)

    # Build mount command
    cmd = ["mount", "-t", "cifs"]
    if options:
        cmd.extend(["-o", ",".join(options)])
    cmd.extend([source, mount_point])

    if logger:
        # Log without password
        safe_cmd = cmd.copy()
        for i, arg in enumerate(safe_cmd):
            if "password=" in arg:
                safe_cmd[i] = arg.split("password=")[0] + "password=***"
        logger.debug(f"Mounting CIFS: {' '.join(safe_cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            return MountOperationResult(MountResult.SUCCESS, "Mount successful", 0)
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            if "permission denied" in error_msg.lower() or "access denied" in error_msg.lower():
                return MountOperationResult(MountResult.PERMISSION_DENIED, error_msg, result.returncode)
            elif "no such file" in error_msg.lower() or "not found" in error_msg.lower():
                return MountOperationResult(MountResult.NOT_FOUND, error_msg, result.returncode)
            else:
                return MountOperationResult(MountResult.ERROR, error_msg, result.returncode)

    except subprocess.TimeoutExpired:
        return MountOperationResult(MountResult.TIMEOUT, "Mount operation timed out")
    except Exception as e:
        return MountOperationResult(MountResult.ERROR, str(e))


def mount_local(mount: NetworkMount, logger: Optional[logging.Logger] = None) -> MountOperationResult:
    """
    Create a bind mount for a local path.

    Args:
        mount: NetworkMount configuration
        logger: Optional logger for debug output

    Returns:
        MountOperationResult with status and message
    """
    mount_point = mount.mount_point
    source = mount.share_path

    # Check if already mounted
    if is_mounted(mount_point):
        return MountOperationResult(MountResult.ALREADY_MOUNTED, "Already mounted")

    # Check if source exists
    if not os.path.exists(source):
        return MountOperationResult(MountResult.NOT_FOUND, f"Source path does not exist: {source}")

    # Ensure mount point exists
    try:
        ensure_mount_point(mount_point)
    except NetworkMountError as e:
        return MountOperationResult(MountResult.ERROR, str(e))

    # Build mount command
    cmd = ["mount", "--bind"]
    if mount.mount_options:
        cmd.extend(["-o", mount.mount_options])
    cmd.extend([source, mount_point])

    if logger:
        logger.debug(f"Mounting bind: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            return MountOperationResult(MountResult.SUCCESS, "Mount successful", 0)
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            return MountOperationResult(MountResult.ERROR, error_msg, result.returncode)

    except subprocess.TimeoutExpired:
        return MountOperationResult(MountResult.TIMEOUT, "Mount operation timed out")
    except Exception as e:
        return MountOperationResult(MountResult.ERROR, str(e))


def do_mount(mount: NetworkMount, config_dir: str, logger: Optional[logging.Logger] = None) -> MountOperationResult:
    """
    Mount a network share based on its type.

    Args:
        mount: NetworkMount configuration
        config_dir: Config directory for password decryption
        logger: Optional logger for debug output

    Returns:
        MountOperationResult with status and message
    """
    if mount.mount_type == MountType.NFS.value:
        return mount_nfs(mount, logger)
    elif mount.mount_type == MountType.CIFS.value:
        decrypted_password = ""
        if mount.password:
            try:
                decrypted_password = decrypt_password(mount.password, config_dir)
            except NetworkMountError as e:
                return MountOperationResult(MountResult.ERROR, f"Failed to decrypt password: {e}")
        return mount_cifs(mount, decrypted_password, logger)
    elif mount.mount_type == MountType.LOCAL.value:
        return mount_local(mount, logger)
    else:
        return MountOperationResult(MountResult.ERROR, f"Unknown mount type: {mount.mount_type}")


def do_unmount(
    mount: NetworkMount, logger: Optional[logging.Logger] = None, force: bool = False
) -> MountOperationResult:
    """
    Unmount a network share.

    Args:
        mount: NetworkMount configuration
        logger: Optional logger for debug output
        force: Force unmount even if busy

    Returns:
        MountOperationResult with status and message
    """
    mount_point = mount.mount_point

    # Check if mounted
    if not is_mounted(mount_point):
        return MountOperationResult(MountResult.ALREADY_UNMOUNTED, "Not mounted")

    # Build unmount command
    cmd = ["umount"]
    if force:
        cmd.append("-f")
    cmd.append(mount_point)

    if logger:
        logger.debug(f"Unmounting: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            return MountOperationResult(MountResult.SUCCESS, "Unmount successful", 0)
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            if "busy" in error_msg.lower():
                return MountOperationResult(
                    MountResult.ERROR, "Device is busy. Close any open files and try again.", result.returncode
                )
            else:
                return MountOperationResult(MountResult.ERROR, error_msg, result.returncode)

    except subprocess.TimeoutExpired:
        return MountOperationResult(MountResult.TIMEOUT, "Unmount operation timed out")
    except Exception as e:
        return MountOperationResult(MountResult.ERROR, str(e))


def test_connection(mount: NetworkMount, timeout: int = 5) -> Tuple[bool, str]:
    """
    Test network connectivity to a mount server.

    Args:
        mount: NetworkMount configuration
        timeout: Connection timeout in seconds

    Returns:
        Tuple of (success, message)
    """
    if mount.mount_type == MountType.LOCAL.value:
        # For local mounts, just check if the path exists
        if os.path.exists(mount.share_path):
            return True, "Local path exists"
        else:
            return False, f"Local path does not exist: {mount.share_path}"

    server = mount.server
    if not server:
        return False, "No server specified"

    # Determine port based on mount type
    if mount.mount_type == MountType.NFS.value:
        port = 2049  # NFS default port
    elif mount.mount_type == MountType.CIFS.value:
        port = 445  # SMB default port
    else:
        return False, f"Unknown mount type: {mount.mount_type}"

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((server, port))
        sock.close()

        if result == 0:
            return True, f"Successfully connected to {server}:{port}"
        else:
            return False, f"Could not connect to {server}:{port}"

    except socket.gaierror:
        return False, f"Could not resolve hostname: {server}"
    except socket.timeout:
        return False, f"Connection to {server}:{port} timed out"
    except Exception as e:
        return False, f"Connection error: {e}"
