from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from polymarket_alert_bot.storage.locks import LockHeldError

Runner = Callable[[], Any]


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    interval_seconds: float
    runner: Runner
    run_immediately: bool = False
    startup_retry_attempts: int = 0
    startup_retry_delay_seconds: float = 0.0


class RuntimeServiceScheduler:
    def __init__(self, jobs: list[ScheduledJob]) -> None:
        self._jobs = {job.name: job for job in jobs}
        self._threads: dict[str, threading.Thread] = {}
        self._locks = {job.name: threading.Lock() for job in jobs}
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._started = False
        self._job_state: dict[str, dict[str, Any]] = {
            job.name: {
                "interval_seconds": job.interval_seconds,
                "run_immediately": job.run_immediately,
                "startup_retry_attempts": job.startup_retry_attempts,
                "startup_retry_delay_seconds": job.startup_retry_delay_seconds,
                "run_count": 0,
                "last_started_at": None,
                "last_finished_at": None,
                "last_error": None,
                "is_running": False,
            }
            for job in jobs
        }

    def start(self) -> None:
        with self._state_lock:
            if self._started:
                return
            self._started = True
            self._stop_event.clear()
        for job in self._jobs.values():
            thread = threading.Thread(
                target=self._run_loop,
                args=(job,),
                name=f"runtime-scheduler-{job.name}",
                daemon=True,
            )
            self._threads[job.name] = thread
            thread.start()

    def stop(self, *, timeout_seconds: float = 1.0) -> None:
        with self._state_lock:
            if not self._started:
                return
            self._started = False
            self._stop_event.set()
        for thread in self._threads.values():
            thread.join(timeout=timeout_seconds)
        self._threads.clear()

    def run_job_now(self, name: str) -> bool:
        job = self._jobs[name]
        succeeded, _ = self._run_job(job)
        return succeeded

    def snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            jobs = {name: dict(state) for name, state in self._job_state.items()}
            running = self._started and not self._stop_event.is_set()
        return {
            "running": running,
            "jobs": jobs,
        }

    def _run_loop(self, job: ScheduledJob) -> None:
        if job.run_immediately:
            succeeded, error = self._run_job(job)
            retries_remaining = job.startup_retry_attempts
            while not succeeded and retries_remaining > 0 and isinstance(error, LockHeldError):
                if self._stop_event.wait(job.startup_retry_delay_seconds):
                    return
                succeeded, error = self._run_job(job)
                retries_remaining -= 1
        while not self._stop_event.wait(job.interval_seconds):
            self._run_job(job)

    def _run_job(self, job: ScheduledJob) -> tuple[bool, Exception | None]:
        lock = self._locks[job.name]
        if not lock.acquire(blocking=False):
            return False, None
        started_at = _now_iso()
        with self._state_lock:
            state = self._job_state[job.name]
            state["is_running"] = True
            state["last_started_at"] = started_at
            state["last_error"] = None
        try:
            job.runner()
        except Exception as exc:
            with self._state_lock:
                state = self._job_state[job.name]
                state["last_error"] = f"{exc.__class__.__name__}: {exc}"
            return False, exc
        finally:
            finished_at = _now_iso()
            with self._state_lock:
                state = self._job_state[job.name]
                state["is_running"] = False
                state["last_finished_at"] = finished_at
                state["run_count"] += 1
            lock.release()
        return True, None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
