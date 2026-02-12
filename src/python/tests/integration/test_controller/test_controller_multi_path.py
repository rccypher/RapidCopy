# Copyright 2024, RapidCopy Contributors, All rights reserved.

"""
Integration tests for Controller multi-path scanning support.

These tests verify that the Controller correctly handles multiple path pairs,
including file detection, path_pair_id assignment, and queue commands with
correct paths.

Requirements:
    - seedsynctest SSH account must be set up (see DeveloperReadme.md)
    - SSH key authentication configured for seedsynctest@localhost
"""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock
import os
import tempfile
import shutil
import logging
import sys
import stat

import timeout_decorator

from tests.utils import TestUtils
from common import overrides, Context, Config, Args, Status
from common.path_pair import PathPair, PathPairManager
from controller import Controller, ControllerPersist
from model import ModelFile, IModelListener


class DummyListener(IModelListener):
    """Dummy listener to capture model events."""

    @overrides(IModelListener)
    def file_added(self, file: ModelFile):
        pass

    @overrides(IModelListener)
    def file_updated(self, old_file: ModelFile, new_file: ModelFile):
        pass

    @overrides(IModelListener)
    def file_removed(self, file: ModelFile):
        pass


class DummyCommandCallback(Controller.Command.ICallback):
    """Dummy callback to capture command results."""

    @overrides(Controller.Command.ICallback)
    def on_failure(self, error: str):
        pass

    @overrides(Controller.Command.ICallback)
    def on_success(self):
        pass


class TestControllerMultiPath(unittest.TestCase):
    """
    Integration tests for Controller with multiple path pairs.

    These tests verify:
    - Controller creates multi-path scanners when path pairs exist
    - Files from different path pairs are detected with correct path_pair_id
    - Queue commands download to the correct path pair directories
    - Delete commands use the correct path pair paths
    """

    __KEEP_FILES = False  # Set to True for debugging

    maxDiff = None
    temp_dir = None
    work_dir = None

    @staticmethod
    def my_mkdir(*args):
        """Create a directory within temp_dir."""
        os.mkdir(os.path.join(TestControllerMultiPath.temp_dir, *args))

    @staticmethod
    def my_touch(size, *args):
        """Create a file with specified size within temp_dir."""
        path = os.path.join(TestControllerMultiPath.temp_dir, *args)
        with open(path, "wb") as f:
            f.write(bytearray([0xFF] * size))

    def _allow_group_access(self, dir_path: str):
        """Allow group access to directory and all contents for seedsynctest."""
        st = os.stat(dir_path)
        os.chmod(dir_path, st.st_mode | stat.S_IWGRP)
        for root, dirs, files in os.walk(dir_path):
            for d in dirs:
                path = os.path.join(root, d)
                st = os.stat(path)
                os.chmod(path, st.st_mode | stat.S_IWGRP)
            for f in files:
                path = os.path.join(root, f)
                st = os.stat(path)
                os.chmod(path, st.st_mode | stat.S_IWGRP)

    @overrides(unittest.TestCase)
    def setUp(self):
        # Create a temp directory
        TestControllerMultiPath.temp_dir = tempfile.mkdtemp(prefix="test_controller_multi_path")

        # Allow group access for the seedsynctest account
        TestUtils.chmod_from_to(self.temp_dir, tempfile.gettempdir(), 0o775)

        # Create a work directory for temp files
        TestControllerMultiPath.work_dir = os.path.join(TestControllerMultiPath.temp_dir, "work")
        os.mkdir(TestControllerMultiPath.work_dir)

        # Create directory structure for two path pairs
        # Path Pair 1: movies
        #   remote1/
        #     movie1 [file, 2*1024 bytes]
        #     movie2 [dir]
        #       part1 [file, 1*1024 bytes]
        #   local1/
        #     existing_movie [file, 1*1024 bytes]
        #
        # Path Pair 2: tvshows
        #   remote2/
        #     show1 [file, 3*1024 bytes]
        #     show2 [dir]
        #       episode1 [file, 1*1024 bytes]
        #   local2/
        #     existing_show [file, 1*1024 bytes]

        # Path Pair 1: Movies
        TestControllerMultiPath.my_mkdir("remote1")
        TestControllerMultiPath.my_touch(2 * 1024, "remote1", "movie1")
        TestControllerMultiPath.my_mkdir("remote1", "movie2")
        TestControllerMultiPath.my_touch(1 * 1024, "remote1", "movie2", "part1")
        TestControllerMultiPath.my_mkdir("local1")
        TestControllerMultiPath.my_touch(1 * 1024, "local1", "existing_movie")

        # Path Pair 2: TV Shows
        TestControllerMultiPath.my_mkdir("remote2")
        TestControllerMultiPath.my_touch(3 * 1024, "remote2", "show1")
        TestControllerMultiPath.my_mkdir("remote2", "show2")
        TestControllerMultiPath.my_touch(1 * 1024, "remote2", "show2", "episode1")
        TestControllerMultiPath.my_mkdir("local2")
        TestControllerMultiPath.my_touch(1 * 1024, "local2", "existing_show")

        # Allow group access to remote directories for seedsynctest
        self._allow_group_access(os.path.join(self.temp_dir, "remote1"))
        self._allow_group_access(os.path.join(self.temp_dir, "remote2"))

        # Create scanfs executable (same as in test_controller.py)
        current_dir_path = os.path.dirname(os.path.realpath(__file__))
        local_script_path = os.path.abspath(os.path.join(current_dir_path, "..", "..", "..", "scan_fs.py"))
        local_exe_dir = os.path.join(TestControllerMultiPath.temp_dir, "scanfs_local")
        remote_exe_dir = os.path.join(TestControllerMultiPath.temp_dir, "scanfs_remote")
        os.makedirs(local_exe_dir, exist_ok=True)
        os.makedirs(remote_exe_dir, exist_ok=True)
        os.chmod(remote_exe_dir, 0o775)
        local_exe_path = os.path.join(local_exe_dir, "scanfs")
        remote_exe_path = remote_exe_dir
        with open(local_exe_path, "w") as f:
            f.write("#!/bin/sh\n")
            f.write("{} {} $*".format(sys.executable, local_script_path))
        os.chmod(local_exe_path, 0o775)
        ctx_args = Args()
        ctx_args.local_path_to_scanfs = local_exe_path

        # Config with placeholder paths (path pairs will override)
        config_dict = {
            "General": {"debug": "True", "verbose": "True", "log_level": "DEBUG"},
            "Lftp": {
                "remote_address": "localhost",
                "remote_username": "seedsynctest",
                "remote_password": "seedsyncpass",
                "remote_port": 22,
                "remote_path": os.path.join(self.temp_dir, "remote1"),  # Default (will use path pairs)
                "local_path": os.path.join(self.temp_dir, "local1"),  # Default (will use path pairs)
                "remote_path_to_scan_script": remote_exe_path,
                "use_ssh_key": "True",
                "num_max_parallel_downloads": "1",
                "num_max_parallel_files_per_download": "3",
                "num_max_connections_per_root_file": "4",
                "num_max_connections_per_dir_file": "4",
                "num_max_total_connections": "12",
                "use_temp_file": "False",
                "rate_limit": "0",
            },
            "Controller": {
                "interval_ms_remote_scan": "100",
                "interval_ms_local_scan": "100",
                "interval_ms_downloading_scan": "100",
                "extract_path": "/unused/path",
                "use_local_path_as_extract_path": True,
            },
            "Web": {
                "port": "8800",
            },
            "AutoQueue": {"enabled": "False", "patterns_only": "True", "auto_extract": "False"},
        }

        # Create path pairs
        self.path_pair_1_id = "test-pair-movies-001"
        self.path_pair_2_id = "test-pair-tvshows-002"

        path_pair_1 = PathPair(
            id=self.path_pair_1_id,
            name="Movies",
            remote_path=os.path.join(self.temp_dir, "remote1"),
            local_path=os.path.join(self.temp_dir, "local1"),
            enabled=True,
            auto_queue=False,
        )
        path_pair_2 = PathPair(
            id=self.path_pair_2_id,
            name="TV Shows",
            remote_path=os.path.join(self.temp_dir, "remote2"),
            local_path=os.path.join(self.temp_dir, "local2"),
            enabled=True,
            auto_queue=False,
        )

        # Setup PathPairManager with in-memory collection
        path_pair_manager = PathPairManager(self.temp_dir)
        path_pair_manager.load()  # Initialize empty collection
        path_pair_manager.collection.add_pair(path_pair_1)
        path_pair_manager.collection.add_pair(path_pair_2)

        # Setup logger
        logger = logging.getLogger(TestControllerMultiPath.__name__)
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)

        self.context = Context(
            logger=logger,
            web_access_logger=logger,
            config=Config.from_dict(config_dict),
            args=ctx_args,
            status=Status(),
            path_pair_manager=path_pair_manager,
        )
        self.controller_persist = ControllerPersist()
        self.controller = None

        # Patch timestamps for easier comparison
        pm = patch("model.file.ModelFile.remote_modified_timestamp", new_callable=PropertyMock)
        self.addCleanup(pm.stop)
        pm_cls = pm.start()
        pm_cls.return_value = None
        pm = patch("model.file.ModelFile.local_modified_timestamp", new_callable=PropertyMock)
        self.addCleanup(pm.stop)
        pm_cls = pm.start()
        pm_cls.return_value = None

    @overrides(unittest.TestCase)
    def tearDown(self):
        if self.controller:
            self.controller.exit()

        if not TestControllerMultiPath.__KEEP_FILES:
            shutil.rmtree(self.temp_dir)

    def __wait_for_initial_model(self, expected_count: int = 6):
        """Wait until the model has the expected number of files."""
        while len(self.controller.get_model_files()) < expected_count:
            self.controller.process()

    @timeout_decorator.timeout(30)
    def test_multi_path_mode_initialization(self):
        """Test that controller initializes in multi-path mode with path pairs."""
        self.controller = Controller(self.context, self.controller_persist)
        self.controller.start()

        # Verify multi-path mode is enabled
        # Access private attribute for testing
        self.assertTrue(self.controller._Controller__is_multi_path_mode)

        # Verify path pairs are stored
        path_pairs = self.controller._Controller__path_pairs
        self.assertEqual(2, len(path_pairs))
        self.assertIn(self.path_pair_1_id, path_pairs)
        self.assertIn(self.path_pair_2_id, path_pairs)

    @timeout_decorator.timeout(30)
    def test_files_detected_from_multiple_path_pairs(self):
        """Test that files from all path pairs are detected in the model."""
        self.controller = Controller(self.context, self.controller_persist)
        self.controller.start()

        # Wait for initial model to populate
        # Expected files: movie1, movie2 (from remote1), show1, show2 (from remote2)
        #                 existing_movie (from local1), existing_show (from local2)
        self.__wait_for_initial_model(expected_count=6)

        model_files = self.controller.get_model_files()
        file_names = {f.name for f in model_files}

        # Check all expected files are present
        expected_names = {"movie1", "movie2", "show1", "show2", "existing_movie", "existing_show"}
        self.assertEqual(expected_names, file_names)

    @timeout_decorator.timeout(30)
    def test_files_have_correct_path_pair_id(self):
        """Test that files have the correct path_pair_id assigned."""
        self.controller = Controller(self.context, self.controller_persist)
        self.controller.start()

        self.__wait_for_initial_model(expected_count=6)

        model_files = self.controller.get_model_files()
        files_dict = {f.name: f for f in model_files}

        # Files from path pair 1 (Movies)
        self.assertEqual(self.path_pair_1_id, files_dict["movie1"].path_pair_id)
        self.assertEqual(self.path_pair_1_id, files_dict["movie2"].path_pair_id)
        self.assertEqual(self.path_pair_1_id, files_dict["existing_movie"].path_pair_id)

        # Files from path pair 2 (TV Shows)
        self.assertEqual(self.path_pair_2_id, files_dict["show1"].path_pair_id)
        self.assertEqual(self.path_pair_2_id, files_dict["show2"].path_pair_id)
        self.assertEqual(self.path_pair_2_id, files_dict["existing_show"].path_pair_id)

    @timeout_decorator.timeout(30)
    def test_files_have_correct_path_pair_name(self):
        """Test that files have the correct path_pair_name assigned."""
        self.controller = Controller(self.context, self.controller_persist)
        self.controller.start()

        self.__wait_for_initial_model(expected_count=6)

        model_files = self.controller.get_model_files()
        files_dict = {f.name: f for f in model_files}

        # Files from path pair 1 (Movies)
        self.assertEqual("Movies", files_dict["movie1"].path_pair_name)
        self.assertEqual("Movies", files_dict["movie2"].path_pair_name)

        # Files from path pair 2 (TV Shows)
        self.assertEqual("TV Shows", files_dict["show1"].path_pair_name)
        self.assertEqual("TV Shows", files_dict["show2"].path_pair_name)

    @timeout_decorator.timeout(30)
    def test_queue_command_downloads_to_correct_path_pair_directory(self):
        """Test that queue command downloads to the correct path pair local directory."""
        self.controller = Controller(self.context, self.controller_persist)
        self.controller.start()

        self.__wait_for_initial_model(expected_count=6)

        # Setup listener
        listener = DummyListener()
        self.controller.add_model_listener(listener)
        self.controller.process()

        listener.file_updated = MagicMock()
        callback = DummyCommandCallback()
        callback.on_success = MagicMock()
        callback.on_failure = MagicMock()

        # Queue download of movie1 (from path pair 1)
        command = Controller.Command(Controller.Command.Action.QUEUE, "movie1")
        command.add_callback(callback)
        self.controller.queue_command(command)

        # Wait for download to complete
        while True:
            self.controller.process()
            call = listener.file_updated.call_args
            if call:
                new_file = call[0][1]
                if new_file.name == "movie1" and new_file.local_size == 2 * 1024:
                    break

        # Verify file downloaded to correct location (local1, not local2)
        callback.on_success.assert_called_once_with()
        callback.on_failure.assert_not_called()

        movie1_path = os.path.join(self.temp_dir, "local1", "movie1")
        self.assertTrue(os.path.exists(movie1_path))
        self.assertEqual(2 * 1024, os.path.getsize(movie1_path))

        # Verify file NOT in wrong location
        wrong_path = os.path.join(self.temp_dir, "local2", "movie1")
        self.assertFalse(os.path.exists(wrong_path))

    @timeout_decorator.timeout(30)
    def test_queue_command_downloads_to_second_path_pair(self):
        """Test that queue command downloads to the second path pair correctly."""
        self.controller = Controller(self.context, self.controller_persist)
        self.controller.start()

        self.__wait_for_initial_model(expected_count=6)

        # Setup listener
        listener = DummyListener()
        self.controller.add_model_listener(listener)
        self.controller.process()

        listener.file_updated = MagicMock()
        callback = DummyCommandCallback()
        callback.on_success = MagicMock()
        callback.on_failure = MagicMock()

        # Queue download of show1 (from path pair 2)
        command = Controller.Command(Controller.Command.Action.QUEUE, "show1")
        command.add_callback(callback)
        self.controller.queue_command(command)

        # Wait for download to complete
        while True:
            self.controller.process()
            call = listener.file_updated.call_args
            if call:
                new_file = call[0][1]
                if new_file.name == "show1" and new_file.local_size == 3 * 1024:
                    break

        # Verify file downloaded to correct location (local2)
        callback.on_success.assert_called_once_with()
        callback.on_failure.assert_not_called()

        show1_path = os.path.join(self.temp_dir, "local2", "show1")
        self.assertTrue(os.path.exists(show1_path))
        self.assertEqual(3 * 1024, os.path.getsize(show1_path))

        # Verify file NOT in wrong location
        wrong_path = os.path.join(self.temp_dir, "local1", "show1")
        self.assertFalse(os.path.exists(wrong_path))

    @timeout_decorator.timeout(30)
    def test_queue_command_downloads_directory_to_correct_path(self):
        """Test that queuing a directory downloads to the correct path pair."""
        self.controller = Controller(self.context, self.controller_persist)
        self.controller.start()

        self.__wait_for_initial_model(expected_count=6)

        # Setup listener
        listener = DummyListener()
        self.controller.add_model_listener(listener)
        self.controller.process()

        listener.file_updated = MagicMock()
        callback = DummyCommandCallback()
        callback.on_success = MagicMock()
        callback.on_failure = MagicMock()

        # Queue download of movie2 directory (from path pair 1)
        command = Controller.Command(Controller.Command.Action.QUEUE, "movie2")
        command.add_callback(callback)
        self.controller.queue_command(command)

        # Wait for download to complete
        while True:
            self.controller.process()
            call = listener.file_updated.call_args
            if call:
                new_file = call[0][1]
                if new_file.name == "movie2" and new_file.local_size == 1 * 1024:
                    break

        # Verify directory downloaded to correct location
        callback.on_success.assert_called_once_with()
        movie2_dir = os.path.join(self.temp_dir, "local1", "movie2")
        self.assertTrue(os.path.isdir(movie2_dir))

        part1_path = os.path.join(movie2_dir, "part1")
        self.assertTrue(os.path.exists(part1_path))
        self.assertEqual(1 * 1024, os.path.getsize(part1_path))

    @timeout_decorator.timeout(30)
    def test_local_file_added_detected_with_correct_path_pair(self):
        """Test that newly added local files are detected with correct path_pair_id."""
        self.controller = Controller(self.context, self.controller_persist)
        self.controller.start()

        self.__wait_for_initial_model(expected_count=6)

        # Setup listener
        listener = DummyListener()
        self.controller.add_model_listener(listener)
        self.controller.process()

        listener.file_added = MagicMock()

        # Add a new local file to path pair 2's local directory
        new_file_path = os.path.join(self.temp_dir, "local2", "new_show")
        with open(new_file_path, "wb") as f:
            f.write(bytearray([0xAA] * 500))

        # Wait for file to be detected
        while listener.file_added.call_count < 1:
            self.controller.process()

        # Verify the added file has correct path_pair_id
        added_file = listener.file_added.call_args[0][0]
        self.assertEqual("new_show", added_file.name)
        self.assertEqual(self.path_pair_2_id, added_file.path_pair_id)
        self.assertEqual("TV Shows", added_file.path_pair_name)

    @timeout_decorator.timeout(30)
    def test_remote_file_added_detected_with_correct_path_pair(self):
        """Test that newly added remote files are detected with correct path_pair_id."""
        self.controller = Controller(self.context, self.controller_persist)
        self.controller.start()

        self.__wait_for_initial_model(expected_count=6)

        # Setup listener
        listener = DummyListener()
        self.controller.add_model_listener(listener)
        self.controller.process()

        listener.file_added = MagicMock()

        # Add a new remote file to path pair 1's remote directory
        new_file_path = os.path.join(self.temp_dir, "remote1", "new_movie")
        with open(new_file_path, "wb") as f:
            f.write(bytearray([0xBB] * 750))

        # Wait for file to be detected
        while listener.file_added.call_count < 1:
            self.controller.process()

        # Verify the added file has correct path_pair_id
        added_file = listener.file_added.call_args[0][0]
        self.assertEqual("new_movie", added_file.name)
        self.assertEqual(self.path_pair_1_id, added_file.path_pair_id)
        self.assertEqual("Movies", added_file.path_pair_name)

    @timeout_decorator.timeout(30)
    def test_delete_local_uses_correct_path_pair(self):
        """Test that delete local command uses the correct path pair path."""
        self.controller = Controller(self.context, self.controller_persist)
        self.controller.start()

        self.__wait_for_initial_model(expected_count=6)

        # Setup callback
        callback = DummyCommandCallback()
        callback.on_success = MagicMock()
        callback.on_failure = MagicMock()

        # Verify file exists before delete
        existing_movie_path = os.path.join(self.temp_dir, "local1", "existing_movie")
        self.assertTrue(os.path.exists(existing_movie_path))

        # Delete local file from path pair 1
        command = Controller.Command(Controller.Command.Action.DELETE_LOCAL, "existing_movie")
        command.add_callback(callback)
        self.controller.queue_command(command)

        # Wait for delete to complete
        while callback.on_success.call_count < 1 and callback.on_failure.call_count < 1:
            self.controller.process()

        # Verify file deleted from correct location
        callback.on_success.assert_called_once_with()
        callback.on_failure.assert_not_called()
        self.assertFalse(os.path.exists(existing_movie_path))

    @timeout_decorator.timeout(30)
    def test_delete_remote_uses_correct_path_pair(self):
        """Test that delete remote command uses the correct path pair path."""
        self.controller = Controller(self.context, self.controller_persist)
        self.controller.start()

        self.__wait_for_initial_model(expected_count=6)

        # Setup callback
        callback = DummyCommandCallback()
        callback.on_success = MagicMock()
        callback.on_failure = MagicMock()

        # Verify file exists before delete
        movie1_path = os.path.join(self.temp_dir, "remote1", "movie1")
        self.assertTrue(os.path.exists(movie1_path))

        # Delete remote file from path pair 1
        command = Controller.Command(Controller.Command.Action.DELETE_REMOTE, "movie1")
        command.add_callback(callback)
        self.controller.queue_command(command)

        # Wait for delete to complete
        while callback.on_success.call_count < 1 and callback.on_failure.call_count < 1:
            self.controller.process()

        # Verify file deleted from correct location
        callback.on_success.assert_called_once_with()
        callback.on_failure.assert_not_called()
        self.assertFalse(os.path.exists(movie1_path))


class TestControllerMultiPathDisabled(unittest.TestCase):
    """
    Tests for Controller with disabled path pairs.

    Verifies that disabled path pairs are not scanned.
    """

    __KEEP_FILES = False

    @overrides(unittest.TestCase)
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_controller_multi_path_disabled")
        TestUtils.chmod_from_to(self.temp_dir, tempfile.gettempdir(), 0o775)

        # Create directory structure
        os.mkdir(os.path.join(self.temp_dir, "remote1"))
        os.mkdir(os.path.join(self.temp_dir, "local1"))
        os.mkdir(os.path.join(self.temp_dir, "remote2"))
        os.mkdir(os.path.join(self.temp_dir, "local2"))

        # Create files
        with open(os.path.join(self.temp_dir, "remote1", "enabled_file"), "wb") as f:
            f.write(bytearray([0xFF] * 1024))
        with open(os.path.join(self.temp_dir, "remote2", "disabled_file"), "wb") as f:
            f.write(bytearray([0xFF] * 1024))

        # Allow group access for remote directories
        for d in ["remote1", "remote2"]:
            dir_path = os.path.join(self.temp_dir, d)
            os.chmod(dir_path, 0o775)
            for root, dirs, files in os.walk(dir_path):
                for name in dirs + files:
                    os.chmod(os.path.join(root, name), 0o775)

        # Create scanfs executable
        current_dir_path = os.path.dirname(os.path.realpath(__file__))
        local_script_path = os.path.abspath(os.path.join(current_dir_path, "..", "..", "..", "scan_fs.py"))
        local_exe_dir = os.path.join(self.temp_dir, "scanfs_local")
        remote_exe_dir = os.path.join(self.temp_dir, "scanfs_remote")
        os.makedirs(local_exe_dir, exist_ok=True)
        os.makedirs(remote_exe_dir, exist_ok=True)
        os.chmod(remote_exe_dir, 0o775)
        local_exe_path = os.path.join(local_exe_dir, "scanfs")
        with open(local_exe_path, "w") as f:
            f.write("#!/bin/sh\n")
            f.write("{} {} $*".format(sys.executable, local_script_path))
        os.chmod(local_exe_path, 0o775)

        ctx_args = Args()
        ctx_args.local_path_to_scanfs = local_exe_path

        config_dict = {
            "General": {"debug": "True", "verbose": "True", "log_level": "DEBUG"},
            "Lftp": {
                "remote_address": "localhost",
                "remote_username": "seedsynctest",
                "remote_password": "seedsyncpass",
                "remote_port": 22,
                "remote_path": os.path.join(self.temp_dir, "remote1"),
                "local_path": os.path.join(self.temp_dir, "local1"),
                "remote_path_to_scan_script": remote_exe_dir,
                "use_ssh_key": "True",
                "num_max_parallel_downloads": "1",
                "num_max_parallel_files_per_download": "3",
                "num_max_connections_per_root_file": "4",
                "num_max_connections_per_dir_file": "4",
                "num_max_total_connections": "12",
                "use_temp_file": "False",
                "rate_limit": "0",
            },
            "Controller": {
                "interval_ms_remote_scan": "100",
                "interval_ms_local_scan": "100",
                "interval_ms_downloading_scan": "100",
                "extract_path": "/unused/path",
                "use_local_path_as_extract_path": True,
            },
            "Web": {"port": "8800"},
            "AutoQueue": {"enabled": "False", "patterns_only": "True", "auto_extract": "False"},
        }

        # Create path pairs - one enabled, one disabled
        path_pair_1 = PathPair(
            id="enabled-pair",
            name="Enabled",
            remote_path=os.path.join(self.temp_dir, "remote1"),
            local_path=os.path.join(self.temp_dir, "local1"),
            enabled=True,
        )
        path_pair_2 = PathPair(
            id="disabled-pair",
            name="Disabled",
            remote_path=os.path.join(self.temp_dir, "remote2"),
            local_path=os.path.join(self.temp_dir, "local2"),
            enabled=False,  # Disabled
        )

        path_pair_manager = PathPairManager(self.temp_dir)
        path_pair_manager.load()
        path_pair_manager.collection.add_pair(path_pair_1)
        path_pair_manager.collection.add_pair(path_pair_2)

        logger = logging.getLogger("TestControllerMultiPathDisabled")
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        self.context = Context(
            logger=logger,
            web_access_logger=logger,
            config=Config.from_dict(config_dict),
            args=ctx_args,
            status=Status(),
            path_pair_manager=path_pair_manager,
        )
        self.controller_persist = ControllerPersist()
        self.controller = None

        # Patch timestamps
        pm = patch("model.file.ModelFile.remote_modified_timestamp", new_callable=PropertyMock)
        self.addCleanup(pm.stop)
        pm.start().return_value = None
        pm = patch("model.file.ModelFile.local_modified_timestamp", new_callable=PropertyMock)
        self.addCleanup(pm.stop)
        pm.start().return_value = None

    @overrides(unittest.TestCase)
    def tearDown(self):
        if self.controller:
            self.controller.exit()
        if not TestControllerMultiPathDisabled.__KEEP_FILES:
            shutil.rmtree(self.temp_dir)

    @timeout_decorator.timeout(30)
    def test_disabled_path_pair_not_scanned(self):
        """Test that files from disabled path pairs are not detected."""
        self.controller = Controller(self.context, self.controller_persist)
        self.controller.start()

        # Wait for model to populate
        import time

        start_time = time.time()
        while time.time() - start_time < 3:  # Wait up to 3 seconds
            self.controller.process()
            files = self.controller.get_model_files()
            if len(files) >= 1:
                break

        model_files = self.controller.get_model_files()
        file_names = {f.name for f in model_files}

        # Only file from enabled path pair should be present
        self.assertIn("enabled_file", file_names)
        self.assertNotIn("disabled_file", file_names)


if __name__ == "__main__":
    unittest.main()
