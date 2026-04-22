#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

LOG_PATH = os.environ.get("HERMES_RUNTIME_REAL_RUNNER_LOG")


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

    cmd = ["hermes", "chat", "-Q", "-s", "prediction-market-analysis", "-q", payload_text]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    log_event(
        {
            "payload": payload_obj,
            "cmd": cmd,
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    )

    if completed.returncode != 0:
        print(
            json.dumps(
                {
                    "alert_kind": "degraded",
                    "cluster_action": "none",
                    "ttl_hours": 1,
                    "citations": [],
                    "triggers": [],
                    "archive_payload": {"reason": f"hermes_nonzero_exit:{completed.returncode}"},
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
