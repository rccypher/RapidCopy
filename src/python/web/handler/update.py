# Copyright 2017-2025, Inderpreet Singh, rccypher, All rights reserved.

import os
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from bottle import HTTPResponse

from common import overrides
from ..web_app import IHandler, WebApp


class UpdateHandler(IHandler):
    """
    Handler for update operations.
    Proxies requests to the host sidecar update server.
    """

    def __init__(self, logger):
        self.logger = logger.getChild("UpdateHandler")
        # Get update server URL from environment or default
        self.__update_server_url = os.environ.get("UPDATE_SERVER_URL", "http://host.docker.internal:8801")
        # Get update token from environment
        self.__update_token = os.environ.get("UPDATE_TOKEN", "")

    @overrides(IHandler)
    def add_routes(self, web_app: WebApp):
        web_app.add_handler("/server/update/status", self.__handle_status)
        web_app.add_handler("/server/update/trigger", self.__handle_trigger)
        web_app.add_handler("/server/update/health", self.__handle_health)

    def __make_request(self, path: str, method: str = "GET") -> tuple[bool, dict | str]:
        """
        Make a request to the update server.
        Returns (success, data/error_message)
        """
        url = f"{self.__update_server_url}{path}"

        try:
            headers = {}
            if self.__update_token:
                headers["Authorization"] = f"Bearer {self.__update_token}"

            request = Request(url, method=method, headers=headers)

            with urlopen(request, timeout=30) as response:
                data = response.read().decode("utf-8")
                return True, json.loads(data)

        except HTTPError as e:
            self.logger.error(f"HTTP error from update server: {e.code} {e.reason}")
            try:
                error_data = json.loads(e.read().decode("utf-8"))
                return False, error_data.get("error", str(e))
            except:
                return False, f"HTTP {e.code}: {e.reason}"

        except URLError as e:
            self.logger.error(f"URL error connecting to update server: {e.reason}")
            return False, f"Cannot connect to update server: {e.reason}"

        except Exception as e:
            self.logger.error(f"Error communicating with update server: {e}")
            return False, str(e)

    def __handle_health(self):
        """
        Check if update server is reachable (no auth required on sidecar).
        """
        url = f"{self.__update_server_url}/health"
        try:
            request = Request(url, method="GET")
            with urlopen(request, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                return HTTPResponse(
                    body=json.dumps(
                        {
                            "available": True,
                            "configured": bool(self.__update_token),
                            "server_status": data.get("status", "unknown"),
                        }
                    ),
                    status=200,
                    headers={"Content-Type": "application/json"},
                )
        except Exception as e:
            self.logger.debug(f"Update server not available: {e}")
            return HTTPResponse(
                body=json.dumps({"available": False, "configured": bool(self.__update_token), "error": str(e)}),
                status=200,  # Return 200 even if unavailable - frontend handles this
                headers={"Content-Type": "application/json"},
            )

    def __handle_status(self):
        """
        Get current update status from the sidecar.
        """
        if not self.__update_token:
            return HTTPResponse(
                body=json.dumps({"error": "Update token not configured"}),
                status=503,
                headers={"Content-Type": "application/json"},
            )

        success, result = self.__make_request("/status")

        if success:
            return HTTPResponse(body=json.dumps(result), status=200, headers={"Content-Type": "application/json"})
        else:
            return HTTPResponse(
                body=json.dumps({"error": result}), status=502, headers={"Content-Type": "application/json"}
            )

    def __handle_trigger(self):
        """
        Trigger an update via the sidecar.
        """
        if not self.__update_token:
            return HTTPResponse(
                body=json.dumps({"error": "Update token not configured"}),
                status=503,
                headers={"Content-Type": "application/json"},
            )

        success, result = self.__make_request("/update", method="POST")

        if success:
            return HTTPResponse(body=json.dumps(result), status=202, headers={"Content-Type": "application/json"})
        else:
            # Check if it's "already in progress"
            status_code = 409 if "in progress" in str(result).lower() else 502
            return HTTPResponse(
                body=json.dumps({"error": result}), status=status_code, headers={"Content-Type": "application/json"}
            )
