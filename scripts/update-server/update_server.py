#!/usr/bin/env python3
"""
RapidCopy Update Server - Host Sidecar
Lightweight HTTP server that runs on the host to handle RapidCopy updates.
Requires token authentication for security.

Usage:
    UPDATE_TOKEN=your-secret-token python3 update_server.py

Or with systemd service (recommended).
"""

import os
import sys
import json
import subprocess
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# Configuration
HOST = "0.0.0.0"
PORT = int(os.environ.get("UPDATE_SERVER_PORT", "8801"))
RAPIDCOPY_PATH = os.environ.get("RAPIDCOPY_PATH", "/opt/RapidCopy")
UPDATE_TOKEN = os.environ.get("UPDATE_TOKEN", "")
UPDATE_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "update-rapidcopy.sh"
)

# Update state
update_state = {
    "status": "idle",  # idle, updating, success, failed
    "message": "",
    "started_at": None,
    "completed_at": None,
    "output": "",
}
update_lock = threading.Lock()


class UpdateHandler(BaseHTTPRequestHandler):
    """HTTP request handler for update operations."""

    def log_message(self, format, *args):
        """Override to add timestamp to logs."""
        print(f"[{datetime.now().isoformat()}] {args[0]}")

    def send_json(self, status_code, data):
        """Send JSON response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def check_auth(self):
        """Verify the authorization token."""
        if not UPDATE_TOKEN:
            self.send_json(
                500, {"error": "Server not configured: UPDATE_TOKEN not set"}
            )
            return False

        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self.send_json(401, {"error": "Missing or invalid Authorization header"})
            return False

        token = auth_header[7:]  # Remove "Bearer " prefix
        if token != UPDATE_TOKEN:
            self.send_json(403, {"error": "Invalid token"})
            return False

        return True

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            # Health check - no auth required
            self.send_json(200, {"status": "ok", "service": "rapidcopy-updater"})
            return

        if self.path == "/status":
            if not self.check_auth():
                return
            with update_lock:
                self.send_json(200, update_state.copy())
            return

        self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        """Handle POST requests."""
        if self.path == "/update":
            if not self.check_auth():
                return

            with update_lock:
                if update_state["status"] == "updating":
                    self.send_json(
                        409,
                        {
                            "error": "Update already in progress",
                            "started_at": update_state["started_at"],
                        },
                    )
                    return

                # Start update
                update_state["status"] = "updating"
                update_state["message"] = "Update started"
                update_state["started_at"] = datetime.now().isoformat()
                update_state["completed_at"] = None
                update_state["output"] = ""

            # Run update in background thread
            thread = threading.Thread(target=run_update, daemon=True)
            thread.start()

            self.send_json(
                202,
                {"message": "Update started", "started_at": update_state["started_at"]},
            )
            return

        self.send_json(404, {"error": "Not found"})


def run_update():
    """Run the update script in background."""
    global update_state

    try:
        print(f"[{datetime.now().isoformat()}] Starting update...")

        # Run the update script
        result = subprocess.run(
            [UPDATE_SCRIPT],
            cwd=RAPIDCOPY_PATH,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        with update_lock:
            update_state["output"] = result.stdout + result.stderr
            update_state["completed_at"] = datetime.now().isoformat()

            if result.returncode == 0:
                update_state["status"] = "success"
                update_state["message"] = "Update completed successfully"
                print(f"[{datetime.now().isoformat()}] Update completed successfully")
            else:
                update_state["status"] = "failed"
                update_state["message"] = (
                    f"Update failed with exit code {result.returncode}"
                )
                print(f"[{datetime.now().isoformat()}] Update failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        with update_lock:
            update_state["status"] = "failed"
            update_state["message"] = "Update timed out after 10 minutes"
            update_state["completed_at"] = datetime.now().isoformat()
        print(f"[{datetime.now().isoformat()}] Update timed out")

    except Exception as e:
        with update_lock:
            update_state["status"] = "failed"
            update_state["message"] = f"Update error: {str(e)}"
            update_state["completed_at"] = datetime.now().isoformat()
        print(f"[{datetime.now().isoformat()}] Update error: {e}")


def main():
    """Main entry point."""
    if not UPDATE_TOKEN:
        print("WARNING: UPDATE_TOKEN environment variable not set!")
        print("The server will reject all authenticated requests.")
        print("Set UPDATE_TOKEN to enable updates.")

    if not os.path.isdir(RAPIDCOPY_PATH):
        print(f"WARNING: RAPIDCOPY_PATH does not exist: {RAPIDCOPY_PATH}")
        print("Set RAPIDCOPY_PATH environment variable to the correct path.")

    if not os.path.isfile(UPDATE_SCRIPT):
        print(f"ERROR: Update script not found: {UPDATE_SCRIPT}")
        sys.exit(1)

    print(f"RapidCopy Update Server starting...")
    print(f"  Port: {PORT}")
    print(f"  RapidCopy path: {RAPIDCOPY_PATH}")
    print(f"  Update script: {UPDATE_SCRIPT}")
    print(f"  Token configured: {'Yes' if UPDATE_TOKEN else 'No'}")

    server = HTTPServer((HOST, PORT), UpdateHandler)
    print(f"Server listening on {HOST}:{PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
