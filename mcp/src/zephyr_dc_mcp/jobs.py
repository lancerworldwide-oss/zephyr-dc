"""Background job manager for long-running firmware commands."""

from __future__ import annotations

import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

from zephyr_dc_mcp.config import get_settings
from zephyr_dc_mcp.process import truncate_text


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class Job:
    job_id: str
    argv: list[str]
    cwd: str | None
    status: JobStatus = JobStatus.PENDING
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    _proc: subprocess.Popen[str] | None = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self, *, include_output: bool = True, log_tail: int | None = None) -> dict:
        with self._lock:
            stdout = self.stdout
            stderr = self.stderr
            if log_tail is not None and log_tail >= 0:
                stdout = stdout[-log_tail:] if stdout else ""
                stderr = stderr[-log_tail:] if stderr else ""
            data = {
                "job_id": self.job_id,
                "argv": self.argv,
                "cwd": self.cwd,
                "status": self.status.value,
                "returncode": self.returncode,
                "created_at": self.created_at,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "error": self.error,
                "truncated": self.truncated,
            }
            if include_output:
                data["stdout"] = stdout
                data["stderr"] = stderr
            return data


class JobManager:
    """Thread-backed subprocess job tracker."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout_sec: float | None = None,
    ) -> Job:
        if not argv:
            raise ValueError("argv must not be empty")
        settings = get_settings()
        if timeout_sec is None:
            timeout_sec = float(settings.default_job_timeout_sec)

        job_id = str(uuid.uuid4())
        job = Job(job_id=job_id, argv=list(argv), cwd=cwd)
        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(
            target=self._run_job,
            args=(job, env, timeout_sec),
            name=f"job-{job_id[:8]}",
            daemon=True,
        )
        thread.start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> Job | None:
        job = self.get(job_id)
        if job is None:
            return None
        with job._lock:
            if job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMED_OUT):
                return job
            proc = job._proc
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            job.status = JobStatus.CANCELLED
            job.finished_at = time.time()
            job.error = "cancelled by user"
        return job

    def wait(self, job_id: str, timeout_sec: float | None = None) -> Job | None:
        job = self.get(job_id)
        if job is None:
            return None
        deadline = None if timeout_sec is None else time.time() + timeout_sec
        while True:
            with job._lock:
                if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
                    return job
            if deadline is not None and time.time() >= deadline:
                return job
            time.sleep(0.2)

    def _run_job(
        self,
        job: Job,
        env: Mapping[str, str] | None,
        timeout_sec: float,
    ) -> None:
        settings = get_settings()
        max_chars = settings.max_output_chars
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        with job._lock:
            job.status = JobStatus.RUNNING
            job.started_at = time.time()

        try:
            proc = subprocess.Popen(
                job.argv,
                cwd=job.cwd,
                env=merged_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
            )
        except OSError as exc:
            with job._lock:
                job.status = JobStatus.FAILED
                job.error = str(exc)
                job.finished_at = time.time()
                job.returncode = -1
            return

        with job._lock:
            job._proc = proc

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        def _reader(stream, chunks: list[str]) -> None:
            try:
                for line in iter(stream.readline, ""):
                    chunks.append(line)
                    joined = "".join(chunks)
                    truncated, was_trunc = truncate_text(joined, max_chars)
                    with job._lock:
                        if stream is proc.stdout:
                            job.stdout = truncated
                        else:
                            job.stderr = truncated
                        job.truncated = job.truncated or was_trunc
                    if was_trunc:
                        chunks[:] = [truncated]
            finally:
                stream.close()

        t_out = threading.Thread(target=_reader, args=(proc.stdout, stdout_chunks), daemon=True)
        t_err = threading.Thread(target=_reader, args=(proc.stderr, stderr_chunks), daemon=True)
        t_out.start()
        t_err.start()

        try:
            returncode = proc.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            t_out.join(timeout=2)
            t_err.join(timeout=2)
            with job._lock:
                if job.status != JobStatus.CANCELLED:
                    job.status = JobStatus.TIMED_OUT
                    job.error = f"timed out after {timeout_sec}s"
                    job.returncode = -1
                    job.finished_at = time.time()
            return

        t_out.join(timeout=2)
        t_err.join(timeout=2)

        with job._lock:
            if job.status == JobStatus.CANCELLED:
                return
            job.returncode = returncode
            job.finished_at = time.time()
            job.status = JobStatus.SUCCEEDED if returncode == 0 else JobStatus.FAILED


_JOB_MANAGER: JobManager | None = None


def get_job_manager() -> JobManager:
    global _JOB_MANAGER
    if _JOB_MANAGER is None:
        _JOB_MANAGER = JobManager()
    return _JOB_MANAGER


def reset_job_manager() -> JobManager:
    global _JOB_MANAGER
    _JOB_MANAGER = JobManager()
    return _JOB_MANAGER
