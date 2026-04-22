#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

LOG_PATH = os.environ.get("HERMES_RUNTIME_REAL_RUNNER_LOG")
HERMES_EXECUTABLE = os.environ.get("HERMES_RUNTIME_REAL_RUNNER_EXECUTABLE", "hermes").strip() or "hermes"


def _inner_timeout_seconds() -> float:
    configured = float(os.environ.get("POLYMARKET_ALERT_BOT_JUDGMENT_TIMEOUT_SECONDS", "600"))
    slack = min(5.0, max(0.1, configured * 0.1))
    return max(0.1, configured - slack)


def log_event(event: dict) -> None:
    if not LOG_PATH:
        return
    path = Path(LOG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def main() -> int:
    payload_text = sys.stdin.read()
    if not payload_text.strip():
        print(
            json.dumps(
                {
                    "alert_kind": "degraded",
                    "cluster_action": "none",
                    "ttl_hours": 1,
                    "citations": [],
                    "triggers": [],
                    "archive_payload": {"reason": "empty_stdin"},
                },
                ensure_ascii=False,
            )
        )
        return 0

    try:
        payload_obj = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        print(
            json.dumps(
                {
                    "alert_kind": "degraded",
                    "cluster_action": "none",
                    "ttl_hours": 1,
                    "citations": [],
                    "triggers": [],
                    "archive_payload": {"reason": f"invalid_json_stdin:{exc.__class__.__name__}"},
                },
                ensure_ascii=False,
            )
        )
        return 0

    cmd = [HERMES_EXECUTABLE, "chat", "-Q", "-s", "prediction-market-analysis", "-q", payload_text]
    timeout_seconds = _inner_timeout_seconds()
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            finally:
                try:
                    process.communicate(timeout=1)
                except Exception:
                    pass
        log_event(
            {
                "payload": payload_obj,
                "cmd": cmd,
                "timeout_seconds": timeout_seconds,
                "returncode": None,
                "stdout": "",
                "stderr": "timeout",
            }
        )
        print(
            json.dumps(
                {
                    "alert_kind": "degraded",
                    "cluster_action": "none",
                    "ttl_hours": 1,
                    "citations": [],
                    "triggers": [],
                    "archive_payload": {"reason": f"hermes_timeout:{timeout_seconds}"},
                    "summary": "hermes chat timed out",
                },
                ensure_ascii=False,
            )
        )
        return 0

    if process is None:
        print(
            json.dumps(
                {
                    "alert_kind": "degraded",
                    "cluster_action": "none",
                    "ttl_hours": 1,
                    "citations": [],
                    "triggers": [],
                    "archive_payload": {"reason": "hermes_spawn_failed"},
                },
                ensure_ascii=False,
            )
        )
        return 0

    stdout = (stdout or "").strip()
    stderr = (stderr or "").strip()
    log_event(
        {
            "payload": payload_obj,
            "cmd": cmd,
            "returncode": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    )

    if process.returncode != 0:
        print(
            json.dumps(
                {
                    "alert_kind": "degraded",
                    "cluster_action": "none",
                    "ttl_hours": 1,
                    "citations": [],
                    "triggers": [],
                    "archive_payload": {"reason": f"hermes_nonzero_exit:{process.returncode}"},
                    "summary": stderr[:500] if stderr else "hermes returned nonzero exit",
                },
                ensure_ascii=False,
            )
        )
        return 0

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        print(
            json.dumps(
                {
                    "alert_kind": "degraded",
                    "cluster_action": "none",
                    "ttl_hours": 1,
                    "citations": [],
                    "triggers": [],
                    "archive_payload": {"reason": "hermes_stdout_not_json"},
                    "summary": stdout[:500],
                },
                ensure_ascii=False,
            )
        )
        return 0

    print(json.dumps(parsed, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
