import unittest

from common.job_status import JobStatus


class TestJobStatus(unittest.TestCase):
    """Test the shared JobStatus class (extracted from LftpJobStatus)."""

    def test_properties(self):
        s = JobStatus(
            job_id=1,
            job_type=JobStatus.Type.PGET,
            state=JobStatus.State.RUNNING,
            name="test.txt",
            flags="-c",
        )
        self.assertEqual(s.id, 1)
        self.assertEqual(s.type, JobStatus.Type.PGET)
        self.assertEqual(s.state, JobStatus.State.RUNNING)
        self.assertEqual(s.name, "test.txt")
        self.assertEqual(s.flags, "-c")

    def test_transfer_state_on_running(self):
        s = JobStatus(
            job_id=1,
            job_type=JobStatus.Type.PGET,
            state=JobStatus.State.RUNNING,
            name="test.txt",
            flags="",
        )
        ts = JobStatus.TransferState(100, 200, 50, 1024, 10)
        s.total_transfer_state = ts
        self.assertEqual(s.total_transfer_state.size_local, 100)
        self.assertEqual(s.total_transfer_state.size_remote, 200)
        self.assertEqual(s.total_transfer_state.percent_local, 50)
        self.assertEqual(s.total_transfer_state.speed, 1024)
        self.assertEqual(s.total_transfer_state.eta, 10)

    def test_transfer_state_on_queued_raises(self):
        s = JobStatus(
            job_id=1,
            job_type=JobStatus.Type.PGET,
            state=JobStatus.State.QUEUED,
            name="test.txt",
            flags="",
        )
        ts = JobStatus.TransferState(100, 200, 50, 1024, 10)
        with self.assertRaises(TypeError):
            s.total_transfer_state = ts

    def test_active_file_transfer_states(self):
        s = JobStatus(
            job_id=1,
            job_type=JobStatus.Type.MIRROR,
            state=JobStatus.State.RUNNING,
            name="mydir",
            flags="",
        )
        ts = JobStatus.TransferState(50, 100, 50, 512, 5)
        s.add_active_file_transfer_state("mydir/file1.txt", ts)
        files = s.get_active_file_transfer_states()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0][0], "mydir/file1.txt")
        self.assertEqual(files[0][1].speed, 512)

    def test_active_file_on_queued_raises(self):
        s = JobStatus(
            job_id=1,
            job_type=JobStatus.Type.MIRROR,
            state=JobStatus.State.QUEUED,
            name="mydir",
            flags="",
        )
        ts = JobStatus.TransferState(50, 100, 50, 512, 5)
        with self.assertRaises(TypeError):
            s.add_active_file_transfer_state("file.txt", ts)

    def test_default_transfer_state_is_none(self):
        s = JobStatus(
            job_id=1,
            job_type=JobStatus.Type.PGET,
            state=JobStatus.State.RUNNING,
            name="test.txt",
            flags="",
        )
        ts = s.total_transfer_state
        self.assertIsNone(ts.size_local)
        self.assertIsNone(ts.size_remote)
        self.assertIsNone(ts.percent_local)
        self.assertIsNone(ts.speed)
        self.assertIsNone(ts.eta)

    def test_equality(self):
        s1 = JobStatus(1, JobStatus.Type.PGET, JobStatus.State.QUEUED, "a.txt", "")
        s2 = JobStatus(1, JobStatus.Type.PGET, JobStatus.State.QUEUED, "a.txt", "")
        self.assertEqual(s1, s2)

    def test_inequality(self):
        s1 = JobStatus(1, JobStatus.Type.PGET, JobStatus.State.QUEUED, "a.txt", "")
        s2 = JobStatus(2, JobStatus.Type.PGET, JobStatus.State.QUEUED, "a.txt", "")
        self.assertNotEqual(s1, s2)

    def test_type_mirror_and_pget(self):
        self.assertEqual(JobStatus.Type.MIRROR.value, "mirror")
        self.assertEqual(JobStatus.Type.PGET.value, "pget")

    def test_state_values(self):
        self.assertEqual(JobStatus.State.QUEUED.value, 0)
        self.assertEqual(JobStatus.State.RUNNING.value, 1)
