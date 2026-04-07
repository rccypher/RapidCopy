import os
import signal
import subprocess
import sys
import time
import logging
import threading
import unittest

from common.job_status import JobStatus
from rclone.job_queue import JobQueue


class TestJobQueue(unittest.TestCase):
    def setUp(self):
        self.queue = JobQueue(max_parallel_jobs=2)
        logger = logging.getLogger("TestJobQueue")
        logger.addHandler(logging.StreamHandler(sys.stdout))
        self.queue.set_base_logger(logger)

    def tearDown(self):
        self.queue.shutdown()

    def test_enqueue_returns_incrementing_ids(self):
        id1 = self.queue.enqueue("a", False, ["echo", "a"], os.environ.copy())
        id2 = self.queue.enqueue("b", False, ["echo", "b"], os.environ.copy())
        self.assertEqual(id1, 1)
        self.assertEqual(id2, 2)

    def test_status_shows_queued_jobs(self):
        # Enqueue more than max_parallel so some stay queued
        # Use a slow command so jobs don't finish before we check
        env = os.environ.copy()
        self.queue.enqueue("a", False, ["sleep", "10"], env)
        self.queue.enqueue("b", False, ["sleep", "10"], env)
        self.queue.enqueue("c", False, ["sleep", "10"], env)
        # Give feeder time to dispatch first 2
        time.sleep(0.5)

        statuses = self.queue.get_statuses()
        names = {s.name for s in statuses}
        self.assertIn("a", names)
        self.assertIn("b", names)
        self.assertIn("c", names)

        # At least one should be queued (the 3rd, since max_parallel=2)
        queued = [s for s in statuses if s.state == JobStatus.State.QUEUED]
        self.assertGreaterEqual(len(queued), 1)

    def test_kill_queued_job(self):
        env = os.environ.copy()
        self.queue.enqueue("a", False, ["sleep", "30"], env)
        self.queue.enqueue("b", False, ["sleep", "30"], env)
        self.queue.enqueue("c", False, ["sleep", "30"], env)
        time.sleep(0.5)

        result = self.queue.kill_job("c")
        self.assertTrue(result)

        statuses = self.queue.get_statuses()
        names = {s.name for s in statuses}
        self.assertNotIn("c", names)

    def test_kill_running_job(self):
        env = os.environ.copy()
        self.queue.enqueue("slow", False, ["sleep", "30"], env)
        time.sleep(0.5)

        statuses = self.queue.get_statuses()
        running = [s for s in statuses if s.name == "slow" and s.state == JobStatus.State.RUNNING]
        self.assertEqual(len(running), 1)

        result = self.queue.kill_job("slow")
        self.assertTrue(result)
        time.sleep(1)

        statuses = self.queue.get_statuses()
        names = {s.name for s in statuses}
        self.assertNotIn("slow", names)

    def test_kill_nonexistent_job(self):
        result = self.queue.kill_job("nonexistent")
        self.assertFalse(result)

    def test_prioritize_queued_job(self):
        env = os.environ.copy()
        # Fill running slots
        self.queue.enqueue("a", False, ["sleep", "30"], env)
        self.queue.enqueue("b", False, ["sleep", "30"], env)
        # These will be queued
        self.queue.enqueue("c", False, ["sleep", "30"], env)
        self.queue.enqueue("d", False, ["sleep", "30"], env)
        time.sleep(0.5)

        result = self.queue.prioritize("d")
        self.assertTrue(result)

        # Verify d is now first in the pending queue
        statuses = self.queue.get_statuses()
        queued = [s for s in statuses if s.state == JobStatus.State.QUEUED]
        if len(queued) >= 2:
            self.assertEqual(queued[0].name, "d")

    def test_prioritize_nonexistent_job(self):
        result = self.queue.prioritize("nonexistent")
        self.assertFalse(result)

    def test_kill_all(self):
        env = os.environ.copy()
        self.queue.enqueue("a", False, ["sleep", "30"], env)
        self.queue.enqueue("b", False, ["sleep", "30"], env)
        self.queue.enqueue("c", False, ["sleep", "30"], env)
        time.sleep(0.5)

        self.queue.kill_all()
        time.sleep(1)

        statuses = self.queue.get_statuses()
        self.assertEqual(len(statuses), 0)

    def test_completed_job_reports_no_error(self):
        env = os.environ.copy()
        self.queue.enqueue("fast", False, ["echo", "hello"], env)
        time.sleep(1)

        error = self.queue.pop_error()
        self.assertIsNone(error)

    def test_failed_job_reports_error(self):
        env = os.environ.copy()
        self.queue.enqueue("bad", False, ["false"], env)  # 'false' returns exit code 1
        time.sleep(1)

        error = self.queue.pop_error()
        self.assertIsNotNone(error)
        self.assertIn("bad", error)

    def test_job_type_dir_vs_file(self):
        env = os.environ.copy()
        self.queue.enqueue("file1", False, ["sleep", "10"], env)
        self.queue.enqueue("dir1", True, ["sleep", "10"], env)
        time.sleep(0.5)

        statuses = self.queue.get_statuses()
        file_status = next(s for s in statuses if s.name == "file1")
        dir_status = next(s for s in statuses if s.name == "dir1")
        self.assertEqual(file_status.type, JobStatus.Type.PGET)
        self.assertEqual(dir_status.type, JobStatus.Type.MIRROR)
