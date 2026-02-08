# Copyright 2024, SeedSync Contributors, All rights reserved.

import logging
import os
import sys
import tempfile
import unittest

from common import Config, ConfigError


# ===========================================================================
# Logging setup
# ===========================================================================
logger = logging.getLogger("test_config_validation")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class TestControllerValidationConfig(unittest.TestCase):
    """Tests for the new validation config properties in Config.Controller"""

    def _make_good_dict(self):
        """Return a complete valid Controller config dict including validation fields"""
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
        }

    def test_validation_fields_from_dict(self):
        """Validation config fields are parsed correctly from dict"""
        good_dict = self._make_good_dict()
        controller = Config.Controller.from_dict(good_dict)

        self.assertEqual(True, controller.enable_download_validation)
        self.assertEqual(3, controller.download_validation_max_retries)
        self.assertEqual(False, controller.use_chunked_validation)
        self.assertEqual(4, controller.validation_chunk_size_mb)
        logger.info("test_validation_fields_from_dict: all fields parsed correctly")

    def test_enable_download_validation_bool(self):
        """enable_download_validation accepts True/False"""
        d = self._make_good_dict()

        d["enable_download_validation"] = "True"
        c = Config.Controller.from_dict(d)
        self.assertTrue(c.enable_download_validation)

        d["enable_download_validation"] = "False"
        c = Config.Controller.from_dict(d)
        self.assertFalse(c.enable_download_validation)

        d["enable_download_validation"] = "1"
        c = Config.Controller.from_dict(d)
        self.assertTrue(c.enable_download_validation)

        d["enable_download_validation"] = "0"
        c = Config.Controller.from_dict(d)
        self.assertFalse(c.enable_download_validation)

    def test_enable_download_validation_bad_value(self):
        """enable_download_validation rejects non-boolean values"""
        d = self._make_good_dict()
        d["enable_download_validation"] = "SomeString"
        with self.assertRaises(ConfigError) as ctx:
            Config.Controller.from_dict(d)
        self.assertTrue(str(ctx.exception).startswith("Bad config"))
        logger.info("test_enable_download_validation_bad_value: error raised correctly")

    def test_download_validation_max_retries_int(self):
        """download_validation_max_retries accepts positive integers"""
        d = self._make_good_dict()
        d["download_validation_max_retries"] = "5"
        c = Config.Controller.from_dict(d)
        self.assertEqual(5, c.download_validation_max_retries)

    def test_download_validation_max_retries_bad_values(self):
        """download_validation_max_retries rejects non-positive values"""
        d = self._make_good_dict()

        d["download_validation_max_retries"] = "-1"
        with self.assertRaises(ConfigError):
            Config.Controller.from_dict(d)

        d["download_validation_max_retries"] = "0"
        with self.assertRaises(ConfigError):
            Config.Controller.from_dict(d)

        d["download_validation_max_retries"] = "abc"
        with self.assertRaises(ConfigError):
            Config.Controller.from_dict(d)

        logger.info("test_download_validation_max_retries_bad_values: all bad values rejected")

    def test_use_chunked_validation_bool(self):
        """use_chunked_validation accepts True/False"""
        d = self._make_good_dict()

        d["use_chunked_validation"] = "True"
        c = Config.Controller.from_dict(d)
        self.assertTrue(c.use_chunked_validation)

        d["use_chunked_validation"] = "False"
        c = Config.Controller.from_dict(d)
        self.assertFalse(c.use_chunked_validation)

    def test_use_chunked_validation_bad_value(self):
        """use_chunked_validation rejects non-boolean values"""
        d = self._make_good_dict()
        d["use_chunked_validation"] = "NotABool"
        with self.assertRaises(ConfigError):
            Config.Controller.from_dict(d)

    def test_validation_chunk_size_mb_int(self):
        """validation_chunk_size_mb accepts positive integers"""
        d = self._make_good_dict()
        d["validation_chunk_size_mb"] = "8"
        c = Config.Controller.from_dict(d)
        self.assertEqual(8, c.validation_chunk_size_mb)

    def test_validation_chunk_size_mb_bad_values(self):
        """validation_chunk_size_mb rejects non-positive values"""
        d = self._make_good_dict()

        d["validation_chunk_size_mb"] = "-1"
        with self.assertRaises(ConfigError):
            Config.Controller.from_dict(d)

        d["validation_chunk_size_mb"] = "0"
        with self.assertRaises(ConfigError):
            Config.Controller.from_dict(d)

        d["validation_chunk_size_mb"] = "abc"
        with self.assertRaises(ConfigError):
            Config.Controller.from_dict(d)

        logger.info("test_validation_chunk_size_mb_bad_values: all bad values rejected")

    def test_missing_validation_fields_error(self):
        """Missing validation fields cause ConfigError"""
        d = self._make_good_dict()

        for key in ["enable_download_validation", "download_validation_max_retries",
                     "use_chunked_validation", "validation_chunk_size_mb"]:
            test_dict = dict(d)
            del test_dict[key]
            with self.assertRaises(ConfigError) as ctx:
                Config.Controller.from_dict(test_dict)
            self.assertTrue(str(ctx.exception).startswith("Missing config"),
                            "Expected 'Missing config' error for key '{}', got: {}".format(
                                key, str(ctx.exception)))
            logger.info("test_missing_validation_fields_error: '%s' missing correctly detected", key)

    def test_from_file_with_validation_fields(self):
        """Config can be read from INI file with validation fields"""
        config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False)
        try:
            config_file.write("""
[General]
debug=False
verbose=True

[Lftp]
remote_address=remote.server.com
remote_username=remote-user
remote_password=remote-pass
remote_port=3456
remote_path=/path/on/remote/server
local_path=/path/on/local/server
remote_path_to_scan_script=/path/on/remote/server/to/scan/script
use_ssh_key=False
num_max_parallel_downloads=2
num_max_parallel_files_per_download=3
num_max_connections_per_root_file=4
num_max_connections_per_dir_file=5
num_max_total_connections=7
use_temp_file=False

[Controller]
interval_ms_remote_scan=30000
interval_ms_local_scan=10000
interval_ms_downloading_scan=2000
extract_path=/path/where/to/extract/stuff
use_local_path_as_extract_path=False
enable_download_validation=True
download_validation_max_retries=5
use_chunked_validation=True
validation_chunk_size_mb=8

[Web]
port=88

[AutoQueue]
enabled=False
patterns_only=True
auto_extract=True
            """)
            config_file.flush()
            config_file.close()

            config = Config.from_file(config_file.name)

            self.assertEqual(True, config.controller.enable_download_validation)
            self.assertEqual(5, config.controller.download_validation_max_retries)
            self.assertEqual(True, config.controller.use_chunked_validation)
            self.assertEqual(8, config.controller.validation_chunk_size_mb)

            logger.info("test_from_file_with_validation_fields: file parsed successfully")
        finally:
            os.remove(config_file.name)

    def test_default_config_values(self):
        """Config defaults are set correctly for validation properties"""
        controller = Config.Controller()
        self.assertIsNone(controller.enable_download_validation)
        self.assertIsNone(controller.download_validation_max_retries)
        self.assertIsNone(controller.use_chunked_validation)
        self.assertIsNone(controller.validation_chunk_size_mb)
        logger.info("test_default_config_values: all defaults are None as expected")
