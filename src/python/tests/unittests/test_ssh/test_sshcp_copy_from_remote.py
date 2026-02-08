# Copyright 2024, SeedSync Contributors, All rights reserved.

import filecmp
import logging
import os
import shutil
import sys
import tempfile
import unittest

import timeout_decorator
from parameterized import parameterized

from common import overrides
from ssh import Sshcp, SshcpError
from tests.utils import TestUtils


# ===========================================================================
# Logging setup
# ===========================================================================
logger = logging.getLogger("test_sshcp_copy_from_remote")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# SSH test account credentials (must be set up per DeveloperReadme.md)
_PASSWORD = "seedsyncpass"
_PARAMS = [
    ("password", _PASSWORD),
    ("keyauth", None)
]


class TestSshcpCopyFromRemote(unittest.TestCase):
    """
    Tests for the Sshcp.copy_from_remote() method.
    Requires a local SSH server with the seedsynctest account.
    """
    __KEEP_FILES = False

    @overrides(unittest.TestCase)
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_sshcp_cfr")
        self.local_dir = os.path.join(self.temp_dir, "local")
        os.mkdir(self.local_dir)
        self.remote_dir = os.path.join(self.temp_dir, "remote")
        os.mkdir(self.remote_dir)

        # Allow group access for the seedsynctest account
        TestUtils.chmod_from_to(self.remote_dir, tempfile.gettempdir(), 0o775)
        TestUtils.chmod_from_to(self.local_dir, tempfile.gettempdir(), 0o775)

        self.host = "127.0.0.1"
        self.port = 22
        self.user = "seedsynctest"

        # Create a remote file (simulate a file on the "remote" server, accessible locally for test)
        self.remote_file = os.path.join(self.remote_dir, "source.txt")
        with open(self.remote_file, "w") as f:
            f.write("this is remote content for copy_from_remote test")

        self.local_file = os.path.join(self.local_dir, "destination.txt")

        logger.info("setUp: temp_dir=%s, remote_file=%s", self.temp_dir, self.remote_file)

    @overrides(unittest.TestCase)
    def tearDown(self):
        if not self.__KEEP_FILES:
            shutil.rmtree(self.temp_dir)
        logger.info("tearDown: cleaned up %s", self.temp_dir)

    @parameterized.expand(_PARAMS)
    @timeout_decorator.timeout(5)
    def test_copy_from_remote(self, _, password):
        """copy_from_remote successfully copies a remote file to local"""
        self.assertFalse(os.path.exists(self.local_file))
        sshcp = Sshcp(host=self.host, port=self.port, user=self.user, password=password)
        sshcp.copy_from_remote(remote_path=self.remote_file, local_path=self.local_file)

        self.assertTrue(os.path.exists(self.local_file))
        self.assertTrue(filecmp.cmp(self.remote_file, self.local_file))
        logger.info("test_copy_from_remote (%s): file copied successfully", _)

    @parameterized.expand(_PARAMS)
    @timeout_decorator.timeout(5)
    def test_copy_from_remote_binary_file(self, _, password):
        """copy_from_remote correctly handles binary files"""
        binary_content = os.urandom(4096)
        binary_remote = os.path.join(self.remote_dir, "binary.bin")
        with open(binary_remote, "wb") as f:
            f.write(binary_content)

        binary_local = os.path.join(self.local_dir, "binary_copy.bin")
        sshcp = Sshcp(host=self.host, port=self.port, user=self.user, password=password)
        sshcp.copy_from_remote(remote_path=binary_remote, local_path=binary_local)

        self.assertTrue(os.path.exists(binary_local))
        with open(binary_local, "rb") as f:
            copied_content = f.read()
        self.assertEqual(binary_content, copied_content)
        logger.info("test_copy_from_remote_binary_file (%s): binary file matches", _)

    @timeout_decorator.timeout(5)
    def test_copy_from_remote_error_bad_password(self):
        """copy_from_remote raises error on bad password"""
        sshcp = Sshcp(host=self.host, port=self.port, user=self.user, password="wrong password")
        with self.assertRaises(SshcpError) as ctx:
            sshcp.copy_from_remote(remote_path=self.remote_file, local_path=self.local_file)
        self.assertEqual("Incorrect password", str(ctx.exception))
        logger.info("test_copy_from_remote_error_bad_password: correctly raised SshcpError")

    @parameterized.expand(_PARAMS)
    @timeout_decorator.timeout(5)
    def test_copy_from_remote_error_missing_remote_file(self, _, password):
        """copy_from_remote raises error when remote file doesn't exist"""
        missing_remote = os.path.join(self.remote_dir, "nonexistent.txt")
        self.assertFalse(os.path.exists(missing_remote))

        sshcp = Sshcp(host=self.host, port=self.port, user=self.user, password=password)
        with self.assertRaises(SshcpError) as ctx:
            sshcp.copy_from_remote(remote_path=missing_remote, local_path=self.local_file)
        self.assertTrue("No such file or directory" in str(ctx.exception))
        logger.info("test_copy_from_remote_error_missing_remote_file (%s): error raised", _)

    @parameterized.expand(_PARAMS)
    @timeout_decorator.timeout(5)
    def test_copy_from_remote_error_bad_local_dir(self, _, password):
        """copy_from_remote raises error when local directory doesn't exist"""
        bad_local = os.path.join(self.local_dir, "nodir", "file.txt")

        sshcp = Sshcp(host=self.host, port=self.port, user=self.user, password=password)
        with self.assertRaises(SshcpError) as ctx:
            sshcp.copy_from_remote(remote_path=self.remote_file, local_path=bad_local)
        self.assertTrue("No such file or directory" in str(ctx.exception))
        logger.info("test_copy_from_remote_error_bad_local_dir (%s): error raised", _)

    @parameterized.expand(_PARAMS)
    @timeout_decorator.timeout(5)
    def test_copy_from_remote_error_bad_host(self, _, password):
        """copy_from_remote raises error on bad hostname"""
        sshcp = Sshcp(host="badhost", port=self.port, user=self.user, password=password)
        with self.assertRaises(SshcpError) as ctx:
            sshcp.copy_from_remote(remote_path=self.remote_file, local_path=self.local_file)
        self.assertTrue("Connection refused by server" in str(ctx.exception))
        logger.info("test_copy_from_remote_error_bad_host (%s): error raised", _)

    def test_copy_from_remote_empty_paths(self):
        """copy_from_remote raises ValueError on empty paths"""
        sshcp = Sshcp(host=self.host, port=self.port, user=self.user, password=_PASSWORD)
        with self.assertRaises(ValueError):
            sshcp.copy_from_remote(remote_path="", local_path=self.local_file)
        with self.assertRaises(ValueError):
            sshcp.copy_from_remote(remote_path=self.remote_file, local_path="")
        logger.info("test_copy_from_remote_empty_paths: ValueError raised correctly")

    @parameterized.expand(_PARAMS)
    @timeout_decorator.timeout(5)
    def test_copy_from_remote_overwrites_existing(self, _, password):
        """copy_from_remote overwrites an existing local file"""
        with open(self.local_file, "w") as f:
            f.write("old content that should be overwritten")

        sshcp = Sshcp(host=self.host, port=self.port, user=self.user, password=password)
        sshcp.copy_from_remote(remote_path=self.remote_file, local_path=self.local_file)

        self.assertTrue(filecmp.cmp(self.remote_file, self.local_file))
        logger.info("test_copy_from_remote_overwrites_existing (%s): file overwritten", _)
