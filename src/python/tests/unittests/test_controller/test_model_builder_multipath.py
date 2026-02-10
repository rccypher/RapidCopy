# Copyright 2024, SeedSync Contributors, All rights reserved.

import logging
import sys
import unittest
from unittest.mock import patch, MagicMock
import time

from system import SystemFile
from lftp import LftpJobStatus
from model import ModelFile
from controller import ModelBuilder
from controller.validate import ValidationStatus


class TestModelBuilderMultiPath(unittest.TestCase):
    """Tests for ModelBuilder multi-path mapping support"""

    def setUp(self):
        logger = logging.getLogger(TestModelBuilderMultiPath.__name__)
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)
        self.model_builder = ModelBuilder(num_mappings=2)
        self.model_builder.set_base_logger(logger)

    def test_files_in_mapping_0_get_mapping_index_0(self):
        """Files from mapping 0 should have mapping_index=0"""
        r_a = SystemFile("fileA", 100, False)
        self.model_builder.set_remote_files([r_a], mapping_index=0)
        model = self.model_builder.build_model()
        f = model.get_file("fileA")
        self.assertEqual(0, f.mapping_index)

    def test_files_in_mapping_1_get_mapping_index_1(self):
        """Files from mapping 1 should have mapping_index=1"""
        r_b = SystemFile("fileB", 200, False)
        self.model_builder.set_remote_files([r_b], mapping_index=1)
        model = self.model_builder.build_model()
        f = model.get_file("fileB")
        self.assertEqual(1, f.mapping_index)

    def test_files_from_different_mappings_coexist(self):
        """Files from different mappings appear in the same model"""
        r_a = SystemFile("fileA", 100, False)
        r_b = SystemFile("fileB", 200, False)
        self.model_builder.set_remote_files([r_a], mapping_index=0)
        self.model_builder.set_remote_files([r_b], mapping_index=1)
        model = self.model_builder.build_model()
        names = model.get_file_names()
        self.assertIn("fileA", names)
        self.assertIn("fileB", names)
        self.assertEqual(0, model.get_file("fileA").mapping_index)
        self.assertEqual(1, model.get_file("fileB").mapping_index)

    def test_duplicate_name_across_mappings_uses_first(self):
        """If same file name appears in two mappings, first one wins for remote"""
        r_a0 = SystemFile("dup", 100, False)
        r_a1 = SystemFile("dup", 999, False)
        self.model_builder.set_remote_files([r_a0], mapping_index=0)
        self.model_builder.set_remote_files([r_a1], mapping_index=1)
        model = self.model_builder.build_model()
        f = model.get_file("dup")
        self.assertEqual(0, f.mapping_index)
        self.assertEqual(100, f.remote_size)

    def test_local_files_per_mapping(self):
        """Local files set per-mapping are merged correctly"""
        l_a = SystemFile("localA", 50, False)
        l_b = SystemFile("localB", 75, False)
        self.model_builder.set_local_files([l_a], mapping_index=0)
        self.model_builder.set_local_files([l_b], mapping_index=1)
        model = self.model_builder.build_model()
        self.assertEqual(50, model.get_file("localA").local_size)
        self.assertEqual(75, model.get_file("localB").local_size)
        self.assertEqual(0, model.get_file("localA").mapping_index)
        self.assertEqual(1, model.get_file("localB").mapping_index)

    def test_active_files_per_mapping(self):
        """Active files set per-mapping update the correct mapping slot"""
        r_a = SystemFile("activeFile", 100, False)
        self.model_builder.set_remote_files([r_a], mapping_index=0)
        l_a = SystemFile("activeFile", 50, False)
        self.model_builder.set_active_files([l_a], mapping_index=0)
        model = self.model_builder.build_model()
        self.assertEqual(50, model.get_file("activeFile").local_size)

    def test_downloaded_state_with_mapping_index(self):
        """A file in mapping 1 can reach DOWNLOADED state"""
        r_b = SystemFile("dlfile", 200, False)
        l_b = SystemFile("dlfile", 200, False)
        self.model_builder.set_remote_files([r_b], mapping_index=1)
        self.model_builder.set_local_files([l_b], mapping_index=1)
        self.model_builder.set_downloaded_files({"dlfile"})
        model = self.model_builder.build_model()
        self.assertEqual(ModelFile.State.DOWNLOADED, model.get_file("dlfile").state)
        self.assertEqual(1, model.get_file("dlfile").mapping_index)

    def test_deleted_state_with_mapping_index(self):
        """A previously downloaded file from mapping 1 shows as DELETED when local is gone"""
        r_b = SystemFile("delfile", 200, False)
        self.model_builder.set_remote_files([r_b], mapping_index=1)
        self.model_builder.set_downloaded_files({"delfile"})
        model = self.model_builder.build_model()
        self.assertEqual(ModelFile.State.DELETED, model.get_file("delfile").state)
        self.assertEqual(1, model.get_file("delfile").mapping_index)

    def test_validating_state_with_mapping_index(self):
        """A file from mapping 1 enters VALIDATING state when validation is enabled"""
        r_b = SystemFile("valfile", 200, False)
        l_b = SystemFile("valfile", 200, False)
        self.model_builder.set_remote_files([r_b], mapping_index=1)
        self.model_builder.set_local_files([l_b], mapping_index=1)
        self.model_builder.set_downloaded_files({"valfile"})
        self.model_builder.set_validation_enabled(True)
        model = self.model_builder.build_model()
        self.assertEqual(ModelFile.State.VALIDATING, model.get_file("valfile").state)
        self.assertEqual(1, model.get_file("valfile").mapping_index)

    def test_validation_status_sets_validating_in_mapping(self):
        """Active ValidationStatus correctly sets VALIDATING for multi-mapping files"""
        r_b = SystemFile("vsfile", 200, False)
        l_b = SystemFile("vsfile", 200, False)
        self.model_builder.set_remote_files([r_b], mapping_index=1)
        self.model_builder.set_local_files([l_b], mapping_index=1)
        self.model_builder.set_downloaded_files({"vsfile"})
        self.model_builder.set_validation_statuses([ValidationStatus(name="vsfile", is_dir=False)])
        model = self.model_builder.build_model()
        self.assertEqual(ModelFile.State.VALIDATING, model.get_file("vsfile").state)

    def test_directory_in_mapping_1(self):
        """Directories from mapping 1 build correctly with children"""
        r_dir = SystemFile("mydir", 300, True)
        r_child = SystemFile("child.txt", 300, False)
        r_dir.add_child(r_child)
        l_dir = SystemFile("mydir", 300, True)
        l_child = SystemFile("child.txt", 300, False)
        l_dir.add_child(l_child)
        self.model_builder.set_remote_files([r_dir], mapping_index=1)
        self.model_builder.set_local_files([l_dir], mapping_index=1)
        self.model_builder.set_downloaded_files({"mydir"})
        model = self.model_builder.build_model()
        d = model.get_file("mydir")
        self.assertEqual(1, d.mapping_index)
        self.assertTrue(d.is_dir)
        self.assertEqual(ModelFile.State.DOWNLOADED, d.state)
        children = d.get_children()
        self.assertEqual(1, len(children))
        self.assertEqual("child.txt", children[0].name)

    def test_clear_resets_all_mappings(self):
        """clear() resets file data for all mappings"""
        r_a = SystemFile("a", 100, False)
        r_b = SystemFile("b", 200, False)
        self.model_builder.set_remote_files([r_a], mapping_index=0)
        self.model_builder.set_remote_files([r_b], mapping_index=1)
        self.model_builder.clear()
        model = self.model_builder.build_model()
        self.assertEqual(0, len(model.get_file_names()))

    def test_has_changes_after_setting_files_per_mapping(self):
        """has_changes() returns True after setting files on any mapping"""
        self.model_builder.build_model()
        self.assertFalse(self.model_builder.has_changes())
        r_b = SystemFile("new", 100, False)
        self.model_builder.set_remote_files([r_b], mapping_index=1)
        self.assertTrue(self.model_builder.has_changes())

    def test_mixed_local_and_remote_across_mappings(self):
        """Remote from mapping 0 + local from mapping 1 yields two separate files"""
        r_a = SystemFile("remoteOnly", 100, False)
        l_b = SystemFile("localOnly", 50, False)
        self.model_builder.set_remote_files([r_a], mapping_index=0)
        self.model_builder.set_local_files([l_b], mapping_index=1)
        model = self.model_builder.build_model()
        self.assertIn("remoteOnly", model.get_file_names())
        self.assertIn("localOnly", model.get_file_names())
        self.assertEqual(100, model.get_file("remoteOnly").remote_size)
        self.assertIsNone(model.get_file("remoteOnly").local_size)
        self.assertEqual(50, model.get_file("localOnly").local_size)
        self.assertIsNone(model.get_file("localOnly").remote_size)
