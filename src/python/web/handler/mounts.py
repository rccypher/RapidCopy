# Copyright 2025, RapidCopy Contributors, All rights reserved.

"""
REST API handler for network mount management.

Endpoints:
    GET    /server/mounts           - List all mounts with status
    GET    /server/mounts/:id       - Get a specific mount
    POST   /server/mounts           - Create a new mount
    PUT    /server/mounts/:id       - Update a mount
    DELETE /server/mounts/:id       - Delete a mount
    POST   /server/mounts/:id/mount - Mount the share
    POST   /server/mounts/:id/unmount - Unmount the share
    GET    /server/mounts/:id/test  - Test connection to the share
"""

import json
import logging

import bottle

from common import (
    NetworkMountManager,
    NetworkMount,
    NetworkMountError,
    PersistError,
)
from common.mount_utils import (
    do_mount,
    do_unmount,
    get_mount_status,
    test_connection,
    encrypt_password,
    MountResult,
)
from common.network_mount import MountStatus
from web.web_app import IHandler, WebApp


class MountsHandler(IHandler):
    """
    Handler for network mount CRUD and mount/unmount operations.
    """

    def __init__(self, mount_manager: NetworkMountManager, logger: logging.Logger):
        self._manager = mount_manager
        self._logger = logger

    def add_routes(self, web_app: WebApp):
        web_app.get("/server/mounts")(self._get_all)
        web_app.get("/server/mounts/<mount_id>")(self._get_one)
        web_app.post("/server/mounts")(self._create)
        web_app.put("/server/mounts/<mount_id>")(self._update)
        web_app.delete("/server/mounts/<mount_id>")(self._delete)
        web_app.post("/server/mounts/<mount_id>/mount")(self._do_mount)
        web_app.post("/server/mounts/<mount_id>/unmount")(self._do_unmount)
        web_app.get("/server/mounts/<mount_id>/test")(self._test_connection)

    def _get_all(self):
        """Get all mounts with their current status."""
        bottle.response.content_type = "application/json"
        mounts = self._manager.get_all_mounts()

        result = []
        for mount in mounts:
            mount_data = mount.to_dict_safe()
            status, status_message = get_mount_status(mount)
            mount_data["status"] = status.value
            mount_data["status_message"] = status_message
            result.append(mount_data)

        return json.dumps({"success": True, "data": result})

    def _get_one(self, mount_id: str):
        """Get a specific mount by ID with status."""
        bottle.response.content_type = "application/json"
        mount = self._manager.get_mount_by_id(mount_id)

        if mount is None:
            bottle.response.status = 404
            return json.dumps({"success": False, "error": f"Mount with id '{mount_id}' not found"})

        mount_data = mount.to_dict_safe()
        status, status_message = get_mount_status(mount)
        mount_data["status"] = status.value
        mount_data["status_message"] = status_message

        return json.dumps({"success": True, "data": mount_data})

    def _create(self):
        """Create a new mount configuration."""
        bottle.response.content_type = "application/json"
        try:
            data = json.loads(bottle.request.body.read().decode("utf-8"))

            # Validate required fields
            if "name" not in data or "mount_type" not in data:
                bottle.response.status = 400
                return json.dumps({"success": False, "error": "name and mount_type are required"})

            # Encrypt password if provided
            password = data.get("password")
            if password:
                password = encrypt_password(password, self._manager.config_dir)

            # Create the mount
            mount = NetworkMount(
                name=data["name"],
                mount_type=data["mount_type"],
                enabled=data.get("enabled", True),
                server=data.get("server", ""),
                share_path=data.get("share_path", ""),
                username=data.get("username"),
                password=password,
                domain=data.get("domain"),
                mount_options=data.get("mount_options", ""),
            )

            warnings = self._manager.add_mount(mount)

            mount_data = mount.to_dict_safe()
            status, status_message = get_mount_status(mount)
            mount_data["status"] = status.value
            mount_data["status_message"] = status_message

            self._logger.info(f"Created network mount: {mount.name} ({mount.mount_type})")
            return json.dumps({"success": True, "data": mount_data, "warnings": warnings})

        except json.JSONDecodeError as e:
            bottle.response.status = 400
            return json.dumps({"success": False, "error": f"Invalid JSON: {e}"})
        except NetworkMountError as e:
            bottle.response.status = 400
            return json.dumps({"success": False, "error": str(e)})
        except PersistError as e:
            bottle.response.status = 500
            return json.dumps({"success": False, "error": f"Failed to save: {e}"})

    def _update(self, mount_id: str):
        """Update an existing mount configuration."""
        bottle.response.content_type = "application/json"
        try:
            # Check if mount exists
            existing = self._manager.get_mount_by_id(mount_id)
            if existing is None:
                bottle.response.status = 404
                return json.dumps({"success": False, "error": f"Mount with id '{mount_id}' not found"})

            data = json.loads(bottle.request.body.read().decode("utf-8"))

            # Handle password update
            password = existing.password  # Keep existing by default
            if "password" in data:
                if data["password"] and data["password"] != "***":
                    # New password provided, encrypt it
                    password = encrypt_password(data["password"], self._manager.config_dir)
                elif data["password"] == "":
                    # Password cleared
                    password = None

            # Update fields (keep existing values for unspecified fields)
            mount = NetworkMount(
                id=mount_id,
                name=data.get("name", existing.name),
                mount_type=data.get("mount_type", existing.mount_type),
                enabled=data.get("enabled", existing.enabled),
                server=data.get("server", existing.server),
                share_path=data.get("share_path", existing.share_path),
                username=data.get("username", existing.username),
                password=password,
                domain=data.get("domain", existing.domain),
                mount_options=data.get("mount_options", existing.mount_options),
            )

            warnings = self._manager.update_mount(mount)

            mount_data = mount.to_dict_safe()
            status, status_message = get_mount_status(mount)
            mount_data["status"] = status.value
            mount_data["status_message"] = status_message

            self._logger.info(f"Updated network mount: {mount.name}")
            return json.dumps({"success": True, "data": mount_data, "warnings": warnings})

        except json.JSONDecodeError as e:
            bottle.response.status = 400
            return json.dumps({"success": False, "error": f"Invalid JSON: {e}"})
        except NetworkMountError as e:
            bottle.response.status = 400
            return json.dumps({"success": False, "error": str(e)})
        except PersistError as e:
            bottle.response.status = 500
            return json.dumps({"success": False, "error": f"Failed to save: {e}"})

    def _delete(self, mount_id: str):
        """Delete a mount configuration."""
        bottle.response.content_type = "application/json"
        try:
            # Check if mounted first
            mount = self._manager.get_mount_by_id(mount_id)
            if mount is None:
                bottle.response.status = 404
                return json.dumps({"success": False, "error": f"Mount with id '{mount_id}' not found"})

            status, _ = get_mount_status(mount)
            if status == MountStatus.MOUNTED:
                # Try to unmount first
                result = do_unmount(mount, self._logger)
                if result.result != MountResult.SUCCESS and result.result != MountResult.ALREADY_UNMOUNTED:
                    bottle.response.status = 400
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"Cannot delete: mount is active and unmount failed: {result.message}",
                        }
                    )

            self._manager.remove_mount(mount_id)
            self._logger.info(f"Deleted network mount: {mount.name}")
            return json.dumps({"success": True, "data": {"deleted": mount_id}})

        except NetworkMountError as e:
            bottle.response.status = 404
            return json.dumps({"success": False, "error": str(e)})
        except PersistError as e:
            bottle.response.status = 500
            return json.dumps({"success": False, "error": f"Failed to save: {e}"})

    def _do_mount(self, mount_id: str):
        """Mount the specified share."""
        bottle.response.content_type = "application/json"
        try:
            mount = self._manager.get_mount_by_id(mount_id)
            if mount is None:
                bottle.response.status = 404
                return json.dumps({"success": False, "error": f"Mount with id '{mount_id}' not found"})

            result = do_mount(mount, self._manager.config_dir, self._logger)

            if result.result == MountResult.SUCCESS:
                self._logger.info(f"Mounted: {mount.name} -> {mount.mount_point}")
                return json.dumps({"success": True, "data": {"message": result.message}})
            elif result.result == MountResult.ALREADY_MOUNTED:
                return json.dumps({"success": True, "data": {"message": "Already mounted"}})
            else:
                self._logger.warning(f"Mount failed for {mount.name}: {result.message}")
                bottle.response.status = 500
                return json.dumps({"success": False, "error": result.message})

        except Exception as e:
            self._logger.exception(f"Mount error for {mount_id}")
            bottle.response.status = 500
            return json.dumps({"success": False, "error": str(e)})

    def _do_unmount(self, mount_id: str):
        """Unmount the specified share."""
        bottle.response.content_type = "application/json"
        try:
            mount = self._manager.get_mount_by_id(mount_id)
            if mount is None:
                bottle.response.status = 404
                return json.dumps({"success": False, "error": f"Mount with id '{mount_id}' not found"})

            # Check for force flag
            try:
                data = json.loads(bottle.request.body.read().decode("utf-8"))
                force = data.get("force", False)
            except (json.JSONDecodeError, UnicodeDecodeError):
                force = False

            result = do_unmount(mount, self._logger, force=force)

            if result.result == MountResult.SUCCESS:
                self._logger.info(f"Unmounted: {mount.name}")
                return json.dumps({"success": True, "data": {"message": result.message}})
            elif result.result == MountResult.ALREADY_UNMOUNTED:
                return json.dumps({"success": True, "data": {"message": "Already unmounted"}})
            else:
                self._logger.warning(f"Unmount failed for {mount.name}: {result.message}")
                bottle.response.status = 500
                return json.dumps({"success": False, "error": result.message})

        except Exception as e:
            self._logger.exception(f"Unmount error for {mount_id}")
            bottle.response.status = 500
            return json.dumps({"success": False, "error": str(e)})

    def _test_connection(self, mount_id: str):
        """Test connectivity to the mount server."""
        bottle.response.content_type = "application/json"
        try:
            mount = self._manager.get_mount_by_id(mount_id)
            if mount is None:
                bottle.response.status = 404
                return json.dumps({"success": False, "error": f"Mount with id '{mount_id}' not found"})

            success, message = test_connection(mount)

            if success:
                return json.dumps({"success": True, "data": {"connected": True, "message": message}})
            else:
                return json.dumps({"success": True, "data": {"connected": False, "message": message}})

        except Exception as e:
            self._logger.exception(f"Connection test error for {mount_id}")
            bottle.response.status = 500
            return json.dumps({"success": False, "error": str(e)})
