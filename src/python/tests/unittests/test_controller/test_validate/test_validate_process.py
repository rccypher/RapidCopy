# Copyright 2024, SeedSync Contributors, All rights reserved.

import hashlib
import logging
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call

from controller.validate.validate_process import (
    ValidateProcess, ValidationResult, ValidationStatus, ChunkFailure
)
from ssh import SshcpError


# ===========================================================================
# Logging setup for all tests
# ===========================================================================
logger = logging.getLogger("test_validate_process")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


# ===========================================================================
# Helper utilities
# ===========================================================================
def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_file(path: str, content: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


def _pop_result_blocking(proc, timeout=2.0):
    """
    Pop result from a ValidateProcess, retrying briefly since
    multiprocessing.Queue.put() is asynchronous and may not be
    immediately visible to get().
    """
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = proc.pop_result()
        if result is not None:
            return result
        time.sleep(0.05)
    return None


# ===========================================================================
# Data model unit tests
# ===========================================================================
class TestChunkFailure(unittest.TestCase):
    """Tests for the ChunkFailure data class"""

    def test_attributes(self):
        cf = ChunkFailure(
            file_path="/local/file.bin",
            chunk_index=3,
            chunk_offset=3072,
            chunk_size=1024
        )
        self.assertEqual("/local/file.bin", cf.file_path)
        self.assertEqual(3, cf.chunk_index)
        self.assertEqual(3072, cf.chunk_offset)
        self.assertEqual(1024, cf.chunk_size)
        self.assertIsNone(cf.remote_file_path)

    def test_remote_file_path_settable(self):
        cf = ChunkFailure("/local/file.bin", 0, 0, 1024)
        cf.remote_file_path = "/remote/file.bin"
        self.assertEqual("/remote/file.bin", cf.remote_file_path)


class TestValidationResult(unittest.TestCase):
    """Tests for the ValidationResult data class"""

    def test_passed_result(self):
        result = ValidationResult(
            file_name="test.bin",
            is_dir=False,
            status=ValidationResult.Status.PASSED
        )
        self.assertEqual("test.bin", result.file_name)
        self.assertFalse(result.is_dir)
        self.assertEqual(ValidationResult.Status.PASSED, result.status)
        self.assertIsNone(result.error_message)
        self.assertEqual([], result.failed_chunks)
        self.assertEqual(0, result.chunks_repaired)

    def test_failed_result_with_chunks(self):
        chunks = [ChunkFailure("/f", 0, 0, 1024), ChunkFailure("/f", 1, 1024, 1024)]
        result = ValidationResult(
            file_name="test.bin",
            is_dir=False,
            status=ValidationResult.Status.FAILED,
            error_message="mismatch",
            failed_chunks=chunks,
            chunks_repaired=1
        )
        self.assertEqual(ValidationResult.Status.FAILED, result.status)
        self.assertEqual("mismatch", result.error_message)
        self.assertEqual(2, len(result.failed_chunks))
        self.assertEqual(1, result.chunks_repaired)

    def test_error_result(self):
        result = ValidationResult(
            file_name="dir",
            is_dir=True,
            status=ValidationResult.Status.ERROR,
            error_message="Something went wrong"
        )
        self.assertEqual(ValidationResult.Status.ERROR, result.status)
        self.assertTrue(result.is_dir)
        self.assertEqual("Something went wrong", result.error_message)

    def test_status_enum_values(self):
        self.assertEqual(0, ValidationResult.Status.PASSED.value)
        self.assertEqual(1, ValidationResult.Status.FAILED.value)
        self.assertEqual(2, ValidationResult.Status.ERROR.value)


class TestValidationStatus(unittest.TestCase):
    """Tests for the ValidationStatus data class"""

    def test_init(self):
        vs = ValidationStatus(name="myfile", is_dir=True)
        self.assertEqual("myfile", vs.name)
        self.assertTrue(vs.is_dir)
        self.assertEqual(ValidationStatus.State.VALIDATING, vs.state)

    def test_state_enum(self):
        self.assertEqual(0, ValidationStatus.State.VALIDATING.value)


# ===========================================================================
# ValidateProcess unit tests (with mocked SSH)
# ===========================================================================
class TestValidateProcessWholeFile(unittest.TestCase):
    """Tests for whole-file SHA256 validation mode"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_validate_")
        self.local_path = os.path.join(self.temp_dir, "local")
        self.remote_path = os.path.join(self.temp_dir, "remote")
        os.makedirs(self.local_path)
        os.makedirs(self.remote_path)

        logger.info("Test setUp: temp_dir=%s", self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        logger.info("Test tearDown: cleaned up %s", self.temp_dir)

    def test_constructor_properties(self):
        """Test that file_name and is_dir properties are exposed correctly"""
        proc = ValidateProcess(
            local_path="/local",
            remote_path="/remote",
            file_name="test.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22
        )
        self.assertEqual("test.bin", proc.file_name)
        self.assertFalse(proc.is_dir)

    def test_constructor_properties_dir(self):
        proc = ValidateProcess(
            local_path="/local",
            remote_path="/remote",
            file_name="mydir",
            is_dir=True,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22
        )
        self.assertEqual("mydir", proc.file_name)
        self.assertTrue(proc.is_dir)

    def test_pop_result_empty(self):
        """pop_result returns None when no result is available"""
        proc = ValidateProcess(
            local_path="/local",
            remote_path="/remote",
            file_name="test.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22
        )
        self.assertIsNone(proc.pop_result())

    @patch("controller.validate.validate_process.Sshcp")
    def test_whole_file_pass(self, mock_sshcp_cls):
        """Whole-file validation passes when local and remote hashes match"""
        content = b"Hello, this is test data for validation."
        local_file = os.path.join(self.local_path, "test.bin")
        _make_file(local_file, content)

        expected_hash = _sha256(content)
        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.return_value = "{}\n".format(expected_hash).encode()

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="test.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=False
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status)
        self.assertEqual("test.bin", result.file_name)
        self.assertFalse(result.is_dir)
        self.assertIsNone(result.error_message)
        logger.info("test_whole_file_pass: PASSED - hash=%s", expected_hash)

    @patch("controller.validate.validate_process.Sshcp")
    def test_whole_file_fail(self, mock_sshcp_cls):
        """Whole-file validation fails when hashes don't match"""
        content = b"Local content"
        local_file = os.path.join(self.local_path, "test.bin")
        _make_file(local_file, content)

        fake_remote_hash = "a" * 64
        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.return_value = "{}\n".format(fake_remote_hash).encode()

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="test.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=False
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.FAILED, result.status)
        self.assertIn("Checksum mismatch", result.error_message)
        logger.info("test_whole_file_fail: correctly detected mismatch")

    @patch("controller.validate.validate_process.Sshcp")
    def test_whole_file_missing_local(self, mock_sshcp_cls):
        """Whole-file validation returns ERROR when local file doesn't exist"""
        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="nonexistent.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=False
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.ERROR, result.status)
        self.assertIn("Local file not found", result.error_message)
        logger.info("test_whole_file_missing_local: correctly returned ERROR")

    @patch("controller.validate.validate_process.Sshcp")
    def test_whole_file_remote_ssh_error(self, mock_sshcp_cls):
        """Whole-file validation returns ERROR when remote hash computation fails"""
        content = b"Some data"
        local_file = os.path.join(self.local_path, "test.bin")
        _make_file(local_file, content)

        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.side_effect = SshcpError("Connection refused")

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="test.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=False
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.ERROR, result.status)
        self.assertIn("remote SHA256", result.error_message)
        logger.info("test_whole_file_remote_ssh_error: correctly returned ERROR")


class TestValidateProcessWholeDirectory(unittest.TestCase):
    """Tests for whole-file directory validation mode"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_validate_dir_")
        self.local_path = os.path.join(self.temp_dir, "local")
        self.remote_path = os.path.join(self.temp_dir, "remote")
        os.makedirs(self.local_path)
        os.makedirs(self.remote_path)
        logger.info("TestValidateProcessWholeDirectory setUp: %s", self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("controller.validate.validate_process.Sshcp")
    def test_directory_pass(self, mock_sshcp_cls):
        """Directory validation passes when all file hashes match"""
        dir_path = os.path.join(self.local_path, "mydir")
        os.makedirs(dir_path)

        file1_content = b"file1 content"
        file2_content = b"file2 content"
        _make_file(os.path.join(dir_path, "a.txt"), file1_content)
        _make_file(os.path.join(dir_path, "sub", "b.txt"), file2_content)

        # Mock SSH to return correct hashes for each file queried
        def shell_side_effect(cmd):
            if "a.txt" in cmd:
                return "{}\n".format(_sha256(file1_content)).encode()
            elif "b.txt" in cmd:
                return "{}\n".format(_sha256(file2_content)).encode()
            return b""

        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.side_effect = shell_side_effect

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="mydir",
            is_dir=True,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=False
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status)
        self.assertTrue(result.is_dir)
        logger.info("test_directory_pass: all files validated successfully")

    @patch("controller.validate.validate_process.Sshcp")
    def test_directory_fail_one_file(self, mock_sshcp_cls):
        """Directory validation fails when one file's hash doesn't match"""
        dir_path = os.path.join(self.local_path, "mydir")
        os.makedirs(dir_path)

        file1_content = b"file1 content"
        file2_content = b"file2 content"
        _make_file(os.path.join(dir_path, "a.txt"), file1_content)
        _make_file(os.path.join(dir_path, "b.txt"), file2_content)

        def shell_side_effect(cmd):
            if "a.txt" in cmd:
                return "{}\n".format(_sha256(file1_content)).encode()
            elif "b.txt" in cmd:
                return "{}\n".format("b" * 64).encode()  # wrong hash
            return b""

        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.side_effect = shell_side_effect

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="mydir",
            is_dir=True,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=False
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.FAILED, result.status)
        self.assertIn("Checksum mismatch", result.error_message)
        logger.info("test_directory_fail_one_file: detected mismatch in directory")

    @patch("controller.validate.validate_process.Sshcp")
    def test_directory_missing_local(self, mock_sshcp_cls):
        """Directory validation returns ERROR when local directory doesn't exist"""
        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="nodir",
            is_dir=True,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=False
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.ERROR, result.status)
        self.assertIn("Local directory not found", result.error_message)

    @patch("controller.validate.validate_process.Sshcp")
    def test_directory_empty_passes(self, mock_sshcp_cls):
        """Directory validation passes if directory exists but has no files"""
        dir_path = os.path.join(self.local_path, "emptydir")
        os.makedirs(dir_path)

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="emptydir",
            is_dir=True,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=False
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status)

    @patch("controller.validate.validate_process.Sshcp")
    def test_directory_skips_lftp_temp_files(self, mock_sshcp_cls):
        """Directory validation skips .lftp and .lftp-pget-status files"""
        dir_path = os.path.join(self.local_path, "mydir")
        os.makedirs(dir_path)

        real_content = b"real file"
        _make_file(os.path.join(dir_path, "real.txt"), real_content)
        _make_file(os.path.join(dir_path, "temp.lftp"), b"temp data")
        _make_file(os.path.join(dir_path, "temp.lftp-pget-status"), b"status data")

        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.return_value = "{}\n".format(_sha256(real_content)).encode()

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="mydir",
            is_dir=True,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=False
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status)
        # Should have only called shell once (for real.txt)
        self.assertEqual(1, mock_ssh.shell.call_count)
        logger.info("test_directory_skips_lftp_temp_files: correctly skipped temp files")

    @patch("controller.validate.validate_process.Sshcp")
    def test_directory_remote_error(self, mock_sshcp_cls):
        """Directory validation returns ERROR when SSH fails mid-validation"""
        dir_path = os.path.join(self.local_path, "mydir")
        os.makedirs(dir_path)
        _make_file(os.path.join(dir_path, "a.txt"), b"data")

        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.side_effect = SshcpError("Connection lost")

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="mydir",
            is_dir=True,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=False
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.ERROR, result.status)
        self.assertIn("remote SHA256", result.error_message)


# ===========================================================================
# Chunked validation unit tests
# ===========================================================================
class TestValidateProcessChunkedFile(unittest.TestCase):
    """Tests for per-chunk SHA256 validation and selective re-download"""

    CHUNK_SIZE = 64  # small chunk size for testing

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_validate_chunk_")
        self.local_path = os.path.join(self.temp_dir, "local")
        self.remote_path = os.path.join(self.temp_dir, "remote")
        os.makedirs(self.local_path)
        os.makedirs(self.remote_path)
        logger.info("TestValidateProcessChunkedFile setUp: %s", self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("controller.validate.validate_process.Sshcp")
    def test_chunked_file_pass(self, mock_sshcp_cls):
        """Chunked validation passes when all chunk hashes match"""
        # Create a file with 3 chunks worth of data
        content = b"A" * self.CHUNK_SIZE + b"B" * self.CHUNK_SIZE + b"C" * 32
        local_file = os.path.join(self.local_path, "test.bin")
        _make_file(local_file, content)

        # Build remote hash output that matches local
        chunk_hashes = []
        for i in range(3):
            start = i * self.CHUNK_SIZE
            end = min(start + self.CHUNK_SIZE, len(content))
            h = _sha256(content[start:end])
            chunk_hashes.append("{} {}".format(i, h))

        remote_output = "\n".join(chunk_hashes) + "\n"

        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.return_value = remote_output.encode()

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="test.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status)
        self.assertEqual(0, result.chunks_repaired)
        logger.info("test_chunked_file_pass: all chunks validated")

    @patch("controller.validate.validate_process.Sshcp")
    def test_chunked_file_fail_repair_success(self, mock_sshcp_cls):
        """Chunked validation detects bad chunk, repairs it, re-verifies"""
        correct_content = b"A" * self.CHUNK_SIZE + b"B" * self.CHUNK_SIZE
        corrupted_content = b"A" * self.CHUNK_SIZE + b"X" * self.CHUNK_SIZE
        local_file = os.path.join(self.local_path, "test.bin")
        _make_file(local_file, corrupted_content)

        correct_chunk0_hash = _sha256(correct_content[:self.CHUNK_SIZE])
        correct_chunk1_hash = _sha256(correct_content[self.CHUNK_SIZE:])

        call_count = {"shell": 0}

        def shell_side_effect(cmd):
            call_count["shell"] += 1
            # Chunk hash commands
            if "sha256sum" in cmd and "while" in cmd:
                return "{} {}\n{} {}\n".format(
                    0, correct_chunk0_hash,
                    1, correct_chunk1_hash
                ).encode()
            # dd command for chunk extraction
            if "dd if=" in cmd and "of=" in cmd:
                return b""
            # rm cleanup command
            if "rm -f" in cmd:
                return b""
            return b""

        def copy_from_remote_side_effect(remote_path, local_path):
            # Write the correct chunk data to local_path
            with open(local_path, "wb") as f:
                f.write(correct_content[self.CHUNK_SIZE:])

        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.side_effect = shell_side_effect
        mock_ssh.copy_from_remote.side_effect = copy_from_remote_side_effect

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="test.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        # After repair, chunk 1 should now match, so re-verify passes
        self.assertEqual(ValidationResult.Status.PASSED, result.status)
        self.assertEqual(1, result.chunks_repaired)
        logger.info("test_chunked_file_fail_repair_success: repaired chunk verified")

    @patch("controller.validate.validate_process.Sshcp")
    def test_chunked_file_missing_local(self, mock_sshcp_cls):
        """Chunked validation returns ERROR when local file doesn't exist"""
        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="missing.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.ERROR, result.status)
        self.assertIn("Local file not found", result.error_message)

    @patch("controller.validate.validate_process.Sshcp")
    def test_chunked_file_remote_hash_error(self, mock_sshcp_cls):
        """Chunked validation returns ERROR when remote chunk hashing fails"""
        content = b"A" * self.CHUNK_SIZE
        local_file = os.path.join(self.local_path, "test.bin")
        _make_file(local_file, content)

        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.side_effect = SshcpError("Network error")

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="test.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.ERROR, result.status)
        self.assertIn("chunk hashes", result.error_message)

    @patch("controller.validate.validate_process.Sshcp")
    def test_chunked_repair_failure(self, mock_sshcp_cls):
        """Chunked validation reports FAILED when repair itself fails"""
        content = b"A" * self.CHUNK_SIZE + b"B" * self.CHUNK_SIZE
        local_file = os.path.join(self.local_path, "test.bin")
        _make_file(local_file, content)

        correct_hash = _sha256(b"C" * self.CHUNK_SIZE)  # different from local
        local_hash0 = _sha256(content[:self.CHUNK_SIZE])

        def shell_side_effect(cmd):
            if "sha256sum" in cmd and "while" in cmd:
                return "{} {}\n{} {}\n".format(
                    0, local_hash0,
                    1, correct_hash  # chunk 1 differs
                ).encode()
            if "dd if=" in cmd and "of=" in cmd:
                raise SshcpError("dd failed")
            if "rm -f" in cmd:
                return b""
            return b""

        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.side_effect = shell_side_effect

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="test.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.FAILED, result.status)
        self.assertIn("some repairs failed", result.error_message)
        self.assertEqual(0, result.chunks_repaired)
        logger.info("test_chunked_repair_failure: correctly reported failed repair")


class TestValidateProcessChunkedDirectory(unittest.TestCase):
    """Tests for chunked validation of directories"""

    CHUNK_SIZE = 64

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_validate_chunkdir_")
        self.local_path = os.path.join(self.temp_dir, "local")
        self.remote_path = os.path.join(self.temp_dir, "remote")
        os.makedirs(self.local_path)
        os.makedirs(self.remote_path)
        logger.info("TestValidateProcessChunkedDirectory setUp: %s", self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("controller.validate.validate_process.Sshcp")
    def test_chunked_dir_pass(self, mock_sshcp_cls):
        """Chunked directory validation passes when all files' chunks match"""
        dir_path = os.path.join(self.local_path, "mydir")
        os.makedirs(dir_path)

        file1_content = b"X" * self.CHUNK_SIZE
        file2_content = b"Y" * (self.CHUNK_SIZE + 10)
        _make_file(os.path.join(dir_path, "a.bin"), file1_content)
        _make_file(os.path.join(dir_path, "b.bin"), file2_content)

        def shell_side_effect(cmd):
            if "a.bin" in cmd and "sha256sum" in cmd:
                h = _sha256(file1_content[:self.CHUNK_SIZE])
                return "0 {}\n".format(h).encode()
            elif "b.bin" in cmd and "sha256sum" in cmd:
                h0 = _sha256(file2_content[:self.CHUNK_SIZE])
                h1 = _sha256(file2_content[self.CHUNK_SIZE:])
                return "0 {}\n1 {}\n".format(h0, h1).encode()
            return b""

        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.side_effect = shell_side_effect

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="mydir",
            is_dir=True,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.PASSED, result.status)
        self.assertTrue(result.is_dir)
        logger.info("test_chunked_dir_pass: all chunks in directory validated")

    @patch("controller.validate.validate_process.Sshcp")
    def test_chunked_dir_missing(self, mock_sshcp_cls):
        """Chunked directory validation returns ERROR for missing directory"""
        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="nodir",
            is_dir=True,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=True,
            chunk_size_bytes=self.CHUNK_SIZE
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.ERROR, result.status)
        self.assertIn("Local directory not found", result.error_message)


# ===========================================================================
# Helper method tests
# ===========================================================================
class TestCollectLocalFiles(unittest.TestCase):
    """Tests for the _collect_local_files static method"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_collect_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_empty_directory(self):
        files = ValidateProcess._collect_local_files(self.temp_dir)
        self.assertEqual([], files)

    def test_flat_directory(self):
        _make_file(os.path.join(self.temp_dir, "a.txt"), b"a")
        _make_file(os.path.join(self.temp_dir, "b.txt"), b"b")
        files = sorted(ValidateProcess._collect_local_files(self.temp_dir))
        self.assertEqual(["a.txt", "b.txt"], files)

    def test_nested_directory(self):
        _make_file(os.path.join(self.temp_dir, "a.txt"), b"a")
        _make_file(os.path.join(self.temp_dir, "sub", "b.txt"), b"b")
        _make_file(os.path.join(self.temp_dir, "sub", "deep", "c.txt"), b"c")
        files = sorted(ValidateProcess._collect_local_files(self.temp_dir))
        self.assertEqual(["a.txt", os.path.join("sub", "b.txt"),
                          os.path.join("sub", "deep", "c.txt")], files)

    def test_skips_lftp_files(self):
        _make_file(os.path.join(self.temp_dir, "good.txt"), b"g")
        _make_file(os.path.join(self.temp_dir, "temp.lftp"), b"t")
        _make_file(os.path.join(self.temp_dir, "temp.lftp-pget-status"), b"s")
        files = ValidateProcess._collect_local_files(self.temp_dir)
        self.assertEqual(["good.txt"], files)


class TestComputeLocalSha256(unittest.TestCase):
    """Tests for the _compute_local_sha256 static method"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_sha256_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_hash_matches_known_value(self):
        content = b"test data for sha256"
        file_path = os.path.join(self.temp_dir, "test.bin")
        _make_file(file_path, content)

        expected = _sha256(content)
        result = ValidateProcess._compute_local_sha256(file_path)
        self.assertEqual(expected, result)

    def test_empty_file(self):
        file_path = os.path.join(self.temp_dir, "empty.bin")
        _make_file(file_path, b"")

        expected = _sha256(b"")
        result = ValidateProcess._compute_local_sha256(file_path)
        self.assertEqual(expected, result)

    def test_nonexistent_file_returns_none(self):
        result = ValidateProcess._compute_local_sha256(
            os.path.join(self.temp_dir, "nope.bin")
        )
        self.assertIsNone(result)

    def test_large_file(self):
        """Ensure hash works correctly for files larger than the read buffer"""
        content = os.urandom(32768)  # 32KB
        file_path = os.path.join(self.temp_dir, "large.bin")
        _make_file(file_path, content)

        expected = _sha256(content)
        result = ValidateProcess._compute_local_sha256(file_path)
        self.assertEqual(expected, result)


# ===========================================================================
# Process lifecycle tests
# ===========================================================================
class TestValidateProcessLifecycle(unittest.TestCase):
    """Tests that ValidateProcess works correctly as a subprocess"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_validate_lifecycle_")
        self.local_path = os.path.join(self.temp_dir, "local")
        self.remote_path = os.path.join(self.temp_dir, "remote")
        os.makedirs(self.local_path)
        os.makedirs(self.remote_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("controller.validate.validate_process.Sshcp")
    def test_run_once_catches_unexpected_exceptions(self, mock_sshcp_cls):
        """run_once wraps unexpected exceptions into ERROR result"""
        content = b"data"
        _make_file(os.path.join(self.local_path, "test.bin"), content)

        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.side_effect = RuntimeError("Unexpected crash")

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="test.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=False
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertIsNotNone(result)
        self.assertEqual(ValidationResult.Status.ERROR, result.status)
        self.assertIn("Unexpected crash", result.error_message)

    @patch("controller.validate.validate_process.Sshcp")
    def test_mode_selection_whole_file(self, mock_sshcp_cls):
        """Verify run_once routes to whole-file mode when use_chunked=False"""
        content = b"data"
        _make_file(os.path.join(self.local_path, "test.bin"), content)

        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.return_value = "{}\n".format(_sha256(content)).encode()

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="test.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=False
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertEqual(ValidationResult.Status.PASSED, result.status)
        # Whole-file mode calls shell with sha256sum (not while loop)
        cmd = mock_ssh.shell.call_args[0][0]
        self.assertIn("sha256sum", cmd)
        self.assertNotIn("while", cmd)

    @patch("controller.validate.validate_process.Sshcp")
    def test_mode_selection_chunked(self, mock_sshcp_cls):
        """Verify run_once routes to chunked mode when use_chunked=True"""
        content = b"data" * 100
        _make_file(os.path.join(self.local_path, "test.bin"), content)

        chunk_size = 64
        chunk_hashes = []
        for i in range(0, len(content), chunk_size):
            h = _sha256(content[i:i + chunk_size])
            chunk_hashes.append("{} {}".format(i // chunk_size, h))

        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.return_value = "\n".join(chunk_hashes).encode()

        proc = ValidateProcess(
            local_path=self.local_path,
            remote_path=self.remote_path,
            file_name="test.bin",
            is_dir=False,
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            use_chunked=True,
            chunk_size_bytes=chunk_size
        )
        proc.logger = logger
        proc.run_once()

        result = _pop_result_blocking(proc)
        self.assertEqual(ValidationResult.Status.PASSED, result.status)
        # Chunked mode calls shell with while loop
        cmd = mock_ssh.shell.call_args[0][0]
        self.assertIn("while", cmd)
