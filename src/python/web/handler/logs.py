# Copyright 2026, RapidCopy Contributors, All rights reserved.

"""
Log search API handler.

Serves historical log records from the on-disk rotating log files.

GET /server/logs
  Query params:
    search  — substring to match (case-insensitive); empty = all
    level   — minimum level filter: DEBUG|INFO|WARNING|ERROR|CRITICAL
    limit   — max records to return (default 500, max 2000)
    before  — Unix timestamp (float); return only records older than this
"""

import os
import re
import json
import glob as glob_module
from typing import Generator

from bottle import HTTPResponse, request

from ..web_app import IHandler, WebApp
from common import overrides

_LEVEL_ORDER = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
    "CRITICAL": 4,
}

# Pattern matching StandardFormatter output:
# 2026-02-19 16:30:37 - INFO - rapidcopy (MainProcess/MainThread) - message
_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (DEBUG|INFO|WARNING|ERROR|CRITICAL) - (.+?) \(\S+/\S+\) - (.*)$"
)


def _log_files_newest_first(log_dir: str, logger_name: str) -> list[str]:
    """Return log file paths for the given logger, newest-first."""
    base = os.path.join(log_dir, f"{logger_name}.log")
    rotated = sorted(
        glob_module.glob(base + ".*"),
        key=lambda p: int(p.rsplit(".", 1)[-1]) if p.rsplit(".", 1)[-1].isdigit() else 0,
    )
    # Current file is newest; rotated .1 is next, .2 older, etc.
    files = [base] + rotated
    return [f for f in files if os.path.isfile(f)]


def _iter_records_reversed(log_dir: str, logger_name: str) -> Generator[dict, None, None]:
    """
    Yield parsed log records from disk, newest first, across all rotated files.
    Accumulates continuation lines (tracebacks) onto the preceding record.
    """
    for path in _log_files_newest_first(log_dir, logger_name):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError:
            continue

        # Walk lines in reverse; accumulate traceback lines onto the last header
        pending_extra: list[str] = []
        for raw in reversed(lines):
            line = raw.rstrip("\n")
            m = _LOG_LINE_RE.match(line)
            if m:
                timestamp_str, level, logger, message = m.groups()
                # Parse timestamp to Unix float (local time)
                from datetime import datetime
                try:
                    ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S").timestamp()
                except ValueError:
                    ts = 0.0
                record = {
                    "time": ts,
                    "level_name": level,
                    "logger_name": logger,
                    "message": message,
                    "exc_tb": "\n".join(reversed(pending_extra)) if pending_extra else None,
                }
                pending_extra = []
                yield record
            else:
                # Continuation line (traceback or wrapped message)
                pending_extra.append(line)


class LogsHandler(IHandler):
    """REST handler for querying historical log records."""

    _DEFAULT_LIMIT = 500
    _MAX_LIMIT = 2000

    def __init__(self, log_dir: str, logger_name: str = "rapidcopy"):
        self._log_dir = log_dir
        self._logger_name = logger_name

    @overrides(IHandler)
    def add_routes(self, web_app: WebApp):
        web_app.add_handler("/server/logs", self._handle_get_logs)

    def _handle_get_logs(self):
        search = (request.query.get("search") or "").strip().lower()
        level_filter = (request.query.get("level") or "").upper().strip()
        before_str = request.query.get("before") or ""
        limit_str = request.query.get("limit") or str(self._DEFAULT_LIMIT)

        try:
            limit = min(int(limit_str), self._MAX_LIMIT)
        except ValueError:
            limit = self._DEFAULT_LIMIT

        before: float | None = None
        if before_str:
            try:
                before = float(before_str)
            except ValueError:
                pass

        min_level = _LEVEL_ORDER.get(level_filter, 0)

        if not os.path.isdir(self._log_dir):
            body = json.dumps({"records": [], "truncated": False})
            return HTTPResponse(body=body, content_type="application/json")

        records = []
        truncated = False
        for rec in _iter_records_reversed(self._log_dir, self._logger_name):
            if before is not None and rec["time"] >= before:
                continue
            if _LEVEL_ORDER.get(rec["level_name"], 0) < min_level:
                continue
            if search and search not in rec["message"].lower() and (
                rec["exc_tb"] is None or search not in rec["exc_tb"].lower()
            ):
                continue
            records.append(rec)
            if len(records) >= limit:
                truncated = True
                break

        # Reverse so oldest-first for the UI
        records.reverse()

        body = json.dumps({"records": records, "truncated": truncated})
        return HTTPResponse(body=body, content_type="application/json")
