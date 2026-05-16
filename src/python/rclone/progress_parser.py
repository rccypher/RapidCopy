# Parse rclone JSON log output (--use-json-log --stats 1s -v) into JobStatus TransferState.

import json
import logging

from common.job_status import JobStatus


class RcloneProgressParser:
    """
    Parses rclone's JSON log lines emitted to stderr with --use-json-log.

    rclone emits JSON objects like:
    {
      "level": "info",
      "msg": "Transferred: ...",
      "stats": {
        "bytes": 1293942,
        "totalBytes": 10485760,
        "speed": 512000.0,
        "eta": 18,
        "transferring": [
          {
            "name": "file.bin",
            "size": 10485760,
            "bytes": 1293942,
            "percentage": 12,
            "speed": 512000.0,
            "eta": 18
          }
        ]
      }
    }
    """

    def __init__(self):
        self.logger = logging.getLogger("RcloneProgressParser")

    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild("RcloneProgressParser")

    def parse_line(self, line: str) -> dict | None:
        """
        Parse a single JSON log line from rclone stderr.

        Returns a dict with:
          "total": JobStatus.TransferState for overall progress
          "files": dict[str, JobStatus.TransferState] for per-file progress
        Or None if the line is not a stats line.
        """
        line = line.strip()
        if not line:
            return None

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            self.logger.debug("Skipping non-JSON line: %s", line[:200])
            return None

        stats = data.get("stats")
        if stats is None:
            return None

        # Parse total transfer state
        total_bytes_transferred = stats.get("bytes")
        total_bytes_remote = stats.get("totalBytes")
        speed = stats.get("speed")
        eta = stats.get("eta")

        # Calculate percentage
        percent = None
        if total_bytes_remote and total_bytes_remote > 0 and total_bytes_transferred is not None:
            percent = int(100 * total_bytes_transferred / total_bytes_remote)

        # Convert speed to int if present (rclone reports as float)
        if speed is not None:
            speed = int(speed)

        # Convert eta to int if present
        if eta is not None:
            eta = int(eta)

        total_state = JobStatus.TransferState(
            size_local=total_bytes_transferred,
            size_remote=total_bytes_remote,
            percent_local=percent,
            speed=speed,
            eta=eta,
        )

        # Parse per-file transfer states
        files: dict[str, JobStatus.TransferState] = {}
        transferring = stats.get("transferring")
        if transferring:
            for file_info in transferring:
                name = file_info.get("name")
                if not name:
                    continue
                file_speed = file_info.get("speed")
                if file_speed is not None:
                    file_speed = int(file_speed)
                file_eta = file_info.get("eta")
                if file_eta is not None:
                    file_eta = int(file_eta)
                files[name] = JobStatus.TransferState(
                    size_local=file_info.get("bytes"),
                    size_remote=file_info.get("size"),
                    percent_local=file_info.get("percentage"),
                    speed=file_speed,
                    eta=file_eta,
                )

        return {"total": total_state, "files": files}
