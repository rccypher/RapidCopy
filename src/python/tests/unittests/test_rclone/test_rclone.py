import logging
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

from rclone.rclone import Rclone, RcloneError


class TestRclone(unittest.TestCase):
    """Test Rclone class initialization and command construction."""

    @patch("rclone.rclone.subprocess.run")
    @patch("rclone.rclone.shutil.which", return_value="/usr/bin/rclone")
    def setUp(self, mock_which, mock_run):
        # Mock rclone obscure
        mock_run.return_value = MagicMock(returncode=0, stdout="obscured_pass\n")
        self.rclone = Rclone(
            address="example.com",
            port=22,
            user="testuser",
            password="testpass",
        )
        logger = logging.getLogger("TestRclone")
        logger.addHandler(logging.StreamHandler(sys.stdout))
        self.rclone.set_base_logger(logger)
        self.rclone.set_base_remote_dir_path("/remote/downloads")
        self.rclone.set_base_local_dir_path("/local/staging")

    def tearDown(self):
        self.rclone.exit()

    def test_missing_rclone_binary(self):
        with patch("rclone.rclone.shutil.which", return_value=None):
            with self.assertRaises(RcloneError) as ctx:
                Rclone("host", 22, "user", "pass")
            self.assertIn("not found", str(ctx.exception))

    def test_default_properties(self):
        self.assertEqual(self.rclone.num_parallel_jobs, 2)
        self.assertEqual(self.rclone.num_parallel_files, 4)
        self.assertEqual(self.rclone.num_connections_per_root_file, 2)
        self.assertEqual(self.rclone.num_connections_per_dir_file, 2)
        self.assertEqual(self.rclone.num_max_total_connections, 16)
        self.assertEqual(self.rclone.rate_limit, "0")
        self.assertFalse(self.rclone.use_temp_file)

    def test_set_num_parallel_jobs(self):
        self.rclone.num_parallel_jobs = 5
        self.assertEqual(self.rclone.num_parallel_jobs, 5)

    def test_set_num_parallel_jobs_zero_raises(self):
        with self.assertRaises(ValueError):
            self.rclone.num_parallel_jobs = 0

    def test_set_rate_limit(self):
        self.rclone.rate_limit = "1M"
        self.assertEqual(self.rclone.rate_limit, "1M")

    def test_set_rate_limit_int(self):
        self.rclone.rate_limit = 0
        self.assertEqual(self.rclone.rate_limit, "0")

    def test_set_use_temp_file(self):
        self.rclone.use_temp_file = True
        self.assertTrue(self.rclone.use_temp_file)

    def test_set_temp_file_name(self):
        self.rclone.temp_file_name = "*.lftp"
        self.assertEqual(self.rclone.temp_file_name, "*.lftp")

    def test_build_command_single_file(self):
        self.rclone.use_temp_file = True
        self.rclone.temp_file_name = "*.lftp"
        self.rclone.rate_limit = "1M"
        cmd, env = self.rclone._build_command(
            "movie.mkv", False, "/remote/downloads", "/local/staging"
        )
        self.assertEqual(cmd[0], "rclone")
        self.assertEqual(cmd[1], "copyto")
        self.assertIn("--partial-suffix", cmd)
        suffix_idx = cmd.index("--partial-suffix")
        self.assertEqual(cmd[suffix_idx + 1], ".lftp")
        self.assertIn("--bwlimit", cmd)
        bw_idx = cmd.index("--bwlimit")
        self.assertEqual(cmd[bw_idx + 1], "1M")
        self.assertIn("--checksum", cmd)
        self.assertIn("--use-json-log", cmd)
        self.assertIn("RCLONE_SFTP_PASS", env)

    def test_build_command_directory(self):
        self.rclone.num_parallel_files = 8
        cmd, env = self.rclone._build_command(
            "Season 1", True, "/remote/downloads", "/local/staging"
        )
        self.assertEqual(cmd[0], "rclone")
        self.assertEqual(cmd[1], "copy")
        self.assertIn("--transfers", cmd)
        transfers_idx = cmd.index("--transfers")
        self.assertEqual(cmd[transfers_idx + 1], "8")
        # Should have --inplace since use_temp_file is False by default
        self.assertIn("--inplace", cmd)

    @patch("rclone.rclone.shutil.which", return_value="/usr/bin/rclone")
    @patch("rclone.rclone.subprocess.run")
    def test_build_command_ssh_key_auth(self, mock_run, mock_which):
        rclone = Rclone("host", 22, "user", None)
        rclone.set_base_remote_dir_path("/remote")
        rclone.set_base_local_dir_path("/local")
        cmd, env = rclone._build_command("file.txt", False, "/remote", "/local")
        self.assertIn("--sftp-key-file", cmd)
        self.assertNotIn("RCLONE_SFTP_PASS", env)
        rclone.exit()

    def test_status_empty(self):
        statuses = self.rclone.status()
        self.assertEqual(len(statuses), 0)

    def test_raise_pending_error_no_error(self):
        # Should not raise
        self.rclone.raise_pending_error()

    def test_extract_suffix(self):
        self.rclone.temp_file_name = "*.lftp"
        self.assertEqual(self.rclone._extract_suffix(), ".lftp")

    def test_extract_suffix_no_star(self):
        self.rclone.temp_file_name = ".partial"
        self.assertEqual(self.rclone._extract_suffix(), ".partial")

    def test_num_connections_validation(self):
        with self.assertRaises(ValueError):
            self.rclone.num_connections_per_root_file = 0
        with self.assertRaises(ValueError):
            self.rclone.num_connections_per_dir_file = 0
        with self.assertRaises(ValueError):
            self.rclone.num_parallel_files = 0
        with self.assertRaises(ValueError):
            self.rclone.num_max_total_connections = -1
