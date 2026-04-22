from __future__ import annotations

import threading

from polymarket_alert_bot.service.scheduler import RuntimeServiceScheduler, ScheduledJob
from polymarket_alert_bot.storage.locks import LockHeldError


def test_run_job_now_updates_snapshot_fields():
    call_log: list[str] = []
    scheduler = RuntimeServiceScheduler(
        [
            ScheduledJob(
                name="scan",
                interval_seconds=60.0,
                runner=lambda: call_log.append("scan"),
            )
        ]
    )

    assert scheduler.run_job_now("scan") is True
    snapshot = scheduler.snapshot()
    job = snapshot["jobs"]["scan"]

    assert call_log == ["scan"]
    assert snapshot["running"] is False
    assert job["run_count"] == 1
    assert job["last_started_at"] is not None
    assert job["last_finished_at"] is not None
    assert job["last_error"] is None
    assert job["is_running"] is False


def test_run_job_now_captures_runner_error():
    def _raise_error():
        raise ValueError("boom")

    scheduler = RuntimeServiceScheduler(
        [
            ScheduledJob(
                name="scan",
                interval_seconds=60.0,
                runner=_raise_error,
            )
        ]
    )

    assert scheduler.run_job_now("scan") is False
    snapshot = scheduler.snapshot()
    job = snapshot["jobs"]["scan"]

    assert job["run_count"] == 1
    assert job["last_started_at"] is not None
    assert job["last_finished_at"] is not None
    assert job["last_error"].startswith("ValueError: boom")
    assert job["is_running"] is False


def test_run_job_now_rejects_overlapping_execution():
    started = threading.Event()
    unblock = threading.Event()
    call_count = 0
    first_result: list[bool] = []
    count_lock = threading.Lock()

    def _blocking_runner():
        nonlocal call_count
        with count_lock:
            call_count += 1
        started.set()
        assert unblock.wait(timeout=1.0)

    scheduler = RuntimeServiceScheduler(
        [
            ScheduledJob(
                name="scan",
                interval_seconds=60.0,
                runner=_blocking_runner,
            )
        ]
    )

    def _run_first_call():
        first_result.append(scheduler.run_job_now("scan"))

    thread = threading.Thread(target=_run_first_call, daemon=True)
    thread.start()
    assert started.wait(timeout=1.0)

    try:
        second_result = scheduler.run_job_now("scan")
    finally:
        unblock.set()
        thread.join(timeout=1.0)

    assert first_result == [True]
    assert second_result is False
    assert call_count == 1


def test_start_runs_short_interval_jobs_with_fake_runner_callbacks():
    enough_runs = threading.Event()
    call_count = 0
    count_lock = threading.Lock()

    def _runner():
        nonlocal call_count
        with count_lock:
            call_count += 1
            if call_count >= 2:
                enough_runs.set()

    scheduler = RuntimeServiceScheduler(
        [
            ScheduledJob(
                name="monitor",
                interval_seconds=0.02,
                runner=_runner,
                run_immediately=True,
            )
        ]
    )
    scheduler.start()
    try:
        assert enough_runs.wait(timeout=1.0)
    finally:
        scheduler.stop()

    snapshot = scheduler.snapshot()
    job = snapshot["jobs"]["monitor"]
    assert snapshot["running"] is False
    assert job["run_count"] >= 2
    assert job["last_error"] is None


def test_start_retries_immediate_job_once_when_lock_is_held():
    retried_successfully = threading.Event()
    call_count = 0
    count_lock = threading.Lock()

    def _runner():
        nonlocal call_count
        with count_lock:
            call_count += 1
            current_call = call_count
        if current_call == 1:
            raise LockHeldError("lock already held: /tmp/scan.lock")
        retried_successfully.set()

    scheduler = RuntimeServiceScheduler(
        [
            ScheduledJob(
                name="scan",
                interval_seconds=60.0,
                runner=_runner,
                run_immediately=True,
                startup_retry_attempts=1,
                startup_retry_delay_seconds=0.01,
            )
        ]
    )

    scheduler.start()
    try:
        assert retried_successfully.wait(timeout=1.0)
    finally:
        scheduler.stop()

    snapshot = scheduler.snapshot()
    job = snapshot["jobs"]["scan"]
    assert call_count == 2
    assert job["run_count"] == 2
    assert job["last_error"] is None
    assert job["last_finished_at"] is not None
