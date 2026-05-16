# Copyright 2024, SeedSync Contributors, All rights reserved.

import logging
import os
import sys
import tempfile
import shutil
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from controller.validate.validate_process import (
    ValidateProcess, ValidationResult, ValidationStatus
)
from controller.controller_persist import ControllerPersist
from controller import ModelBuilder
from model import ModelFile
from system import SystemFile


# ===========================================================================
# Logging setup
# ===========================================================================
logger = logging.getLogger("test_controller_validation")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


# ===========================================================================
# Controller persistence tests for validation retry tracking
# ===========================================================================
class TestControllerPersistValidation(unittest.TestCase):
    """Tests for validation_retry_counts in ControllerPersist"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_persist_val_")
        self.persist_file = os.path.join(self.temp_dir, "controller.persist")
        logger.info("setUp: persist_file=%s", self.persist_file)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initial_validation_retry_counts(self):
        """validation_retry_counts starts empty"""
        persist = ControllerPersist()
        self.assertEqual({}, persist.validation_retry_counts)

    def test_set_and_get_retry_counts(self):
        """Can set and get validation retry counts"""
        persist = ControllerPersist()
        persist.validation_retry_counts["file_a"] = 1
        persist.validation_retry_counts["file_b"] = 3
        self.assertEqual(1, persist.validation_retry_counts["file_a"])
        self.assertEqual(3, persist.validation_retry_counts["file_b"])

    def test_delete_retry_count(self):
        """Can delete a retry count entry"""
        persist = ControllerPersist()
        persist.validation_retry_counts["file_a"] = 2
        del persist.validation_retry_counts["file_a"]
        self.assertNotIn("file_a", persist.validation_retry_counts)

    def test_retry_count_get_with_default(self):
        """Can use .get() with default for missing entries"""
        persist = ControllerPersist()
        self.assertEqual(0, persist.validation_retry_counts.get("nonexistent", 0))
        logger.info("test_retry_count_get_with_default: default returned correctly")


# ===========================================================================
# Model builder validation status tests
# ===========================================================================
class TestModelBuilderValidation(unittest.TestCase):
    """Tests for validation status integration in ModelBuilder"""

    def setUp(self):
        self.model_builder = ModelBuilder()
        self.model_builder.set_base_logger(logger)

    def test_set_validation_statuses_marks_file_validating(self):
        """File should be set to VALIDATING when there's an active validation status"""
        self.model_builder.clear()

        # Create remote and local file that looks DOWNLOADED
        r_a = SystemFile("a", 1024, False)
        l_a = SystemFile("a", 1024, False)

        self.model_builder.set_remote_files([r_a])
        self.model_builder.set_local_files([l_a])
        self.model_builder.set_downloaded_files({"a"})

        # Set validation status
        vs = ValidationStatus(name="a", is_dir=False)
        self.model_builder.set_validation_statuses([vs])

        model = self.model_builder.build_model()
        file_a = model.get_file("a")
        self.assertEqual(ModelFile.State.VALIDATING, file_a.state)
        logger.info("test_set_validation_statuses_marks_file_validating: state is VALIDATING")

    def test_no_validation_status_file_remains_downloaded(self):
        """File remains DOWNLOADED when no validation is active"""
        self.model_builder.clear()

        r_a = SystemFile("a", 1024, False)
        l_a = SystemFile("a", 1024, False)

        self.model_builder.set_remote_files([r_a])
        self.model_builder.set_local_files([l_a])
        self.model_builder.set_downloaded_files({"a"})
        self.model_builder.set_validation_statuses([])

        model = self.model_builder.build_model()
        file_a = model.get_file("a")
        self.assertEqual(ModelFile.State.DOWNLOADED, file_a.state)

    def test_validation_status_directory(self):
        """Directory file is set to VALIDATING correctly"""
        self.model_builder.clear()

        r_a = SystemFile("a", 1024, True)
        r_aa = SystemFile("aa", 1024, False)
        r_a.add_child(r_aa)

        l_a = SystemFile("a", 1024, True)
        l_aa = SystemFile("aa", 1024, False)
        l_a.add_child(l_aa)

        self.model_builder.set_remote_files([r_a])
        self.model_builder.set_local_files([l_a])
        self.model_builder.set_downloaded_files({"a"})

        vs = ValidationStatus(name="a", is_dir=True)
        self.model_builder.set_validation_statuses([vs])

        model = self.model_builder.build_model()
        file_a = model.get_file("a")
        self.assertEqual(ModelFile.State.VALIDATING, file_a.state)
        logger.info("test_validation_status_directory: directory marked as VALIDATING")

    def test_clear_removes_validation_statuses(self):
        """ModelBuilder.clear() removes validation statuses"""
        self.model_builder.clear()

        r_a = SystemFile("a", 1024, False)
        l_a = SystemFile("a", 1024, False)

        self.model_builder.set_remote_files([r_a])
        self.model_builder.set_local_files([l_a])
        self.model_builder.set_downloaded_files({"a"})

        vs = ValidationStatus(name="a", is_dir=False)
        self.model_builder.set_validation_statuses([vs])

        # Clear and rebuild
        self.model_builder.clear()
        self.model_builder.set_remote_files([r_a])
        self.model_builder.set_local_files([l_a])
        self.model_builder.set_downloaded_files({"a"})

        model = self.model_builder.build_model()
        file_a = model.get_file("a")
        # Should be DOWNLOADED not VALIDATING after clear
        self.assertEqual(ModelFile.State.DOWNLOADED, file_a.state)
        logger.info("test_clear_removes_validation_statuses: cleared correctly")


# ===========================================================================
# Model file state tests
# ===========================================================================
class TestModelFileValidatingState(unittest.TestCase):
    """Tests for the VALIDATING state in ModelFile"""

    def test_validating_state_exists(self):
        """ModelFile.State.VALIDATING enum value exists"""
        self.assertEqual(7, ModelFile.State.VALIDATING.value)

    def test_validating_state_settable(self):
        """ModelFile state can be set to VALIDATING"""
        mf = ModelFile("test.bin", False)
        mf.state = ModelFile.State.VALIDATING
        self.assertEqual(ModelFile.State.VALIDATING, mf.state)

    def test_all_states_including_validating(self):
        """All expected states exist and have correct values"""
        expected = {
            "DEFAULT": 0,
            "DOWNLOADING": 1,
            "QUEUED": 2,
            "DOWNLOADED": 3,
            "DELETED": 4,
            "EXTRACTING": 5,
            "EXTRACTED": 6,
            "VALIDATING": 7,
        }
        for name, value in expected.items():
            state = ModelFile.State[name]
            self.assertEqual(value, state.value,
                             "State {} expected value {} got {}".format(name, value, state.value))
        logger.info("test_all_states_including_validating: all states correct")


# ===========================================================================
# Serialization test for VALIDATING state
# ===========================================================================
class TestSerializeValidatingState(unittest.TestCase):
    """Test that VALIDATING state is serialized correctly"""

    def test_serialize_validating(self):
        from web.serialize import SerializeModel
        import json

        serialize = SerializeModel()

        a = ModelFile("a", False)
        a.state = ModelFile.State.VALIDATING
        files = [a]

        # Get the SSE output and parse using the standard pattern
        stream = serialize.model(files)
        parsed = dict()
        for line in stream.split("\n"):
            if line:
                key, value = line.split(":", maxsplit=1)
                parsed[key.strip()] = value.strip()

        self.assertIn("data", parsed, "No data field found in SSE stream")
        data = json.loads(parsed["data"])
        self.assertEqual(1, len(data))
        self.assertEqual("validating", data[0]["state"])
        logger.info("test_serialize_validating: state serialized as 'validating'")
