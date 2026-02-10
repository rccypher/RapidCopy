# Copyright 2024, SeedSync Contributors, All rights reserved.

import unittest
import json

from .test_serialize import parse_stream
from web.serialize import SerializeModel
from model import ModelFile


class TestSerializeModelMappingIndex(unittest.TestCase):
    """Tests for mapping_index serialization in the model stream"""

    def test_mapping_index_none_by_default(self):
        """mapping_index defaults to None when not set"""
        serialize = SerializeModel()
        a = ModelFile("a", False)
        out = parse_stream(serialize.model([a]))
        data = json.loads(out["data"])
        self.assertIsNone(data[0]["mapping_index"])

    def test_mapping_index_zero(self):
        """mapping_index=0 serializes correctly"""
        serialize = SerializeModel()
        a = ModelFile("a", False)
        a.mapping_index = 0
        out = parse_stream(serialize.model([a]))
        data = json.loads(out["data"])
        self.assertEqual(0, data[0]["mapping_index"])

    def test_mapping_index_nonzero(self):
        """mapping_index=1 serializes correctly"""
        serialize = SerializeModel()
        a = ModelFile("a", False)
        a.mapping_index = 1
        out = parse_stream(serialize.model([a]))
        data = json.loads(out["data"])
        self.assertEqual(1, data[0]["mapping_index"])

    def test_mapping_index_in_update_event(self):
        """mapping_index appears in update events"""
        serialize = SerializeModel()
        a = ModelFile("a", False)
        a.mapping_index = 2
        out = parse_stream(
            serialize.update_event(SerializeModel.UpdateEvent(
                SerializeModel.UpdateEvent.Change.ADDED, None, a
            ))
        )
        data = json.loads(out["data"])
        self.assertEqual(2, data["new_file"]["mapping_index"])

    def test_mapping_index_in_children(self):
        """mapping_index is serialized for child files too"""
        serialize = SerializeModel()
        parent = ModelFile("parent", True)
        parent.mapping_index = 1
        child = ModelFile("child", False)
        child.mapping_index = 1
        parent.add_child(child)
        out = parse_stream(serialize.model([parent]))
        data = json.loads(out["data"])
        self.assertEqual(1, data[0]["mapping_index"])
        # Children don't inherit mapping_index from model - they have their own default
        self.assertIn("mapping_index", data[0]["children"][0])

    def test_multiple_files_different_mapping_indices(self):
        """Multiple files with different mapping_indices serialize correctly"""
        serialize = SerializeModel()
        a = ModelFile("a", False)
        a.mapping_index = 0
        b = ModelFile("b", False)
        b.mapping_index = 1
        c = ModelFile("c", False)
        c.mapping_index = 2
        out = parse_stream(serialize.model([a, b, c]))
        data = json.loads(out["data"])
        self.assertEqual(0, data[0]["mapping_index"])
        self.assertEqual(1, data[1]["mapping_index"])
        self.assertEqual(2, data[2]["mapping_index"])


class TestSerializeModelValidatingState(unittest.TestCase):
    """Tests for VALIDATING state serialization"""

    def test_validating_state_serialized(self):
        """VALIDATING state is serialized as 'validating'"""
        serialize = SerializeModel()
        a = ModelFile("a", False)
        a.state = ModelFile.State.VALIDATING
        out = parse_stream(serialize.model([a]))
        data = json.loads(out["data"])
        self.assertEqual("validating", data[0]["state"])

    def test_all_states_serialized(self):
        """All 8 states including VALIDATING serialize correctly"""
        serialize = SerializeModel()
        states = [
            (ModelFile.State.DEFAULT, "default"),
            (ModelFile.State.QUEUED, "queued"),
            (ModelFile.State.DOWNLOADING, "downloading"),
            (ModelFile.State.DOWNLOADED, "downloaded"),
            (ModelFile.State.DELETED, "deleted"),
            (ModelFile.State.EXTRACTING, "extracting"),
            (ModelFile.State.EXTRACTED, "extracted"),
            (ModelFile.State.VALIDATING, "validating"),
        ]
        files = []
        for state, _ in states:
            f = ModelFile("file_{}".format(state.name.lower()), False)
            f.state = state
            files.append(f)
        out = parse_stream(serialize.model(files))
        data = json.loads(out["data"])
        for i, (_, expected_str) in enumerate(states):
            self.assertEqual(expected_str, data[i]["state"])
