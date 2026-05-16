# Copyright 2024, RapidCopy Contributors, All rights reserved.

import unittest
import tempfile
from unittest.mock import patch

from common.path_pair import (
    PathPair,
    PathPairCollection,
    PathPairManager,
    PathPairError,
    is_running_in_docker,
    DOCKER_DOWNLOADS_BASE,
)


class TestIsRunningInDocker(unittest.TestCase):
    """Tests for Docker environment detection."""

    @patch("os.path.exists")
    def test_detects_docker_via_dockerenv(self, mock_exists):
        """Should return True when /.dockerenv exists."""
        mock_exists.return_value = True
        self.assertTrue(is_running_in_docker())

    @patch("os.path.exists")
    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_not_in_docker_when_no_indicators(self, mock_open, mock_exists):
        """Should return False when not in Docker."""
        mock_exists.return_value = False
        self.assertFalse(is_running_in_docker())


class TestPathPairValidation(unittest.TestCase):
    """Tests for PathPair validation including Docker warnings."""

    def test_validate_returns_empty_list_when_valid(self):
        """Valid path pair should return no warnings outside Docker."""
        pair = PathPair(
            name="Test",
            remote_path="/remote/path",
            local_path="/local/path",
            enabled=True,
            auto_queue=True,
        )
        # Not in Docker, so no warnings expected
        with patch("common.path_pair.is_running_in_docker", return_value=False):
            warnings = pair.validate()
            self.assertEqual(warnings, [])

    def test_validate_raises_on_empty_remote_path(self):
        """Should raise PathPairError when remote_path is empty."""
        pair = PathPair(
            name="Test",
            remote_path="",
            local_path="/local/path",
        )
        with self.assertRaises(PathPairError) as ctx:
            pair.validate()
        self.assertIn("remote_path cannot be empty", str(ctx.exception))

    def test_validate_raises_on_empty_local_path(self):
        """Should raise PathPairError when local_path is empty."""
        pair = PathPair(
            name="Test",
            remote_path="/remote/path",
            local_path="",
        )
        with self.assertRaises(PathPairError) as ctx:
            pair.validate()
        self.assertIn("local_path cannot be empty", str(ctx.exception))

    @patch("common.path_pair.is_running_in_docker", return_value=True)
    def test_docker_warning_when_local_path_not_under_downloads(self, mock_docker):
        """Should return warning in Docker when local_path is not under /downloads."""
        pair = PathPair(
            name="Movies",
            remote_path="/remote/movies",
            local_path="/media/movies",  # Not under /downloads
        )
        warnings = pair.validate()
        self.assertEqual(len(warnings), 1)
        self.assertIn("/media/movies", warnings[0])
        self.assertIn(DOCKER_DOWNLOADS_BASE, warnings[0])

    @patch("common.path_pair.is_running_in_docker", return_value=True)
    def test_no_docker_warning_when_local_path_under_downloads(self, mock_docker):
        """Should NOT return warning in Docker when local_path is under /downloads."""
        pair = PathPair(
            name="Movies",
            remote_path="/remote/movies",
            local_path="/downloads/movies",  # Correct subdirectory
        )
        warnings = pair.validate()
        self.assertEqual(warnings, [])

    @patch("common.path_pair.is_running_in_docker", return_value=True)
    def test_no_docker_warning_when_local_path_is_downloads(self, mock_docker):
        """Should NOT return warning when local_path is exactly /downloads."""
        pair = PathPair(
            name="Default",
            remote_path="/remote",
            local_path="/downloads",
        )
        warnings = pair.validate()
        self.assertEqual(warnings, [])

    @patch("common.path_pair.is_running_in_docker", return_value=True)
    def test_docker_warning_for_path_with_downloads_prefix_but_not_subdir(self, mock_docker):
        """Should warn for paths like /downloads-extra that aren't real subdirs."""
        pair = PathPair(
            name="Test",
            remote_path="/remote",
            local_path="/downloads-extra/movies",  # Not a real subdirectory
        )
        warnings = pair.validate()
        self.assertEqual(len(warnings), 1)


class TestPathPairCollection(unittest.TestCase):
    """Tests for PathPairCollection operations."""

    @patch("common.path_pair.is_running_in_docker", return_value=False)
    def test_add_pair_returns_warnings(self, mock_docker):
        """add_pair should return validation warnings."""
        collection = PathPairCollection()
        pair = PathPair(
            name="Test",
            remote_path="/remote/path",
            local_path="/local/path",
        )
        warnings = collection.add_pair(pair)
        self.assertEqual(warnings, [])
        self.assertEqual(len(collection.path_pairs), 1)

    @patch("common.path_pair.is_running_in_docker", return_value=True)
    def test_add_pair_returns_docker_warnings(self, mock_docker):
        """add_pair should return Docker warnings when applicable."""
        collection = PathPairCollection()
        pair = PathPair(
            name="Movies",
            remote_path="/remote/movies",
            local_path="/media/movies",  # Not under /downloads
        )
        warnings = collection.add_pair(pair)
        self.assertEqual(len(warnings), 1)
        self.assertIn("/media/movies", warnings[0])
        # Pair should still be added
        self.assertEqual(len(collection.path_pairs), 1)

    @patch("common.path_pair.is_running_in_docker", return_value=True)
    def test_update_pair_returns_warnings(self, mock_docker):
        """update_pair should return validation warnings."""
        collection = PathPairCollection()
        # Add initial pair with valid path
        pair = PathPair(
            name="Movies",
            remote_path="/remote/movies",
            local_path="/downloads/movies",
        )
        collection.add_pair(pair)

        # Update to invalid path
        updated_pair = PathPair(
            id=pair.id,
            name="Movies",
            remote_path="/remote/movies",
            local_path="/media/movies",  # Changed to invalid
        )
        warnings = collection.update_pair(updated_pair)
        self.assertEqual(len(warnings), 1)


if __name__ == "__main__":
    unittest.main()
