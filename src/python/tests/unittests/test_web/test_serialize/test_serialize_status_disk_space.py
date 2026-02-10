# Copyright 2024, SeedSync Contributors, All rights reserved.

import unittest
import json
from datetime import datetime
from pytz import timezone

from .test_serialize import parse_stream
from common import Status
from web.serialize import SerializeStatus


class TestSerializeStatusDiskSpace(unittest.TestCase):
    """Tests for disk space status serialization"""

    def test_downloads_paused_disk_space_default_none(self):
        """downloads_paused_disk_space defaults to None"""
        serialize = SerializeStatus()
        status = Status()
        out = parse_stream(serialize.status(status))
        data = json.loads(out["data"])
        self.assertIsNone(data["controller"]["downloads_paused_disk_space"])

    def test_downloads_paused_disk_space_true(self):
        """downloads_paused_disk_space serializes True correctly"""
        serialize = SerializeStatus()
        status = Status()
        status.controller.downloads_paused_disk_space = True
        out = parse_stream(serialize.status(status))
        data = json.loads(out["data"])
        self.assertEqual(True, data["controller"]["downloads_paused_disk_space"])

    def test_downloads_paused_disk_space_false(self):
        """downloads_paused_disk_space serializes False correctly"""
        serialize = SerializeStatus()
        status = Status()
        status.controller.downloads_paused_disk_space = False
        out = parse_stream(serialize.status(status))
        data = json.loads(out["data"])
        self.assertEqual(False, data["controller"]["downloads_paused_disk_space"])

    def test_disk_space_error_default_none(self):
        """disk_space_error defaults to None"""
        serialize = SerializeStatus()
        status = Status()
        out = parse_stream(serialize.status(status))
        data = json.loads(out["data"])
        self.assertIsNone(data["controller"]["disk_space_error"])

    def test_disk_space_error_with_message(self):
        """disk_space_error serializes error string correctly"""
        serialize = SerializeStatus()
        status = Status()
        status.controller.disk_space_error = "Low disk space on /data (5.2% free, threshold 10%)"
        out = parse_stream(serialize.status(status))
        data = json.loads(out["data"])
        self.assertEqual(
            "Low disk space on /data (5.2% free, threshold 10%)",
            data["controller"]["disk_space_error"]
        )

    def test_disk_space_fields_present_in_controller_section(self):
        """Both disk space fields are present in the controller section"""
        serialize = SerializeStatus()
        status = Status()
        out = parse_stream(serialize.status(status))
        data = json.loads(out["data"])
        self.assertIn("downloads_paused_disk_space", data["controller"])
        self.assertIn("disk_space_error", data["controller"])

    def test_disk_space_with_other_status_fields(self):
        """Disk space fields coexist with other controller status fields"""
        serialize = SerializeStatus()
        status = Status()
        timestamp = datetime(2018, 11, 9, 21, 40, 18, tzinfo=timezone('UTC'))
        status.controller.latest_local_scan_time = timestamp
        status.controller.downloads_paused_disk_space = True
        status.controller.disk_space_error = "Low disk"
        out = parse_stream(serialize.status(status))
        data = json.loads(out["data"])
        # All fields present
        self.assertEqual(str(1541799618.0), data["controller"]["latest_local_scan_time"])
        self.assertEqual(True, data["controller"]["downloads_paused_disk_space"])
        self.assertEqual("Low disk", data["controller"]["disk_space_error"])
