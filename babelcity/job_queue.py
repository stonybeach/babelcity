"""In-memory job queue with thread-safe operations."""

import logging
import threading
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"


@dataclass
class Job:
    id: str
    job_type: str  # Glossary, Translation, QA
    project_id: str
    project_name: str
    volume_id: str
    volume_number: str
    config_id: str
    params: dict = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    progress_completed: int = 0
    progress_total: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    result_message: str = ""


class JobQueue:
    """Singleton in-memory job queue."""

    def __init__(self):
        self._lock = threading.Lock()
        self._pending = []  # Ordered list of Job
        self._completed = []
        self._running: Optional[Job] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def is_running(self):
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def is_paused(self):
        """Return True if the job queue is currently paused."""
        return self._stop_event.is_set()

    def add_job(self, job: Job):
        with self._lock:
            self._pending.append(job)

    def start(self):
        if self.is_running:
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self.worker_loop, daemon=True)
        self._worker_thread.start()

    def pause(self):
        self._stop_event.set()
        # Mark running job as paused so executor can check
        with self._lock:
            if self._running:
                self._running.status = JobStatus.PENDING
                self._pending.insert(0, self._running)
                self._running = None
        # Wait for worker to finish
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)

    def remove_job(self, job_id: str):
        with self._lock:
            self._pending = [j for j in self._pending if j.id != job_id]

    def clear_pending(self):
        with self._lock:
            self._pending.clear()

    def clear_failed(self):
        with self._lock:
            self._completed = [j for j in self._completed if j.status != JobStatus.FAILED]

    def move_up(self, job_id: str):
        with self._lock:
            idx = next((i for i, j in enumerate(self._pending) if j.id == job_id), -1)
            if idx > 0:
                self._pending[idx], self._pending[idx - 1] = self._pending[idx - 1], self._pending[idx]

    def move_down(self, job_id: str):
        with self._lock:
            idx = next((i for i, j in enumerate(self._pending) if j.id == job_id), -1)
            if 0 <= idx < len(self._pending) - 1:
                self._pending[idx], self._pending[idx + 1] = self._pending[idx + 1], self._pending[idx]

    def move_to_top(self, job_id: str):
        with self._lock:
            job = next((j for j in self._pending if j.id == job_id), None)
            if job:
                self._pending.remove(job)
                self._pending.insert(0, job)

    def move_to_bottom(self, job_id: str):
        with self._lock:
            job = next((j for j in self._pending if j.id == job_id), None)
            if job:
                self._pending.remove(job)
                self._pending.append(job)

    def repeat_job(self, job_id: str):
        with self._lock:
            job = next((j for j in self._completed if j.id == job_id), None)
            if job:
                job.status = JobStatus.PENDING
                self._completed.remove(job)
                self._pending.append(job)

    def remove_completed(self, job_id: str):
        with self._lock:
            self._completed = [j for j in self._completed if j.id != job_id]

    def clear_completed(self):
        with self._lock:
            self._completed.clear()

    def delete_job(self, job_id: str):
        """Delete a job. Running jobs cannot be deleted."""
        with self._lock:
            # Check running
            if self._running and self._running.id == job_id:
                return False  # Cannot delete running job
            # Check pending
            self._pending = [j for j in self._pending if j.id != job_id]
            # Check completed
            self._completed = [j for j in self._completed if j.id != job_id]
            return True

    def get_all_jobs(self):
        with self._lock:
            all_jobs = []
            # Running first
            if self._running:
                all_jobs.append(self._running)
            # Then pending in order
            all_jobs.extend(self._pending)
            # Then completed
            all_jobs.extend(self._completed)
            return all_jobs

    def update_progress(self, job_id: str, completed: int, total: int):
        with self._lock:
            if self._running and self._running.id == job_id:
                self._running.progress_completed = completed
                self._running.progress_total = total
        try:
            from .ws import broadcast_progress
            broadcast_progress(job_id, completed, total)
        except Exception:
            pass

    def _broadcast_status(self, job_id: str, status: str):
        try:
            from .ws import broadcast_status
            broadcast_status(job_id, status)
        except Exception:
            pass

    def worker_loop(self):
        """Background worker loop."""
        from .job_executors import execute_job, JobPausedException

        while not self._stop_event.is_set():
            # Pick next pending job
            with self._lock:
                if not self._pending:
                    self._running = None
                    logger.info("Worker loop: no pending jobs, exiting.")
                    break  # No more jobs
                job = self._pending.pop(0)
                job.status = JobStatus.RUNNING
                self._running = job

            self._broadcast_status(job.id, job.status.value)
            logger.info(f"Worker loop: starting job {job.id} type={job.job_type} project={job.project_name} volume={job.volume_number}")

            # Execute
            try:
                execute_job(
                    job,
                    lambda c, t: self.update_progress(job.id, c, t),
                    should_stop_callback=lambda: self._stop_event.is_set(),
                )
                job.status = JobStatus.COMPLETED
                logger.info(f"Worker loop: job {job.id} completed successfully.")
            except JobPausedException:
                logger.info(f"Worker loop: job {job.id} was paused, re-queuing.")
                with self._lock:
                    job.status = JobStatus.PENDING
                    if not any(j.id == job.id for j in self._pending):
                        self._pending.insert(0, job)
                    self._running = None
                self._broadcast_status(job.id, job.status.value)
                return
            except Exception as e:
                # Check if paused (legacy path: pause() may have already set status)
                with self._lock:
                    if job.status == JobStatus.PENDING:
                        logger.info(f"Worker loop: job {job.id} was paused, re-queuing.")
                        return  # Job already moved to pending, don't add to completed
                job.status = JobStatus.FAILED
                job.result_message = str(e)
                logger.error(f"Worker loop: job {job.id} FAILED with error: {e}", exc_info=True)

            self._broadcast_status(job.id, job.status.value)

            # Move to completed
            with self._lock:
                if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    self._completed.append(job)
                    self._running = None


job_queue = JobQueue()