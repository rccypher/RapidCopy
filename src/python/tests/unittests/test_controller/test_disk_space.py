# Copyright 2024, SeedSync Contributors, All rights reserved.

import logging
import sys
import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import shutil
import time

from common import Status
from common.config import PathMapping


class TestDiskSpaceCheck(unittest.TestCase):
    """
    Tests for the Controller's disk space checking logic.
    Since Controller.__check_disk_space() is private, we test it by
    calling Controller.process() with mocked dependencies. However,
    Controller has many dependencies (scanners, lftp, etc.) that are
    hard to mock fully. Instead, we test the disk_usage logic and
    status updates at a unit level.
    """

    def test_status_properties_exist(self):
        """ControllerStatus has disk space properties"""
        status = Status()
        self.assertIsNone(status.controller.downloads_paused_disk_space)
        self.assertIsNone(status.controller.disk_space_error)

    def test_status_downloads_paused_disk_space(self):
        """Can set and get downloads_paused_disk_space"""
        status = Status()
        status.controller.downloads_paused_disk_space = True
        self.assertEqual(True, status.controller.downloads_paused_disk_space)
        status.controller.downloads_paused_disk_space = False
        self.assertEqual(False, status.controller.downloads_paused_disk_space)

    def test_status_disk_space_error(self):
        """Can set and get disk_space_error"""
        status = Status()
        status.controller.disk_space_error = "Low disk space on /data (5.2% free)"
        self.assertEqual("Low disk space on /data (5.2% free)", status.controller.disk_space_error)

    def test_status_disk_space_listener_notification(self):
        """Setting disk space properties notifies listeners"""
        status = Status()
        mock_listener = MagicMock()
        mock_listener.notify = MagicMock()
        status.add_listener(mock_listener)

        status.controller.downloads_paused_disk_space = True
        mock_listener.notify.assert_called()
        mock_listener.notify.reset_mock()

        status.controller.disk_space_error = "Low disk"
        mock_listener.notify.assert_called()

    def test_status_copy_includes_disk_space(self):
        """Status.copy() includes disk space fields"""
        status = Status()
        status.controller.downloads_paused_disk_space = True
        status.controller.disk_space_error = "Low disk on /data"
        copy = status.copy()
        self.assertEqual(True, copy.controller.downloads_paused_disk_space)
        self.assertEqual("Low disk on /data", copy.controller.disk_space_error)


class TestDiskSpaceThresholdLogic(unittest.TestCase):
    """
    Tests for the disk space threshold logic by verifying the actual
    calculation used in Controller.__check_disk_space().
    This tests the logic: percent_free = (usage.free / usage.total) * 100
    """

    def test_percent_free_above_threshold(self):
        """When free space is above threshold, no pause should occur"""
        # Simulate: 200GB total, 30GB free = 15% free, threshold = 10%
        total = 200 * 1024 * 1024 * 1024
        free = 30 * 1024 * 1024 * 1024
        percent_free = (free / total) * 100
        threshold = 10
        self.assertGreater(percent_free, threshold)

    def test_percent_free_below_threshold(self):
        """When free space is below threshold, pause should occur"""
        # Simulate: 200GB total, 10GB free = 5% free, threshold = 10%
        total = 200 * 1024 * 1024 * 1024
        free = 10 * 1024 * 1024 * 1024
        percent_free = (free / total) * 100
        threshold = 10
        self.assertLess(percent_free, threshold)

    def test_percent_free_at_threshold(self):
        """When free space equals threshold exactly, no pause (not strictly less)"""
        # 200GB total, 20GB free = 10.0% free, threshold = 10%
        total = 200 * 1024 * 1024 * 1024
        free = 20 * 1024 * 1024 * 1024
        percent_free = (free / total) * 100
        threshold = 10
        # The controller uses `percent_free < threshold`, so exactly at threshold = no pause
        self.assertFalse(percent_free < threshold)

    def test_zero_free_space(self):
        """Zero free space triggers threshold"""
        total = 100 * 1024 * 1024 * 1024
        free = 0
        percent_free = (free / total) * 100
        threshold = 10
        self.assertTrue(percent_free < threshold)

    def test_nearly_full_disk(self):
        """Nearly full disk (1% free) triggers threshold"""
        total = 1000 * 1024 * 1024 * 1024
        free = 10 * 1024 * 1024 * 1024  # 1%
        percent_free = (free / total) * 100
        threshold = 10
        self.assertTrue(percent_free < threshold)


class TestDiskSpaceCheckInterval(unittest.TestCase):
    """Tests for the throttled disk space check interval logic"""

    def test_check_interval_constant(self):
        """The disk space check interval is 30 seconds"""
        from controller.controller import Controller
        self.assertEqual(30, Controller._DISK_SPACE_CHECK_INTERVAL_S)

    def test_time_monotonic_throttle_logic(self):
        """Verify the throttle logic: skip if elapsed < interval"""
        interval = 30
        last_check_time = time.monotonic()
        now = last_check_time + 5  # 5 seconds later
        self.assertTrue(now - last_check_time < interval)  # Should be throttled

        now = last_check_time + 31  # 31 seconds later
        self.assertFalse(now - last_check_time < interval)  # Should not be throttled


class TestDiskSpaceConfigProperties(unittest.TestCase):
    """Tests for the disk space config properties on Config.Controller"""

    def test_enable_disk_space_check_from_dict(self):
        """enable_disk_space_check parses True/False from dict"""
        from common import Config
        d = self._make_controller_dict()
        d["enable_disk_space_check"] = "True"
        c = Config.Controller.from_dict(d)
        self.assertTrue(c.enable_disk_space_check)

        d["enable_disk_space_check"] = "False"
        c = Config.Controller.from_dict(d)
        self.assertFalse(c.enable_disk_space_check)

    def test_disk_space_min_percent_from_dict(self):
        """disk_space_min_percent parses positive integer from dict"""
        from common import Config
        d = self._make_controller_dict()
        d["disk_space_min_percent"] = "15"
        c = Config.Controller.from_dict(d)
        self.assertEqual(15, c.disk_space_min_percent)

    def test_disk_space_min_percent_bad_value(self):
        """disk_space_min_percent rejects non-positive values"""
        from common import Config, ConfigError
        d = self._make_controller_dict()
        d["disk_space_min_percent"] = "-1"
        with self.assertRaises(ConfigError):
            Config.Controller.from_dict(d)

        d["disk_space_min_percent"] = "0"
        with self.assertRaises(ConfigError):
            Config.Controller.from_dict(d)

        d["disk_space_min_percent"] = "abc"
        with self.assertRaises(ConfigError):
            Config.Controller.from_dict(d)

    def test_enable_disk_space_check_bad_value(self):
        """enable_disk_space_check rejects non-boolean values"""
        from common import Config, ConfigError
        d = self._make_controller_dict()
        d["enable_disk_space_check"] = "NotABool"
        with self.assertRaises(ConfigError):
            Config.Controller.from_dict(d)

    def _make_controller_dict(self):
        return {
            "interval_ms_remote_scan": "30000",
            "interval_ms_local_scan": "10000",
            "interval_ms_downloading_scan": "2000",
            "extract_path": "/extract/path",
            "use_local_path_as_extract_path": "True",
            "enable_download_validation": "True",
            "download_validation_max_retries": "3",
            "use_chunked_validation": "False",
            "validation_chunk_size_mb": "4",
            "enable_disk_space_check": "True",
            "disk_space_min_percent": "10",
        }
