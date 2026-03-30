# Copyright 2024, RapidCopy Contributors, All rights reserved.

"""
REST API handler for path pair management.

Endpoints:
    GET    /server/path-pairs         - List all path pairs
    GET    /server/path-pairs/:id     - Get a specific path pair
    POST   /server/path-pairs         - Create a new path pair
    PUT    /server/path-pairs/:id     - Update a path pair
    DELETE /server/path-pairs/:id     - Delete a path pair
    POST   /server/path-pairs/reorder - Reorder path pairs
"""

import json
from dataclasses import asdict

import bottle

from common import PathPairManager, PathPair, PathPairError, PersistError
from web.web_app import IHandler, WebApp


class PathPairsHandler(IHandler):
    """
    Handler for path pair CRUD operations.
    """

    def __init__(self, path_pair_manager: PathPairManager):
        self._manager = path_pair_manager

    def add_routes(self, web_app: WebApp):
        web_app.get("/server/path-pairs")(self._get_all)
        web_app.get("/server/path-pairs/<pair_id>")(self._get_one)
        web_app.post("/server/path-pairs")(self._create)
        web_app.put("/server/path-pairs/<pair_id>")(self._update)
        web_app.delete("/server/path-pairs/<pair_id>")(self._delete)
        web_app.post("/server/path-pairs/reorder")(self._reorder)

    def _get_all(self):
        """Get all path pairs."""
        bottle.response.content_type = "application/json"
        pairs = self._manager.get_all_pairs()
        return json.dumps({"success": True, "data": [asdict(p) for p in pairs]})

    def _get_one(self, pair_id: str):
        """Get a specific path pair by ID."""
        bottle.response.content_type = "application/json"
        pair = self._manager.get_pair_by_id(pair_id)
        if pair is None:
            bottle.response.status = 404
            return json.dumps({"success": False, "error": f"Path pair with id '{pair_id}' not found"})
        return json.dumps({"success": True, "data": asdict(pair)})

    def _create(self):
        """Create a new path pair."""
        bottle.response.content_type = "application/json"
        try:
            data = json.loads(bottle.request.body.read().decode("utf-8"))

            # Validate required fields
            if "remote_path" not in data or "local_path" not in data:
                bottle.response.status = 400
                return json.dumps({"success": False, "error": "remote_path and local_path are required"})

            # Create the path pair (ID will be auto-generated)
            pair = PathPair(
                name=data.get("name", ""),
                remote_path=data["remote_path"],
                local_path=data["local_path"],
                enabled=data.get("enabled", True),
                auto_queue=data.get("auto_queue", True),
            )

            warnings = self._manager.add_pair(pair)

            return json.dumps({"success": True, "data": asdict(pair), "warnings": warnings})

        except json.JSONDecodeError as e:
            bottle.response.status = 400
            return json.dumps({"success": False, "error": f"Invalid JSON: {e}"})
        except PathPairError as e:
            bottle.response.status = 400
            return json.dumps({"success": False, "error": str(e)})
        except PersistError as e:
            bottle.response.status = 500
            return json.dumps({"success": False, "error": f"Failed to save: {e}"})

    def _update(self, pair_id: str):
        """Update an existing path pair."""
        bottle.response.content_type = "application/json"
        try:
            # Check if pair exists
            existing = self._manager.get_pair_by_id(pair_id)
            if existing is None:
                bottle.response.status = 404
                return json.dumps({"success": False, "error": f"Path pair with id '{pair_id}' not found"})

            data = json.loads(bottle.request.body.read().decode("utf-8"))

            # Update fields (keep existing values for unspecified fields)
            pair = PathPair(
                id=pair_id,
                name=data.get("name", existing.name),
                remote_path=data.get("remote_path", existing.remote_path),
                local_path=data.get("local_path", existing.local_path),
                enabled=data.get("enabled", existing.enabled),
                auto_queue=data.get("auto_queue", existing.auto_queue),
            )

            self._manager.update_pair(pair)

            return json.dumps({"success": True, "data": asdict(pair), "warnings": []})

        except json.JSONDecodeError as e:
            bottle.response.status = 400
            return json.dumps({"success": False, "error": f"Invalid JSON: {e}"})
        except PathPairError as e:
            bottle.response.status = 400
            return json.dumps({"success": False, "error": str(e)})
        except PersistError as e:
            bottle.response.status = 500
            return json.dumps({"success": False, "error": f"Failed to save: {e}"})

    def _delete(self, pair_id: str):
        """Delete a path pair."""
        bottle.response.content_type = "application/json"
        try:
            self._manager.remove_pair(pair_id)
            return json.dumps({"success": True, "data": {"deleted": pair_id}})
        except PathPairError as e:
            bottle.response.status = 404
            return json.dumps({"success": False, "error": str(e)})
        except PersistError as e:
            bottle.response.status = 500
            return json.dumps({"success": False, "error": f"Failed to save: {e}"})

    def _reorder(self):
        """Reorder path pairs."""
        bottle.response.content_type = "application/json"
        try:
            data = json.loads(bottle.request.body.read().decode("utf-8"))

            if "order" not in data or not isinstance(data["order"], list):
                bottle.response.status = 400
                return json.dumps({"success": False, "error": "order field must be a list of path pair IDs"})

            self._manager.reorder_pairs(data["order"])

            return json.dumps({"success": True, "data": [asdict(p) for p in self._manager.get_all_pairs()]})

        except json.JSONDecodeError as e:
            bottle.response.status = 400
            return json.dumps({"success": False, "error": f"Invalid JSON: {e}"})
        except PathPairError as e:
            bottle.response.status = 400
            return json.dumps({"success": False, "error": str(e)})
        except PersistError as e:
            bottle.response.status = 500
            return json.dumps({"success": False, "error": f"Failed to save: {e}"})
