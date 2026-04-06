# Thread-safe job queue for rclone transfers.
# Uses ThreadPoolExecutor for subprocess execution and a custom deque for priority support.

import contextlib
import logging
import os
import selectors
import signal
import subprocess
import threading
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum

from common.job_status import JobStatus

from .progress_parser import RcloneProgressParser


class _JobState(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class _Job:
    """Internal representation of a transfer job."""

    name: str
    is_dir: bool
    command: list[str]
    env: dict[str, str]
    job_id: int
    state: _JobState = _JobState.QUEUED
    process: subprocess.Popen | None = field(default=None, repr=False)
    future: Future | None = field(default=None, repr=False)
    total_transfer_state: JobStatus.TransferState = field(
        default_factory=lambda: JobStatus.TransferState(None, None, None, None, None)
    )
    active_files: dict[str, JobStatus.TransferState] = field(default_factory=dict)
    error: str | None = None
    kill_event: threading.Event = field(default_factory=threading.Event)


class JobQueue:
    """
    Manages rclone transfer jobs with a priority queue and thread pool.

    - Pending jobs sit in a deque (supports prioritize = move to front)
    - A feeder thread dispatches jobs to a ThreadPoolExecutor
    - Each worker runs an rclone subprocess with non-blocking stderr reading
    - status() returns a thread-safe snapshot of all jobs
    """

    def __init__(self, max_parallel_jobs: int = 2):
        self.logger = logging.getLogger("JobQueue")
        self._lock = threading.Lock()
        self._pending: deque[_Job] = deque()
        self._running: dict[str, _Job] = {}  # name -> job
        self._errors: list[str] = []
        self._next_id = 1
        self._max_parallel_jobs = max_parallel_jobs
        self._executor = ThreadPoolExecutor(max_workers=max_parallel_jobs)
        self._progress_parser = RcloneProgressParser()
        self._shutdown_event = threading.Event()

        # Feeder thread moves jobs from pending deque to executor
        self._feeder_thread = threading.Thread(
            target=self._feeder_loop, daemon=True, name="rclone-job-feeder"
        )
        self._feeder_condition = threading.Condition(self._lock)
        self._feeder_thread.start()

    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild("JobQueue")
        self._progress_parser.set_base_logger(self.logger)

    def enqueue(self, name: str, is_dir: bool, command: list[str], env: dict[str, str]) -> int:
        """Add a job to the pending queue. Non-blocking. Returns the job ID."""
        with self._feeder_condition:
            job_id = self._next_id
            self._next_id += 1
            job = _Job(name=name, is_dir=is_dir, command=command, env=env, job_id=job_id)
            self._pending.append(job)
            self._feeder_condition.notify()
        return job_id

    def get_statuses(self) -> list[JobStatus]:
        """Return a snapshot of all queued and running jobs as JobStatus objects."""
        statuses = []
        with self._lock:
            # Queued jobs
            for job in self._pending:
                status = JobStatus(
                    job_id=job.job_id,
                    job_type=JobStatus.Type.MIRROR if job.is_dir else JobStatus.Type.PGET,
                    state=JobStatus.State.QUEUED,
                    name=job.name,
                    flags="",
                )
                statuses.append(status)

            # Running jobs
            for job in self._running.values():
                status = JobStatus(
                    job_id=job.job_id,
                    job_type=JobStatus.Type.MIRROR if job.is_dir else JobStatus.Type.PGET,
                    state=JobStatus.State.RUNNING,
                    name=job.name,
                    flags="",
                )
                status.total_transfer_state = job.total_transfer_state
                for filename, ts in job.active_files.items():
                    status.add_active_file_transfer_state(filename, ts)
                statuses.append(status)

        return statuses

    def kill_job(self, name: str) -> bool:
        """
        Kill a queued or running job by name. Atomic under lock.
        Returns True if the job was found.
        """
        with self._lock:
            # Check pending queue first
            for i, job in enumerate(self._pending):
                if job.name == name:
                    del self._pending[i]
                    self.logger.debug("Removed queued job '%s'", name)
                    return True

            # Check running jobs
            job = self._running.get(name)
            if job and job.process:
                self.logger.debug("Killing running job '%s' (pid=%d)", name, job.process.pid)
                job.kill_event.set()
                self._terminate_process(job.process)
                return True

        self.logger.debug("Kill failed to find job '%s'", name)
        return False

    def kill_all(self):
        """Kill all queued and running jobs."""
        with self._lock:
            self._pending.clear()
            for job in list(self._running.values()):
                if job.process:
                    job.kill_event.set()
                    self._terminate_process(job.process)

    def prioritize(self, name: str) -> bool:
        """Move a queued job to the front of the pending queue."""
        with self._lock:
            for i, job in enumerate(self._pending):
                if job.name == name:
                    del self._pending[i]
                    self._pending.appendleft(job)
                    self.logger.debug("Prioritized queued job '%s'", name)
                    return True
        self.logger.debug("Prioritize failed to find queued job '%s'", name)
        return False

    def pop_error(self) -> str | None:
        """Pop the oldest error from the error list, or None."""
        with self._lock:
            if self._errors:
                return self._errors.pop(0)
        return None

    def shutdown(self):
        """Shut down the job queue. Kills all jobs and stops the feeder thread."""
        self._shutdown_event.set()
        self.kill_all()
        with self._feeder_condition:
            self._feeder_condition.notify_all()
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _feeder_loop(self):
        """Feeder thread: moves jobs from pending deque to executor."""
        while not self._shutdown_event.is_set():
            job = None
            with self._feeder_condition:
                while not self._pending and not self._shutdown_event.is_set():
                    self._feeder_condition.wait(timeout=1.0)
                if self._shutdown_event.is_set():
                    break
                if self._pending:
                    # Only dispatch if we have capacity
                    if len(self._running) < self._max_parallel_jobs:
                        job = self._pending.popleft()
                    else:
                        # Wait for a running job to finish
                        self._feeder_condition.wait(timeout=1.0)
                        continue

            if job:
                self._dispatch_job(job)

    def _dispatch_job(self, job: _Job):
        """Submit a job to the executor."""
        with self._lock:
            job.state = _JobState.RUNNING
            self._running[job.name] = job
        job.future = self._executor.submit(self._run_job, job)

    def _run_job(self, job: _Job):
        """Worker function: runs an rclone subprocess and reads progress."""
        try:
            self.logger.info("Starting rclone job '%s': %s", job.name, " ".join(job.command))
            proc = subprocess.Popen(
                job.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=job.env,
                start_new_session=True,  # own process group for clean kill
            )
            with self._lock:
                job.process = proc

            # Non-blocking stderr reader using selectors
            # Keep last N stderr lines for error diagnosis
            recent_stderr: list[str] = []
            sel = selectors.DefaultSelector()
            try:
                sel.register(proc.stderr, selectors.EVENT_READ)
                while proc.poll() is None:
                    if job.kill_event.is_set():
                        break
                    events = sel.select(timeout=1.0)
                    if events:
                        line = proc.stderr.readline()
                        if line:
                            decoded = line.decode("utf-8", "replace")
                            recent_stderr.append(decoded.rstrip())
                            if len(recent_stderr) > 20:
                                recent_stderr.pop(0)
                            self._process_progress_line(job, decoded)
            finally:
                sel.close()

            # Read any remaining stderr
            remaining = proc.stderr.read()
            if remaining:
                for line in remaining.decode("utf-8", "replace").splitlines():
                    recent_stderr.append(line.rstrip())
                    if len(recent_stderr) > 20:
                        recent_stderr.pop(0)
                    self._process_progress_line(job, line)

            proc.wait()

            if proc.returncode != 0 and not job.kill_event.is_set():
                # Extract error/fatal messages from recent stderr for diagnosis
                error_details = [l for l in recent_stderr if '"error"' in l or '"fatal"' in l]
                detail_str = error_details[-1] if error_details else "; ".join(recent_stderr[-3:])
                error_msg = f"rclone job '{job.name}' failed (exit {proc.returncode}): {detail_str}"
                self.logger.warning(error_msg)
                with self._lock:
                    job.state = _JobState.FAILED
                    job.error = error_msg
                    self._errors.append(error_msg)
            else:
                with self._lock:
                    job.state = _JobState.COMPLETED
                self.logger.info("rclone job '%s' completed", job.name)

        except Exception as e:
            error_msg = f"rclone job '{job.name}' error: {e}"
            self.logger.exception(error_msg)
            with self._lock:
                job.state = _JobState.FAILED
                job.error = error_msg
                self._errors.append(error_msg)
        finally:
            # Clean up: remove from running, reap process
            with self._lock:
                self._running.pop(job.name, None)
            if job.process:
                try:
                    job.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._terminate_process(job.process)
                    job.process.wait()
            # Notify feeder that a slot is available
            with self._feeder_condition:
                self._feeder_condition.notify()

    def _process_progress_line(self, job: _Job, line: str):
        """Parse a progress line and update job state."""
        result = self._progress_parser.parse_line(line)
        if result:
            with self._lock:
                job.total_transfer_state = result["total"]
                job.active_files = result["files"]

    @staticmethod
    def _terminate_process(proc: subprocess.Popen):
        """Two-phase kill: SIGTERM, wait, then SIGKILL."""
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            return
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=5)
