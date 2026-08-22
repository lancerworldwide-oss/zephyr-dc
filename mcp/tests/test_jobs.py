"""Tests for background jobs."""

from __future__ import annotations

import sys
import time

from zephyr_dc_mcp.jobs import JobStatus, reset_job_manager


def test_job_lifecycle_success():
    mgr = reset_job_manager()
    job = mgr.start([sys.executable, "-c", "print('ok')"], timeout_sec=30)
    finished = mgr.wait(job.job_id, timeout_sec=10)
    assert finished is not None
    assert finished.status == JobStatus.SUCCEEDED
    assert finished.returncode == 0
    assert "ok" in finished.stdout


def test_job_cancel():
    mgr = reset_job_manager()
    job = mgr.start(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        timeout_sec=60,
    )
    time.sleep(0.3)
    cancelled = mgr.cancel(job.job_id)
    assert cancelled is not None
    assert cancelled.status == JobStatus.CANCELLED
