# Copyright 2024, SeedSync Contributors, All rights reserved.
#
# End-to-end integration tests for the download validation feature.
# These tests use a real SSH server (seedsynctest account) and real
# filesystem operations to test the complete validation pipeline.
#
# Requirements:
#   - SSH server running on localhost port 22
#   - seedsynctest user account (see DeveloperReadme.md)
#   - Runs inside the Docker test container or with equivalent setup

import hashlib
import logging
import os
import shutil
import sys
import tempfile
import time
import unittest

import timeout_decorator
from parameterized import parameterized

from common import overrides
from controller.validate.validate_process import (
    ValidateProcess, ValidationResult, ValidationStatus, ChunkFailure
)
from ssh import Sshcp, SshcpError
from tests.utils import TestUtils


# ===========================================================================
# Logging setup
# ===========================================================================
logger = logging.getLogger("test_validate_e2e")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s [%(funcName)s:%(lineno)d] - %(message)s"
))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


# ===========================================================================
# Constants
# ===========================================================================
_PASSWORD = "seedsyncpass"
_HOST = "127.0.0.1"
_PORT = 22
_USER = "seedsynctest"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_file(path: str, content: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


# ===========================================================================
# E2E: Whole-file validation with real SSH
# ===========================================================================
class TestE2EWholeFileValidation(unittest.TestCase):
    """
    End-to-end tests for whole-file SHA256 validation.
    Uses real SSH connections to validate files between local and remote paths.
    """

    @overrides(unittest.TestCase)
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_e2e_validate_")
        self.local_path = os.path.join(self.temp_dir, "local")
        self.remote_path = os.path.join(self.temp_dir, "remote")
        os.makedirs(self.local_path)
        os.makedirs(self.remote_path)

        # Allow group access for seedsynctest
        TestUtils.chmod_from_to(self.remote_path, tempfile.gettempdir(), 0o775)
        TestUtils.chmod_from_to(self.local_path, tempfile.gettempdir(), 0o775)

        logger.info("E2E setUp: temp_dir=%s", self.temp_dir)

    @overrides(unittest.TestCase)
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        logger.info("E2E tearDown: cleaned up %s", self.temp_dir)

    @timeout_decorator.timeout(30)
    def test_e2e_single_file_matching(self):
        """
        E2E: Create identical files locally and remotely, validate passes.
        Tests the complete pipeline: file creation -> SSH hash -> comparison.
        """
        content = b"End-to-end test content for whole-file validation. " * 100
        _make_file(os.path.join(self.local_path, "data.bin"), content)
        _make_file(os.path.join(self.remote_path, "data.bin"), content)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="data.bin",
            is_dir=False,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=False
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=25)

        result = proc.pop_result()
        self.assertIsNotNone(result, "Process should produce a result")
        self.assertEqual(ValidationResult.Status.PASSED, result.status,
                         "Identical files should pass validation. Error: {}".format(
                             result.error_message))
        self.assertEqual("data.bin", result.file_name)
        self.assertFalse(result.is_dir)
        logger.info("test_e2e_single_file_matching: PASSED - hash matches via real SSH")

    @timeout_decorator.timeout(30)
    def test_e2e_single_file_mismatched(self):
        """
        E2E: Create different files locally and remotely, validate fails.
        """
        _make_file(os.path.join(self.local_path, "data.bin"), b"local content")
        _make_file(os.path.join(self.remote_path, "data.bin"), b"remote content")

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="data.bin",
            is_dir=False,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=False
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=25)

        result = proc.pop_result()
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.FAILED, result.status)
        self.assertIn("Checksum mismatch", result.error_message)
        logger.info("test_e2e_single_file_mismatched: FAILED correctly detected")

    @timeout_decorator.timeout(30)
    def test_e2e_directory_all_matching(self):
        """
        E2E: Create a directory with multiple files, all matching, validate passes.
        """
        files = {
            "a.txt": b"file a content\n" * 50,
            os.path.join("sub", "b.bin"): os.urandom(2048),
            os.path.join("sub", "deep", "c.dat"): b"deep file content" * 100,
        }

        for rel_path, content in files.items():
            _make_file(os.path.join(self.local_path, "mydir", rel_path), content)
            _make_file(os.path.join(self.remote_path, "mydir", rel_path), content)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="mydir",
            is_dir=True,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=False
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=25)

        result = proc.pop_result()
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status,
                         "Directory should pass. Error: {}".format(result.error_message))
        self.assertTrue(result.is_dir)
        logger.info("test_e2e_directory_all_matching: all %d files matched", len(files))

    @timeout_decorator.timeout(30)
    def test_e2e_directory_one_file_different(self):
        """
        E2E: Directory where one file differs - validation should fail.
        """
        common_content = b"same content"
        _make_file(os.path.join(self.local_path, "mydir", "same.txt"), common_content)
        _make_file(os.path.join(self.remote_path, "mydir", "same.txt"), common_content)

        _make_file(os.path.join(self.local_path, "mydir", "diff.txt"), b"local version")
        _make_file(os.path.join(self.remote_path, "mydir", "diff.txt"), b"remote version")

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="mydir",
            is_dir=True,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=False
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=25)

        result = proc.pop_result()
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.FAILED, result.status)
        self.assertIn("Checksum mismatch", result.error_message)
        logger.info("test_e2e_directory_one_file_different: mismatch detected in directory")

    @timeout_decorator.timeout(30)
    def test_e2e_large_file(self):
        """
        E2E: Validate a larger file (~100KB) to test buffered hashing.
        """
        content = os.urandom(102400)
        _make_file(os.path.join(self.local_path, "large.bin"), content)
        _make_file(os.path.join(self.remote_path, "large.bin"), content)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="large.bin",
            is_dir=False,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=False
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=25)

        result = proc.pop_result()
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status,
                         "Large file should pass. Error: {}".format(result.error_message))
        logger.info("test_e2e_large_file: 100KB file validated successfully")

    @timeout_decorator.timeout(30)
    def test_e2e_empty_directory(self):
        """
        E2E: Empty directory validation passes (no files to check).
        """
        empty_dir = os.path.join(self.local_path, "emptydir")
        os.makedirs(empty_dir)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="emptydir",
            is_dir=True,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=False
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=25)

        result = proc.pop_result()
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status)
        logger.info("test_e2e_empty_directory: empty dir validated as PASSED")

    @timeout_decorator.timeout(30)
    def test_e2e_bad_ssh_credentials(self):
        """
        E2E: Validation with wrong SSH credentials returns ERROR.
        """
        content = b"data"
        _make_file(os.path.join(self.local_path, "test.bin"), content)
        _make_file(os.path.join(self.remote_path, "test.bin"), content)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="test.bin",
            is_dir=False,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password="wrong_password",
            remote_port=_PORT,
            use_chunked=False
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=25)

        result = proc.pop_result()
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.ERROR, result.status)
        logger.info("test_e2e_bad_ssh_credentials: ERROR returned for bad password")


# ===========================================================================
# E2E: Chunked validation with real SSH
# ===========================================================================
class TestE2EChunkedValidation(unittest.TestCase):
    """
    End-to-end tests for chunked SHA256 validation with selective re-download.
    Uses real SSH connections and actual chunk hashing on remote server.
    """

    CHUNK_SIZE = 512  # small chunk size for faster testing

    @overrides(unittest.TestCase)
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_e2e_chunked_")
        self.local_path = os.path.join(self.temp_dir, "local")
        self.remote_path = os.path.join(self.temp_dir, "remote")
        os.makedirs(self.local_path)
        os.makedirs(self.remote_path)

        TestUtils.chmod_from_to(self.remote_path, tempfile.gettempdir(), 0o775)
        TestUtils.chmod_from_to(self.local_path, tempfile.gettempdir(), 0o775)

        logger.info("Chunked E2E setUp: temp_dir=%s, chunk_size=%d",
                     self.temp_dir, self.CHUNK_SIZE)

    @overrides(unittest.TestCase)
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        logger.info("Chunked E2E tearDown: cleaned up")

    @timeout_decorator.timeout(60)
    def test_e2e_chunked_matching_file(self):
        """
        E2E Chunked: Identical files pass chunked validation.
        """
        content = os.urandom(self.CHUNK_SIZE * 3 + 100)  # 3.5 chunks
        _make_file(os.path.join(self.local_path, "test.bin"), content)
        _make_file(os.path.join(self.remote_path, "test.bin"), content)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="test.bin",
            is_dir=False,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=55)

        result = proc.pop_result()
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status,
                         "Identical files should pass chunked validation. Error: {}".format(
                             result.error_message))
        logger.info("test_e2e_chunked_matching_file: PASSED with %d chunks",
                     (len(content) + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE)

    @timeout_decorator.timeout(60)
    def test_e2e_chunked_corrupt_chunk_repaired(self):
        """
        E2E Chunked: File with one corrupted chunk gets repaired automatically.
        The local file has one chunk different from remote - validation should
        detect it, repair it via SCP, and re-verify.
        """
        original_content = os.urandom(self.CHUNK_SIZE * 4)
        # Corrupt chunk 2 locally
        corrupted_content = bytearray(original_content)
        corrupt_start = self.CHUNK_SIZE * 2
        corrupt_end = self.CHUNK_SIZE * 3
        for i in range(corrupt_start, corrupt_end):
            corrupted_content[i] = (corrupted_content[i] + 1) % 256

        _make_file(os.path.join(self.local_path, "test.bin"), bytes(corrupted_content))
        _make_file(os.path.join(self.remote_path, "test.bin"), original_content)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="test.bin",
            is_dir=False,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=55)

        result = proc.pop_result()
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status,
                         "Corrupted chunk should be repaired. Error: {}".format(
                             result.error_message))
        self.assertGreaterEqual(result.chunks_repaired, 1,
                                "At least 1 chunk should have been repaired")

        # Verify the local file now matches the remote
        with open(os.path.join(self.local_path, "test.bin"), "rb") as f:
            repaired = f.read()
        self.assertEqual(original_content, repaired,
                         "Repaired file should match the original remote content")
        logger.info("test_e2e_chunked_corrupt_chunk_repaired: chunk repaired, "
                     "%d chunks repaired", result.chunks_repaired)

    @timeout_decorator.timeout(60)
    def test_e2e_chunked_multiple_corrupt_chunks(self):
        """
        E2E Chunked: File with multiple corrupted chunks all get repaired.
        """
        original_content = os.urandom(self.CHUNK_SIZE * 5)
        corrupted = bytearray(original_content)
        # Corrupt chunks 0 and 3
        for i in range(0, self.CHUNK_SIZE):
            corrupted[i] = (corrupted[i] + 1) % 256
        for i in range(self.CHUNK_SIZE * 3, self.CHUNK_SIZE * 4):
            corrupted[i] = (corrupted[i] + 1) % 256

        _make_file(os.path.join(self.local_path, "multi.bin"), bytes(corrupted))
        _make_file(os.path.join(self.remote_path, "multi.bin"), original_content)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="multi.bin",
            is_dir=False,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=55)

        result = proc.pop_result()
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status,
                         "All corrupt chunks should be repaired. Error: {}".format(
                             result.error_message))
        self.assertEqual(2, result.chunks_repaired)

        with open(os.path.join(self.local_path, "multi.bin"), "rb") as f:
            repaired = f.read()
        self.assertEqual(original_content, repaired)
        logger.info("test_e2e_chunked_multiple_corrupt_chunks: %d chunks repaired",
                     result.chunks_repaired)

    @timeout_decorator.timeout(60)
    def test_e2e_chunked_directory_matching(self):
        """
        E2E Chunked: Directory with multiple matching files passes chunked validation.
        """
        files = {
            "a.bin": os.urandom(self.CHUNK_SIZE * 2),
            os.path.join("sub", "b.bin"): os.urandom(self.CHUNK_SIZE + 10),
        }

        for rel_path, content in files.items():
            _make_file(os.path.join(self.local_path, "mydir", rel_path), content)
            _make_file(os.path.join(self.remote_path, "mydir", rel_path), content)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="mydir",
            is_dir=True,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=55)

        result = proc.pop_result()
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status,
                         "Matching directory should pass. Error: {}".format(
                             result.error_message))
        self.assertTrue(result.is_dir)
        logger.info("test_e2e_chunked_directory_matching: directory with %d files passed",
                     len(files))

    @timeout_decorator.timeout(60)
    def test_e2e_chunked_directory_repair(self):
        """
        E2E Chunked: Directory with one corrupted file chunk gets repaired.
        """
        good_content = os.urandom(self.CHUNK_SIZE)
        bad_original = os.urandom(self.CHUNK_SIZE * 2)
        bad_corrupted = bytearray(bad_original)
        for i in range(0, self.CHUNK_SIZE):
            bad_corrupted[i] = (bad_corrupted[i] + 1) % 256

        _make_file(os.path.join(self.local_path, "mydir", "good.bin"), good_content)
        _make_file(os.path.join(self.remote_path, "mydir", "good.bin"), good_content)

        _make_file(os.path.join(self.local_path, "mydir", "bad.bin"), bytes(bad_corrupted))
        _make_file(os.path.join(self.remote_path, "mydir", "bad.bin"), bad_original)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="mydir",
            is_dir=True,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=55)

        result = proc.pop_result()
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status,
                         "Corrupted chunk in directory should be repaired. Error: {}".format(
                             result.error_message))
        self.assertGreaterEqual(result.chunks_repaired, 1)

        with open(os.path.join(self.local_path, "mydir", "bad.bin"), "rb") as f:
            repaired = f.read()
        self.assertEqual(bad_original, repaired)
        logger.info("test_e2e_chunked_directory_repair: directory chunk repaired")

    @timeout_decorator.timeout(60)
    def test_e2e_chunked_single_chunk_file(self):
        """
        E2E Chunked: File smaller than chunk size validates correctly.
        """
        content = b"small file" * 5  # Much smaller than CHUNK_SIZE
        _make_file(os.path.join(self.local_path, "small.bin"), content)
        _make_file(os.path.join(self.remote_path, "small.bin"), content)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="small.bin",
            is_dir=False,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=55)

        result = proc.pop_result()
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status,
                         "Small file should pass chunked validation. Error: {}".format(
                             result.error_message))
        logger.info("test_e2e_chunked_single_chunk_file: sub-chunk-size file passed")

    @timeout_decorator.timeout(60)
    def test_e2e_chunked_last_chunk_partial(self):
        """
        E2E Chunked: File whose size is not a multiple of chunk size validates correctly.
        """
        # File size = 2.5 chunks
        content = os.urandom(self.CHUNK_SIZE * 2 + self.CHUNK_SIZE // 2)
        _make_file(os.path.join(self.local_path, "partial.bin"), content)
        _make_file(os.path.join(self.remote_path, "partial.bin"), content)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="partial.bin",
            is_dir=False,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.set_base_logger(logger)
        proc.start()
        proc.join(timeout=55)

        result = proc.pop_result()
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status,
                         "Partial last chunk should pass. Error: {}".format(
                             result.error_message))
        logger.info("test_e2e_chunked_last_chunk_partial: partial chunk validated ok")


# ===========================================================================
# E2E: Workflow simulation tests
# ===========================================================================
class TestE2EValidationWorkflow(unittest.TestCase):
    """
    Simulates the full validation workflow as it would occur during
    a real download: file arrives -> validation triggered -> result handled.
    """

    @overrides(unittest.TestCase)
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_e2e_workflow_")
        self.local_path = os.path.join(self.temp_dir, "local")
        self.remote_path = os.path.join(self.temp_dir, "remote")
        os.makedirs(self.local_path)
        os.makedirs(self.remote_path)

        TestUtils.chmod_from_to(self.remote_path, tempfile.gettempdir(), 0o775)
        TestUtils.chmod_from_to(self.local_path, tempfile.gettempdir(), 0o775)

        logger.info("Workflow E2E setUp: %s", self.temp_dir)

    @overrides(unittest.TestCase)
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @timeout_decorator.timeout(30)
    def test_workflow_pass_no_redownload(self):
        """
        Workflow: file passes validation -> no redownload needed.
        Simulates what the controller does when validation succeeds.
        """
        content = b"perfect download" * 100
        _make_file(os.path.join(self.local_path, "file.bin"), content)
        _make_file(os.path.join(self.remote_path, "file.bin"), content)

        # Step 1: Start validation (as controller would)
        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="file.bin",
            is_dir=False,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=False
        )
        proc.set_base_logger(logger)
        proc.start()

        # Step 2: Poll for result (as controller.process() loop would)
        result = None
        for _ in range(50):
            if not proc.is_alive():
                result = proc.pop_result()
                break
            time.sleep(0.1)

        # Step 3: Check result (as __check_validation_results would)
        self.assertIsNotNone(result, "Should receive result within timeout")
        self.assertEqual(ValidationResult.Status.PASSED, result.status)

        # Step 4: Verify file still exists (no delete/requeue)
        self.assertTrue(os.path.exists(os.path.join(self.local_path, "file.bin")))
        logger.info("test_workflow_pass_no_redownload: workflow completed - no redownload")

    @timeout_decorator.timeout(30)
    def test_workflow_fail_triggers_redownload(self):
        """
        Workflow: file fails validation -> local file deleted -> redownload logic.
        Simulates what the controller does when validation fails.
        """
        _make_file(os.path.join(self.local_path, "file.bin"), b"corrupted local data")
        _make_file(os.path.join(self.remote_path, "file.bin"), b"correct remote data")

        # Step 1: Start validation
        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="file.bin",
            is_dir=False,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=False
        )
        proc.set_base_logger(logger)
        proc.start()

        # Step 2: Poll for result
        result = None
        for _ in range(50):
            if not proc.is_alive():
                result = proc.pop_result()
                break
            time.sleep(0.1)

        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.FAILED, result.status)

        # Step 3: Simulate controller's __delete_local_and_requeue behavior
        local_file_path = os.path.join(self.local_path, "file.bin")
        self.assertTrue(os.path.exists(local_file_path))
        os.remove(local_file_path)
        self.assertFalse(os.path.exists(local_file_path))

        logger.info("test_workflow_fail_triggers_redownload: "
                     "validation failed, local file deleted, ready for requeue")

    @timeout_decorator.timeout(60)
    def test_workflow_chunked_repair_no_redownload(self):
        """
        Workflow: chunked validation detects corruption, repairs in-place,
        no full redownload needed.
        """
        chunk_size = 512
        original = os.urandom(chunk_size * 3)
        corrupted = bytearray(original)
        for i in range(chunk_size, chunk_size * 2):
            corrupted[i] = (corrupted[i] + 1) % 256

        _make_file(os.path.join(self.local_path, "file.bin"), bytes(corrupted))
        _make_file(os.path.join(self.remote_path, "file.bin"), original)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="file.bin",
            is_dir=False,
            remote_address=_HOST,
            remote_username=_USER,
            remote_password=_PASSWORD,
            remote_port=_PORT,
            use_chunked=True,
            chunk_size_bytes=chunk_size
        )
        proc.set_base_logger(logger)
        proc.start()

        result = None
        for _ in range(100):
            if not proc.is_alive():
                result = proc.pop_result()
                break
            time.sleep(0.1)

        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status,
                         "Chunk repair should fix the file. Error: {}".format(
                             result.error_message))
        self.assertGreaterEqual(result.chunks_repaired, 1)

        # Verify file is now correct without needing a full redownload
        with open(os.path.join(self.local_path, "file.bin"), "rb") as f:
            final_content = f.read()
        self.assertEqual(original, final_content)
        logger.info("test_workflow_chunked_repair_no_redownload: "
                     "repaired in-place, full redownload avoided")

    @timeout_decorator.timeout(30)
    def test_workflow_retry_counting(self):
        """
        Workflow: Simulate retry counting as controller would manage it.
        """
        retry_counts = {}
        max_retries = 3

        _make_file(os.path.join(self.local_path, "file.bin"), b"bad")
        _make_file(os.path.join(self.remote_path, "file.bin"), b"good")

        for attempt in range(max_retries + 1):
            proc = ValidateProcess(
                local_path=self.local_path,
                remote_path=self.remote_path,
                file_name="file.bin",
                is_dir=False,
                remote_address=_HOST,
                remote_username=_USER,
                remote_password=_PASSWORD,
                remote_port=_PORT,
                use_chunked=False
            )
            proc.set_base_logger(logger)
            proc.start()
            proc.join(timeout=25)

            result = proc.pop_result()
            self.assertIsNotNone(result)
            self.assertEqual(ValidationResult.Status.FAILED, result.status)

            retry_count = retry_counts.get("file.bin", 0)
            if retry_count < max_retries:
                retry_counts["file.bin"] = retry_count + 1
                logger.info("  Attempt %d/%d: would delete and re-queue",
                            retry_count + 1, max_retries)
            else:
                logger.info("  Attempt %d: max retries reached, giving up",
                            retry_count + 1)
                break

        # After max_retries attempts, should have retried exactly max_retries times
        self.assertEqual(max_retries, retry_counts["file.bin"])
        logger.info("test_workflow_retry_counting: "
                     "correctly tracked %d retries", max_retries)
