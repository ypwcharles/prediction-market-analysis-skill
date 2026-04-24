from __future__ import annotations

import asyncio
import threading

import httpx
import pytest
from fastapi import FastAPI

from polymarket_alert_bot.runtime_flow import MonitorFlowSummary, ScanFlowSummary
from polymarket_alert_bot.service.app import create_app
from polymarket_alert_bot.service.auth import TELEGRAM_SECRET_HEADER
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations

INTERNAL_BEARER_TOKEN = "test-internal-bearer"
TELEGRAM_WEBHOOK_SECRET = "test-telegram-secret"


def _bearer_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _build_app(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    scan_runner=None,
    monitor_runner=None,
    report_runner=None,
    callback_runner=None,
) -> FastAPI:
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(tmp_path / ".runtime-data"))
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SERVICE_BEARER_TOKEN", INTERNAL_BEARER_TOKEN)
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_WEBHOOK_SECRET", TELEGRAM_WEBHOOK_SECRET)
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SERVICE_ENABLE_SCHEDULER", "0")

    resolved_scan_runner = scan_runner or (
        lambda: ScanFlowSummary(
            run_id="scan-run-default",
            strict_alert_ids=(),
            research_alert_ids=(),
            heartbeat_alert_id=None,
        )
    )
    resolved_monitor_runner = monitor_runner or (
        lambda: MonitorFlowSummary(
            run_id="monitor-run-default",
            delivered_alert_ids=(),
            stale_alert_ids=(),
        )
    )
    resolved_report_runner = report_runner or (lambda: "report-run-default")
    resolved_callback_runner = callback_runner or (
        lambda payload: {"handled": True, "payload": payload}
    )

    app = create_app(
        start_scheduler=False,
        scan_runner=resolved_scan_runner,
        monitor_runner=resolved_monitor_runner,
        report_runner=resolved_report_runner,
        callback_runner=resolved_callback_runner,
    )
    return app


def _request(app, method: str, path: str, **kwargs) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


def test_healthz_is_public(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    response = _request(app, "GET", "/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status_requires_bearer_auth(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    missing = _request(app, "GET", "/status")
    invalid = _request(app, "GET", "/status", headers=_bearer_header("wrong-token"))
    ok = _request(app, "GET", "/status", headers=_bearer_header(INTERNAL_BEARER_TOKEN))

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert ok.status_code == 200
    body = ok.json()
    assert body["service"]["scheduler_enabled"] is False
    assert "latest_runs" in body
    assert "counts" in body
    assert "scheduler" in body
    assert body["scheduler"]["jobs"]["scan"]["run_immediately"] is True
    assert body["scheduler"]["jobs"]["monitor"]["run_immediately"] is False
    assert body["scheduler"]["jobs"]["report"]["run_immediately"] is False


def test_status_marks_latest_scan_as_running_when_scheduler_job_is_active(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    conn = connect_db(tmp_path / ".runtime-data" / "sqlite" / "runtime.sqlite3")
    apply_migrations(conn)
    conn.execute(
        """
        INSERT INTO runs (id, run_type, status, started_at, finished_at, degraded_reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "scan-run-provisional",
            "scan",
            "degraded",
            "2026-04-24T13:37:47.531026+00:00",
            "2026-04-24T13:37:47.531026+00:00",
            "executable_checks_partial",
            "2026-04-24T13:37:47.531026+00:00",
        ],
    )
    conn.commit()
    conn.close()

    with app.state.scheduler._state_lock:
        app.state.scheduler._job_state["scan"]["is_running"] = True
        app.state.scheduler._job_state["scan"]["last_started_at"] = (
            "2026-04-24T13:37:47.528706+00:00"
        )
        app.state.scheduler._job_state["scan"]["last_finished_at"] = None

    response = _request(app, "GET", "/status", headers=_bearer_header(INTERNAL_BEARER_TOKEN))

    assert response.status_code == 200
    scan = response.json()["latest_runs"]["scan"]
    assert scan["id"] == "scan-run-provisional"
    assert scan["status"] == "running"
    assert scan["finished_at"] is None


@pytest.mark.parametrize(
    ("path", "expected_run_id"),
    [
        ("/internal/scan", "scan-run-1"),
        ("/internal/monitor", "monitor-run-1"),
        ("/internal/report", "report-run-1"),
    ],
)
def test_internal_endpoints_require_auth_and_invoke_runners(
    tmp_path,
    monkeypatch,
    path: str,
    expected_run_id: str,
):
    calls = {"scan": 0, "monitor": 0, "report": 0}

    def scan_runner():
        calls["scan"] += 1
        return ScanFlowSummary(
            run_id="scan-run-1",
            strict_alert_ids=("strict-1",),
            research_alert_ids=(),
            heartbeat_alert_id=None,
        )

    def monitor_runner():
        calls["monitor"] += 1
        return MonitorFlowSummary(
            run_id="monitor-run-1",
            delivered_alert_ids=("monitor-1",),
            stale_alert_ids=(),
        )

    def report_runner():
        calls["report"] += 1
        return "report-run-1"

    app = _build_app(
        tmp_path,
        monkeypatch,
        scan_runner=scan_runner,
        monitor_runner=monitor_runner,
        report_runner=report_runner,
    )
    unauthorized = _request(app, "POST", path)
    authorized = _request(app, "POST", path, headers=_bearer_header(INTERNAL_BEARER_TOKEN))

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["run_id"] == expected_run_id
    assert calls == {
        "scan": 1 if path == "/internal/scan" else 0,
        "monitor": 1 if path == "/internal/monitor" else 0,
        "report": 1 if path == "/internal/report" else 0,
    }


def test_telegram_webhook_requires_secret_and_routes_payload(tmp_path, monkeypatch):
    callback_payloads: list[dict[str, object]] = []

    def callback_runner(payload: dict[str, object]):
        callback_payloads.append(payload)
        return {"callback_handled": True}

    app = _build_app(
        tmp_path,
        monkeypatch,
        callback_runner=callback_runner,
    )
    missing = _request(app, "POST", "/telegram/webhook", json={"callback_query": {"id": "cb-1"}})
    invalid = _request(
        app,
        "POST",
        "/telegram/webhook",
        headers={TELEGRAM_SECRET_HEADER: "wrong-secret"},
        json={"callback_query": {"id": "cb-1"}},
    )
    malformed = _request(
        app,
        "POST",
        "/telegram/webhook",
        headers={TELEGRAM_SECRET_HEADER: TELEGRAM_WEBHOOK_SECRET},
        json=[{"not": "an-object"}],
    )
    accepted = _request(
        app,
        "POST",
        "/telegram/webhook",
        headers={TELEGRAM_SECRET_HEADER: TELEGRAM_WEBHOOK_SECRET},
        json={"callback_query": {"id": "cb-1"}},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert malformed.status_code == 400
    assert accepted.status_code == 200
    assert accepted.json()["callback_handled"] is True
    assert callback_payloads == [{"callback_query": {"id": "cb-1"}}]


def test_telegram_webhook_offloads_callback_runner_to_worker_thread(tmp_path, monkeypatch):
    callback_thread_ids: list[int] = []

    def callback_runner(payload: dict[str, object]):
        callback_thread_ids.append(threading.get_ident())
        return {"handled": True, "payload": payload}

    app = _build_app(
        tmp_path,
        monkeypatch,
        callback_runner=callback_runner,
    )
    response = _request(
        app,
        "POST",
        "/telegram/webhook",
        headers={TELEGRAM_SECRET_HEADER: TELEGRAM_WEBHOOK_SECRET},
        json={"callback_query": {"id": "cb-thread"}},
    )

    assert response.status_code == 200
    assert callback_thread_ids
    assert callback_thread_ids[0] != threading.get_ident()


def test_telegram_webhook_ignores_unsupported_updates(tmp_path, monkeypatch):
    def callback_runner(_: dict[str, object]):
        raise RuntimeError("unsupported callback payload")

    app = _build_app(
        tmp_path,
        monkeypatch,
        callback_runner=callback_runner,
    )
    ignored = _request(
        app,
        "POST",
        "/telegram/webhook",
        headers={TELEGRAM_SECRET_HEADER: TELEGRAM_WEBHOOK_SECRET},
        json={"message": {"message_id": 1, "text": "/start"}},
    )

    assert ignored.status_code == 200
    assert ignored.json() == {"ignored": True}
