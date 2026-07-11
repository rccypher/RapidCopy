# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
import json

from common import PersistError
from controller import ControllerPersist


class TestControllerPersist(unittest.TestCase):
    def test_from_str(self):
        # Old format (backward compat): plain "downloaded" list
        content = """
        {
            "downloaded": ["one", "two", "th ree", "fo.ur"],
            "extracted": ["fi\\"ve", "si@x", "se\\\\ven", "ei-ght"]
        }
        """
        persist = ControllerPersist.from_str(content)
        golden_downloaded = {"one", "two", "th ree", "fo.ur"}
        golden_extracted = {"fi\"ve", "si@x", "se\\ven", "ei-ght"}
        self.assertEqual(golden_downloaded, persist.downloaded_file_names)
        self.assertEqual(golden_extracted, persist.extracted_file_names)

    def test_to_str(self):
        persist = ControllerPersist()
        persist.record_download("one")
        persist.record_download("two")
        persist.record_download("th ree")
        persist.record_download("fo.ur")
        persist.extracted_file_names.add("fi\"ve")
        persist.extracted_file_names.add("si@x")
        persist.extracted_file_names.add("se\\ven")
        persist.extracted_file_names.add("ei-ght")
        dct = json.loads(persist.to_str())
        self.assertTrue("downloaded_timestamps" in dct)
        self.assertEqual({"one", "two", "th ree", "fo.ur"}, set(dct["downloaded_timestamps"].keys()))
        self.assertTrue("extracted" in dct)
        self.assertEqual({"fi\"ve", "si@x", "se\\ven", "ei-ght"}, set(dct["extracted"]))

    def test_to_and_from_str(self):
        persist = ControllerPersist()
        persist.record_download("one")
        persist.record_download("two")
        persist.record_download("th ree")
        persist.record_download("fo.ur")
        persist.extracted_file_names.add("fi\"ve")
        persist.extracted_file_names.add("si@x")
        persist.extracted_file_names.add("se\\ven")
        persist.extracted_file_names.add("ei-ght")

        persist_actual = ControllerPersist.from_str(persist.to_str())
        self.assertEqual(
            persist.downloaded_file_names,
            persist_actual.downloaded_file_names
        )
        self.assertEqual(
            persist.extracted_file_names,
            persist_actual.extracted_file_names
        )

    def test_persist_read_error(self):
        # bad pattern
        content = """
        {
            "downloaded": [bad string],
            "extracted": []
        }
        """
        with self.assertRaises(PersistError):
            ControllerPersist.from_str(content)
        content = """
        {
            "downloaded": [],
            "extracted": [bad string]
        }
        """
        with self.assertRaises(PersistError):
            ControllerPersist.from_str(content)

        # empty json
        content = ""
        with self.assertRaises(PersistError):
            ControllerPersist.from_str(content)

        # missing extracted key (should still raise)
        content = """
        {
            "downloaded": []
        }
        """
        with self.assertRaises(PersistError):
            ControllerPersist.from_str(content)

        # missing extracted key (new format, should still raise)
        content = """
        {
            "downloaded_timestamps": {}
        }
        """
        with self.assertRaises(PersistError):
            ControllerPersist.from_str(content)

        # malformed
        content = "{"
        with self.assertRaises(PersistError):
            ControllerPersist.from_str(content)


class TestControllerPersistConcurrency(unittest.TestCase):
    """Regression: to_str() must not raise 'changed size during iteration' when the
    controller thread mutates the tracking collections concurrently."""

    def test_to_str_is_safe_under_concurrent_mutation(self):
        import threading

        persist = ControllerPersist()
        stop = threading.Event()
        errors = []

        def mutate():
            i = 0
            while not stop.is_set():
                # Bounded key space so the collections churn (add/remove) without
                # growing unbounded — we're testing the lock, not serialization cost.
                k = i % 200
                persist.record_download("file_{}".format(k))
                persist.add_extracted_file("arc_{}".format(k))
                persist.remove_download("file_{}".format((k + 1) % 200))
                persist.discard_extracted_files({"arc_{}".format((k + 1) % 200)})
                i += 1

        writer = threading.Thread(target=mutate)
        writer.start()
        try:
            # Serialize repeatedly while the writer thread churns the collections.
            for _ in range(2000):
                try:
                    out = persist.to_str()
                    json.loads(out)  # must always be valid JSON
                except Exception as e:  # noqa: BLE001 - capture any race error
                    errors.append(e)
                    break
        finally:
            stop.set()
            writer.join()

        self.assertEqual(errors, [], "to_str() raced with mutation: {}".format(errors))
