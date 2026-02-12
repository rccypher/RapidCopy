# Copyright 2024, RapidCopy Contributors, All rights reserved.

import logging
import os
import shutil
import sys
import tempfile
import time
import unittest

from controller.scan import MultiPathActiveScanner
from system import SystemFile

# Small delay to allow multiprocessing queue to propagate
QUEUE_DELAY = 0.01


def my_mkdir(base_dir, *args):
    """Create a directory in the given base directory."""
    os.makedirs(os.path.join(base_dir, *args), exist_ok=True)


def my_touch(base_dir, size, *args):
    """Create a file with specified size in the given base directory."""
    path = os.path.join(base_dir, *args)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(bytearray([0xFF] * size))


class TestMultiPathActiveScanner(unittest.TestCase):
    """Unit tests for MultiPathActiveScanner class."""

    def setUp(self):
        """Set up test fixtures with multiple temporary directories."""
        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)

        # Create multiple temp directories simulating different path pairs
        self.path_pair_1_dir = tempfile.mkdtemp(prefix="test_multi_path_scanner_pair1_")
        self.path_pair_2_dir = tempfile.mkdtemp(prefix="test_multi_path_scanner_pair2_")
        self.path_pair_3_dir = tempfile.mkdtemp(prefix="test_multi_path_scanner_pair3_")

    def tearDown(self):
        """Clean up test directories."""
        for temp_dir in [self.path_pair_1_dir, self.path_pair_2_dir, self.path_pair_3_dir]:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def _scan_with_queue_delay(self, scanner):
        """
        Helper to scan with a small delay to allow multiprocessing queue to propagate.
        This is needed because set_active_files uses a multiprocessing.Queue and
        the item may not be immediately available for get(block=False).
        """
        time.sleep(QUEUE_DELAY)
        return scanner.scan()

    # =========================================================================
    # Initialization Tests
    # =========================================================================

    def test_init_with_single_path_pair(self):
        """Test initialization with a single path pair."""
        path_pairs = {"pair1": self.path_pair_1_dir}
        scanner = MultiPathActiveScanner(path_pairs)
        self.assertIsNotNone(scanner)

    def test_init_with_multiple_path_pairs(self):
        """Test initialization with multiple path pairs."""
        path_pairs = {
            "pair1": self.path_pair_1_dir,
            "pair2": self.path_pair_2_dir,
            "pair3": self.path_pair_3_dir,
        }
        scanner = MultiPathActiveScanner(path_pairs)
        self.assertIsNotNone(scanner)

    def test_init_with_empty_path_pairs(self):
        """Test initialization with empty path pairs dictionary."""
        path_pairs = {}
        scanner = MultiPathActiveScanner(path_pairs)
        self.assertIsNotNone(scanner)

    # =========================================================================
    # Basic Scan Tests
    # =========================================================================

    def test_scan_returns_empty_list_when_no_active_files(self):
        """Test that scan returns empty list when no active files are set."""
        path_pairs = {"pair1": self.path_pair_1_dir}
        scanner = MultiPathActiveScanner(path_pairs)

        result = scanner.scan()
        self.assertEqual([], result)

    def test_scan_single_file_in_single_path_pair(self):
        """Test scanning a single file in a single path pair."""
        # Create a file in path pair 1
        my_touch(self.path_pair_1_dir, 1024, "test_file.txt")

        path_pairs = {"pair1": self.path_pair_1_dir}
        scanner = MultiPathActiveScanner(path_pairs)

        # Set active files with path_pair_id
        scanner.set_active_files([("test_file.txt", "pair1")])

        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(1, len(result))
        self.assertEqual("test_file.txt", result[0].name)
        self.assertEqual(1024, result[0].size)
        self.assertFalse(result[0].is_dir)

    def test_scan_directory_in_path_pair(self):
        """Test scanning a directory in a path pair."""
        # Create a directory with files
        my_mkdir(self.path_pair_1_dir, "test_dir")
        my_touch(self.path_pair_1_dir, 512, "test_dir", "file1.txt")
        my_touch(self.path_pair_1_dir, 256, "test_dir", "file2.txt")

        path_pairs = {"pair1": self.path_pair_1_dir}
        scanner = MultiPathActiveScanner(path_pairs)

        scanner.set_active_files([("test_dir", "pair1")])

        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(1, len(result))
        self.assertEqual("test_dir", result[0].name)
        self.assertTrue(result[0].is_dir)
        self.assertEqual(512 + 256, result[0].size)
        self.assertEqual(2, len(result[0].children))

    # =========================================================================
    # Multi-Path Routing Tests
    # =========================================================================

    def test_scan_routes_files_to_correct_path_pairs(self):
        """Test that files are routed to correct path pair scanners."""
        # Create files in different path pairs
        my_touch(self.path_pair_1_dir, 100, "file_in_pair1.txt")
        my_touch(self.path_pair_2_dir, 200, "file_in_pair2.txt")
        my_touch(self.path_pair_3_dir, 300, "file_in_pair3.txt")

        path_pairs = {
            "pair1": self.path_pair_1_dir,
            "pair2": self.path_pair_2_dir,
            "pair3": self.path_pair_3_dir,
        }
        scanner = MultiPathActiveScanner(path_pairs)

        # Set active files from all path pairs
        scanner.set_active_files(
            [
                ("file_in_pair1.txt", "pair1"),
                ("file_in_pair2.txt", "pair2"),
                ("file_in_pair3.txt", "pair3"),
            ]
        )

        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(3, len(result))

        # Check each file has correct size (proves it was routed correctly)
        result_by_name = {f.name: f for f in result}
        self.assertEqual(100, result_by_name["file_in_pair1.txt"].size)
        self.assertEqual(200, result_by_name["file_in_pair2.txt"].size)
        self.assertEqual(300, result_by_name["file_in_pair3.txt"].size)

    def test_scan_sets_path_pair_id_on_result_files(self):
        """Test that scanned files have path_pair_id attribute set."""
        my_touch(self.path_pair_1_dir, 100, "file1.txt")
        my_touch(self.path_pair_2_dir, 200, "file2.txt")

        path_pairs = {
            "pair1": self.path_pair_1_dir,
            "pair2": self.path_pair_2_dir,
        }
        scanner = MultiPathActiveScanner(path_pairs)

        scanner.set_active_files(
            [
                ("file1.txt", "pair1"),
                ("file2.txt", "pair2"),
            ]
        )

        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(2, len(result))

        result_by_name = {f.name: f for f in result}
        self.assertEqual("pair1", result_by_name["file1.txt"].path_pair_id)
        self.assertEqual("pair2", result_by_name["file2.txt"].path_pair_id)

    def test_scan_multiple_files_in_same_path_pair(self):
        """Test scanning multiple files from the same path pair."""
        my_touch(self.path_pair_1_dir, 100, "file1.txt")
        my_touch(self.path_pair_1_dir, 200, "file2.txt")
        my_touch(self.path_pair_1_dir, 300, "file3.txt")

        path_pairs = {"pair1": self.path_pair_1_dir}
        scanner = MultiPathActiveScanner(path_pairs)

        scanner.set_active_files(
            [
                ("file1.txt", "pair1"),
                ("file2.txt", "pair1"),
                ("file3.txt", "pair1"),
            ]
        )

        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(3, len(result))

        result_by_name = {f.name: f for f in result}
        self.assertEqual(100, result_by_name["file1.txt"].size)
        self.assertEqual(200, result_by_name["file2.txt"].size)
        self.assertEqual(300, result_by_name["file3.txt"].size)

    # =========================================================================
    # Fallback / Default Scanner Tests
    # =========================================================================

    def test_scan_with_none_path_pair_id_uses_default_scanner(self):
        """Test that files with None path_pair_id use default scanner."""
        my_touch(self.path_pair_1_dir, 100, "file_with_none_pair.txt")

        path_pairs = {
            "pair1": self.path_pair_1_dir,
            "pair2": self.path_pair_2_dir,
        }
        scanner = MultiPathActiveScanner(path_pairs)

        # Set active file with None path_pair_id
        scanner.set_active_files([("file_with_none_pair.txt", None)])

        result = self._scan_with_queue_delay(scanner)
        # Should use default scanner (first path pair)
        self.assertEqual(1, len(result))
        self.assertEqual("file_with_none_pair.txt", result[0].name)
        self.assertEqual(100, result[0].size)

    def test_scan_with_unknown_path_pair_id_uses_default_scanner(self):
        """Test that files with unknown path_pair_id use default scanner."""
        my_touch(self.path_pair_1_dir, 150, "file_unknown_pair.txt")

        path_pairs = {
            "pair1": self.path_pair_1_dir,
            "pair2": self.path_pair_2_dir,
        }
        scanner = MultiPathActiveScanner(path_pairs)

        # Set active file with unknown path_pair_id
        scanner.set_active_files([("file_unknown_pair.txt", "unknown_pair")])

        result = self._scan_with_queue_delay(scanner)
        # Should fall back to default scanner
        self.assertEqual(1, len(result))
        self.assertEqual("file_unknown_pair.txt", result[0].name)

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    def test_scan_handles_missing_file_gracefully(self):
        """Test that scanning a non-existent file doesn't crash."""
        path_pairs = {"pair1": self.path_pair_1_dir}
        scanner = MultiPathActiveScanner(path_pairs)

        # Set active file that doesn't exist
        scanner.set_active_files([("nonexistent_file.txt", "pair1")])

        # Should not raise, just skip the missing file
        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(0, len(result))

    def test_scan_continues_after_missing_file(self):
        """Test that scan continues processing after encountering missing file."""
        my_touch(self.path_pair_1_dir, 100, "exists.txt")

        path_pairs = {"pair1": self.path_pair_1_dir}
        scanner = MultiPathActiveScanner(path_pairs)

        scanner.set_active_files(
            [
                ("nonexistent.txt", "pair1"),
                ("exists.txt", "pair1"),
            ]
        )

        result = self._scan_with_queue_delay(scanner)
        # Should have the existing file
        self.assertEqual(1, len(result))
        self.assertEqual("exists.txt", result[0].name)

    def test_scan_with_no_scanners_for_path_pair(self):
        """Test scanning when path_pair has no corresponding scanner."""
        path_pairs = {}  # Empty - no scanners
        scanner = MultiPathActiveScanner(path_pairs)

        scanner.set_active_files([("file.txt", "pair1")])

        # Should return empty (no scanner available)
        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(0, len(result))

    # =========================================================================
    # Queue Behavior Tests
    # =========================================================================

    def test_set_active_files_updates_scan_list(self):
        """Test that set_active_files updates what gets scanned."""
        my_touch(self.path_pair_1_dir, 100, "file1.txt")
        my_touch(self.path_pair_1_dir, 200, "file2.txt")

        path_pairs = {"pair1": self.path_pair_1_dir}
        scanner = MultiPathActiveScanner(path_pairs)

        # First set of active files
        scanner.set_active_files([("file1.txt", "pair1")])
        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(1, len(result))
        self.assertEqual("file1.txt", result[0].name)

        # Update active files
        scanner.set_active_files([("file2.txt", "pair1")])
        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(1, len(result))
        self.assertEqual("file2.txt", result[0].name)

    def test_scan_uses_latest_active_files_when_multiple_updates(self):
        """Test that multiple set_active_files calls use the latest."""
        my_touch(self.path_pair_1_dir, 100, "file1.txt")
        my_touch(self.path_pair_1_dir, 200, "file2.txt")
        my_touch(self.path_pair_1_dir, 300, "file3.txt")

        path_pairs = {"pair1": self.path_pair_1_dir}
        scanner = MultiPathActiveScanner(path_pairs)

        # Set multiple times before scan
        scanner.set_active_files([("file1.txt", "pair1")])
        scanner.set_active_files([("file2.txt", "pair1")])
        scanner.set_active_files([("file3.txt", "pair1")])

        # Should use the latest
        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(1, len(result))
        self.assertEqual("file3.txt", result[0].name)

    def test_scan_without_set_active_files_keeps_previous(self):
        """Test that calling scan without new set_active_files uses previous list."""
        my_touch(self.path_pair_1_dir, 100, "file1.txt")

        path_pairs = {"pair1": self.path_pair_1_dir}
        scanner = MultiPathActiveScanner(path_pairs)

        scanner.set_active_files([("file1.txt", "pair1")])

        # First scan
        result1 = self._scan_with_queue_delay(scanner)
        self.assertEqual(1, len(result1))

        # Second scan without updating active files
        result2 = scanner.scan()
        self.assertEqual(1, len(result2))
        self.assertEqual("file1.txt", result2[0].name)

    def test_set_active_files_with_empty_list_clears_scan(self):
        """Test that setting empty active files list clears the scan."""
        my_touch(self.path_pair_1_dir, 100, "file1.txt")

        path_pairs = {"pair1": self.path_pair_1_dir}
        scanner = MultiPathActiveScanner(path_pairs)

        scanner.set_active_files([("file1.txt", "pair1")])
        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(1, len(result))

        # Clear active files
        scanner.set_active_files([])
        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(0, len(result))

    # =========================================================================
    # Logger Tests
    # =========================================================================

    def test_set_base_logger(self):
        """Test that set_base_logger works correctly."""
        path_pairs = {"pair1": self.path_pair_1_dir}
        scanner = MultiPathActiveScanner(path_pairs)

        test_logger = logging.getLogger("TestLogger")
        scanner.set_base_logger(test_logger)

        # Should not raise
        self.assertIsNotNone(scanner.logger)

    # =========================================================================
    # Mixed Scenario Tests
    # =========================================================================

    def test_scan_mixed_files_and_directories(self):
        """Test scanning a mix of files and directories across path pairs."""
        # Create file in pair1
        my_touch(self.path_pair_1_dir, 500, "file_in_pair1.txt")

        # Create directory in pair2
        my_mkdir(self.path_pair_2_dir, "dir_in_pair2")
        my_touch(self.path_pair_2_dir, 250, "dir_in_pair2", "nested.txt")

        path_pairs = {
            "pair1": self.path_pair_1_dir,
            "pair2": self.path_pair_2_dir,
        }
        scanner = MultiPathActiveScanner(path_pairs)

        scanner.set_active_files(
            [
                ("file_in_pair1.txt", "pair1"),
                ("dir_in_pair2", "pair2"),
            ]
        )

        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(2, len(result))

        result_by_name = {f.name: f for f in result}

        # Verify file
        self.assertFalse(result_by_name["file_in_pair1.txt"].is_dir)
        self.assertEqual(500, result_by_name["file_in_pair1.txt"].size)

        # Verify directory
        self.assertTrue(result_by_name["dir_in_pair2"].is_dir)
        self.assertEqual(250, result_by_name["dir_in_pair2"].size)
        self.assertEqual(1, len(result_by_name["dir_in_pair2"].children))

    def test_scan_same_filename_in_different_path_pairs(self):
        """Test scanning files with same name but in different path pairs."""
        # Create files with same name but different content in different pairs
        my_touch(self.path_pair_1_dir, 100, "common_file.txt")
        my_touch(self.path_pair_2_dir, 999, "common_file.txt")

        path_pairs = {
            "pair1": self.path_pair_1_dir,
            "pair2": self.path_pair_2_dir,
        }
        scanner = MultiPathActiveScanner(path_pairs)

        scanner.set_active_files(
            [
                ("common_file.txt", "pair1"),
                ("common_file.txt", "pair2"),
            ]
        )

        result = self._scan_with_queue_delay(scanner)
        self.assertEqual(2, len(result))

        # Both should be named the same
        self.assertEqual("common_file.txt", result[0].name)
        self.assertEqual("common_file.txt", result[1].name)

        # But should have different sizes (proving they came from different paths)
        sizes = {result[0].size, result[1].size}
        self.assertEqual({100, 999}, sizes)

        # And different path_pair_ids
        path_pair_ids = {result[0].path_pair_id, result[1].path_pair_id}
        self.assertEqual({"pair1", "pair2"}, path_pair_ids)


if __name__ == "__main__":
    unittest.main()
