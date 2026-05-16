import json
import logging
import sys
import unittest

from common.job_status import JobStatus
from rclone.progress_parser import RcloneProgressParser


class TestRcloneProgressParser(unittest.TestCase):
    def setUp(self):
        self.parser = RcloneProgressParser()
        logger = logging.getLogger("TestRcloneProgressParser")
        logger.addHandler(logging.StreamHandler(sys.stdout))
        self.parser.set_base_logger(logger)

    def test_parse_empty_line(self):
        self.assertIsNone(self.parser.parse_line(""))

    def test_parse_non_json_line(self):
        self.assertIsNone(self.parser.parse_line("not json at all"))

    def test_parse_json_without_stats(self):
        line = json.dumps({"level": "info", "msg": "Starting sync"})
        self.assertIsNone(self.parser.parse_line(line))

    def test_parse_stats_with_total_progress(self):
        line = json.dumps({
            "level": "info",
            "msg": "Transferred: 5 MiB / 10 MiB, 50%, 1 MiB/s, ETA 5s",
            "stats": {
                "bytes": 5242880,
                "totalBytes": 10485760,
                "speed": 1048576.0,
                "eta": 5,
            },
        })
        result = self.parser.parse_line(line)
        self.assertIsNotNone(result)
        total = result["total"]
        self.assertEqual(total.size_local, 5242880)
        self.assertEqual(total.size_remote, 10485760)
        self.assertEqual(total.percent_local, 50)
        self.assertEqual(total.speed, 1048576)
        self.assertEqual(total.eta, 5)

    def test_parse_stats_with_transferring_files(self):
        line = json.dumps({
            "level": "info",
            "msg": "Transferred: ...",
            "stats": {
                "bytes": 1000,
                "totalBytes": 2000,
                "speed": 500.0,
                "eta": 2,
                "transferring": [
                    {
                        "name": "movie.mkv",
                        "size": 2000,
                        "bytes": 1000,
                        "percentage": 50,
                        "speed": 500.0,
                        "eta": 2,
                    },
                ],
            },
        })
        result = self.parser.parse_line(line)
        self.assertIsNotNone(result)
        self.assertIn("movie.mkv", result["files"])
        file_state = result["files"]["movie.mkv"]
        self.assertEqual(file_state.size_local, 1000)
        self.assertEqual(file_state.size_remote, 2000)
        self.assertEqual(file_state.percent_local, 50)
        self.assertEqual(file_state.speed, 500)
        self.assertEqual(file_state.eta, 2)

    def test_parse_stats_with_multiple_files(self):
        line = json.dumps({
            "level": "info",
            "msg": "Transferred: ...",
            "stats": {
                "bytes": 3000,
                "totalBytes": 5000,
                "speed": 1000.0,
                "eta": 2,
                "transferring": [
                    {"name": "file1.txt", "size": 2000, "bytes": 1000, "percentage": 50, "speed": 500.0, "eta": 2},
                    {"name": "file2.txt", "size": 3000, "bytes": 2000, "percentage": 66, "speed": 500.0, "eta": 2},
                ],
            },
        })
        result = self.parser.parse_line(line)
        self.assertEqual(len(result["files"]), 2)
        self.assertIn("file1.txt", result["files"])
        self.assertIn("file2.txt", result["files"])

    def test_parse_stats_with_zero_total_bytes(self):
        """When totalBytes is 0 (e.g., at start of transfer), percent should be None."""
        line = json.dumps({
            "level": "info",
            "msg": "Transferred: ...",
            "stats": {
                "bytes": 0,
                "totalBytes": 0,
                "speed": 0.0,
                "eta": None,
            },
        })
        result = self.parser.parse_line(line)
        self.assertIsNotNone(result)
        self.assertIsNone(result["total"].percent_local)

    def test_parse_stats_with_none_speed_and_eta(self):
        line = json.dumps({
            "level": "info",
            "msg": "Transferred: ...",
            "stats": {
                "bytes": 100,
                "totalBytes": 1000,
            },
        })
        result = self.parser.parse_line(line)
        self.assertIsNotNone(result)
        self.assertIsNone(result["total"].speed)
        self.assertIsNone(result["total"].eta)

    def test_parse_stats_no_transferring_key(self):
        line = json.dumps({
            "level": "info",
            "msg": "Transferred: ...",
            "stats": {
                "bytes": 100,
                "totalBytes": 200,
                "speed": 50.0,
                "eta": 2,
            },
        })
        result = self.parser.parse_line(line)
        self.assertEqual(len(result["files"]), 0)

    def test_parse_malformed_json(self):
        self.assertIsNone(self.parser.parse_line("{invalid json"))
