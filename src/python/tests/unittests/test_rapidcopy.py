# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
import sys
import copy
import tempfile

from common import overrides, Config
from common.path_pair import PathPair, PathPairManager
from rapidcopy import Rapidcopy


class TestRapidcopy(unittest.TestCase):
    def test_args_config(self):
        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Rapidcopy._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertEqual("/path/to/config", args.config_dir)

        argv = []
        argv.append("--config_dir")
        argv.append("/path/to/config")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Rapidcopy._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertEqual("/path/to/config", args.config_dir)

        argv = []
        with self.assertRaises(SystemExit):
            Rapidcopy._parse_args(argv)

    def test_args_html(self):
        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        argv.append("--html")
        argv.append("/path/to/html")
        args = Rapidcopy._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertEqual("/path/to/html", args.html)

    def test_args_scanfs(self):
        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Rapidcopy._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertEqual("/path/to/scanfs", args.scanfs)

    def test_args_logdir(self):
        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--logdir")
        argv.append("/path/to/logdir")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Rapidcopy._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertEqual("/path/to/logdir", args.logdir)

        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Rapidcopy._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertIsNone(args.logdir)

    def test_args_debug(self):
        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        argv.append("-d")
        args = Rapidcopy._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertTrue(args.debug)

        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--debug")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Rapidcopy._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertTrue(args.debug)

        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Rapidcopy._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertFalse(args.debug)

    def test_default_config(self):
        config = Rapidcopy._create_default_config()
        # Test that default config doesn't have any uninitialized values
        config_dict = config.as_dict()
        for section, inner_config in config_dict.items():
            for key in inner_config:
                self.assertIsNotNone(inner_config[key], msg="{}.{} is uninitialized".format(section, key))

        # Test that default config is a valid config
        config_dict = config.as_dict()
        config2 = Config.from_dict(config_dict)
        config2_dict = config2.as_dict()
        self.assertEqual(config_dict, config2_dict)

    def test_detect_incomplete_config(self):
        # Test a complete config - should return empty list
        config = Rapidcopy._create_default_config()
        incomplete_value = config.lftp.remote_address
        config.lftp.remote_address = "value"
        config.lftp.remote_password = "value"
        config.lftp.remote_username = "value"
        config.lftp.remote_path = "value"
        config.lftp.local_path = "value"
        config.lftp.remote_path_to_scan_script = "value"
        result = Rapidcopy._detect_incomplete_config(config)
        self.assertEqual(result, [])

        # Test incomplete configs - should return list with field name
        config.lftp.remote_address = incomplete_value
        result = Rapidcopy._detect_incomplete_config(config)
        self.assertEqual(len(result), 1)
        self.assertIn("Server Address", result)
        config.lftp.remote_address = "value"

        config.lftp.remote_username = incomplete_value
        result = Rapidcopy._detect_incomplete_config(config)
        self.assertEqual(len(result), 1)
        self.assertIn("Server Username", result)
        config.lftp.remote_username = "value"

        config.lftp.remote_path = incomplete_value
        result = Rapidcopy._detect_incomplete_config(config)
        self.assertEqual(len(result), 1)
        self.assertIn("Server Directory", result)
        config.lftp.remote_path = "value"

        config.lftp.local_path = incomplete_value
        result = Rapidcopy._detect_incomplete_config(config)
        self.assertEqual(len(result), 1)
        self.assertIn("Local Directory", result)
        config.lftp.local_path = "value"

        config.lftp.remote_path_to_scan_script = incomplete_value
        result = Rapidcopy._detect_incomplete_config(config)
        self.assertEqual(len(result), 1)
        self.assertIn("Remote Scan Script Path", result)
        config.lftp.remote_path_to_scan_script = "value"

    def test_detect_incomplete_config_multiple_fields(self):
        # Test that multiple incomplete fields are all returned
        config = Rapidcopy._create_default_config()
        # All fields are incomplete by default (have dummy values)
        result = Rapidcopy._detect_incomplete_config(config)
        # Should have at least the core fields
        self.assertIn("Server Address", result)
        self.assertIn("Server Username", result)
        self.assertIn("Server Password", result)
        self.assertIn("Server Directory", result)
        self.assertIn("Local Directory", result)

    def test_detect_incomplete_config_with_path_pairs(self):
        """Test that legacy path fields are skipped when path pairs are configured."""
        config = Rapidcopy._create_default_config()
        incomplete_value = config.lftp.remote_address

        # Configure required server fields but leave legacy paths incomplete
        config.lftp.remote_address = "server.example.com"
        config.lftp.remote_password = "password"
        config.lftp.remote_username = "user"
        config.lftp.remote_path_to_scan_script = "/tmp"
        # remote_path and local_path remain as "<replace me>"

        # Without path pairs, should still require legacy paths
        result = Rapidcopy._detect_incomplete_config(config)
        self.assertIn("Server Directory", result)
        self.assertIn("Local Directory", result)

        # Create a PathPairManager with configured path pairs
        with tempfile.TemporaryDirectory() as temp_dir:
            path_pair_manager = PathPairManager(temp_dir)
            path_pair_manager.load()

            # Add a path pair
            path_pair = PathPair(
                name="Test",
                remote_path="/remote/path",
                local_path="/local/path",
                enabled=True,
                auto_queue=True,
            )
            path_pair_manager.collection.add_pair(path_pair)

            # With path pairs configured, legacy paths should NOT be required
            result = Rapidcopy._detect_incomplete_config(config, path_pair_manager)
            self.assertNotIn("Server Directory", result)
            self.assertNotIn("Local Directory", result)
            # Should return empty list since all required fields are configured
            self.assertEqual(result, [])
