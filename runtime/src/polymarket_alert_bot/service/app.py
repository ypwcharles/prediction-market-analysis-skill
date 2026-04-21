from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request, status

from polymarket_alert_bot.calibration.report_writer import run_report
from polymarket_alert_bot.config.settings import RuntimeConfig, RuntimePaths, ensure_runtime_dirs, load_runtime_config, load_runtime_paths
from polymarket_alert_bot.runtime_flow import execute_callback_flow, execute_monitor_flow, execute_scan_flow
from polymarket_alert_bot.service.auth import require_internal_bearer, require_telegram_webhook_secret
from polymarket_alert_bot.service.scheduler import RuntimeServiceScheduler, ScheduledJob
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.locks import file_lock
from polymarket_alert_bot.storage.migrations import apply_migrations


Runner = Callable[[], Any]
CallbackRunner = Callable[[dict[str, object]], Any]


def create_app(
    *,
    paths: RuntimePaths | None = None,
    runtime_config: RuntimeConfig | None = None,
    scheduler: RuntimeServiceScheduler | None = None,
    start_scheduler: bool | None = None,
    scan_runner: Runner | None = None,
    monitor_runner: Runner | None = None,
    report_runner: Runner | None = None,
    callback_runner: CallbackRunner | None = None,
) -> FastAPI:
    resolved_paths = paths or load_runtime_paths()
    ensure_runtime_dirs(resolved_paths)
    config = runtime_config or load_runtime_config()

    resolved_scan_runner = scan_runner or _build_scan_runner(resolved_paths, config)
    resolved_monitor_runner = monitor_runner or _build_monitor_runner(resolved_paths, config)
    resolved_report_runner = report_runner or _build_report_runner(resolved_paths)
    resolved_callback_runner = callback_runner or _build_callback_runner(resolved_paths, config)
    resolved_start_scheduler = config.service_enable_scheduler if start_scheduler is None else start_scheduler
    owns_scheduler = scheduler is None
    resolved_scheduler = scheduler or RuntimeServiceScheduler(
        [
            ScheduledJob("scan", config.scan_interval_seconds, resolved_scan_runner),
            ScheduledJob("monitor", config.monitor_interval_seconds, resolved_monitor_runner),
            ScheduledJob("report", config.report_interval_seconds, resolved_report_runner),
        ]
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if resolved_start_scheduler:
            resolved_scheduler.start()
        try:
            yield
        finally:
            if resolved_start_scheduler or owns_scheduler:
                resolved_scheduler.stop()

    app = FastAPI(title="Polymarket Alert Bot Runtime", lifespan=lifespan)
    app.state.paths = resolved_paths
    app.state.runtime_config = config
    app.state.scheduler = resolved_scheduler
    app.state.scheduler_enabled = resolved_start_scheduler
    app.state.scan_runner = resolved_scan_runner
    app.state.monitor_runner = resolved_monitor_runner
    app.state.report_runner = resolved_report_runner
    app.state.callback_runner = resolved_callback_runner

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {
            "status": "ok",
            "scheduler_enabled": resolved_start_scheduler,
        }

    @app.get("/status")
    def status_endpoint(request: Request) -> dict[str, object]:
        require_internal_bearer(request, request.app.state.runtime_config)
        return _build_status_payload(
            paths=request.app.state.paths,
            scheduler=request.app.state.scheduler,
            runtime_config=request.app.state.runtime_config,
            scheduler_enabled=request.app.state.scheduler_enabled,
        )

    @app.post("/internal/scan")
    def internal_scan(request: Request) -> dict[str, object]:
        require_internal_bearer(request, request.app.state.runtime_config)
        return _serialize_result(_run_internal(request.app.state.scan_runner))

    @app.post("/internal/monitor")
    def internal_monitor(request: Request) -> dict[str, object]:
        require_internal_bearer(request, request.app.state.runtime_config)
        return _serialize_result(_run_internal(request.app.state.monitor_runner))

    @app.post("/internal/report")
    def internal_report(request: Request) -> dict[str, object]:
        require_internal_bearer(request, request.app.state.runtime_config)
        run_id = _run_internal(request.app.state.report_runner)
        return {"run_id": run_id}

    @app.post("/telegram/webhook")
    async def telegram_webhook(request: Request) -> dict[str, object]:
        require_telegram_webhook_secret(request, request.app.state.runtime_config)
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="callback payload must be a JSON object",
            )
        try:
            result = await asyncio.to_thread(request.app.state.callback_runner, payload)
        except RuntimeError as exc:
            # Telegram delivers many update types to the same webhook URL.
            # Only callback_query updates drive runtime state changes; other
            # updates should be accepted and ignored to avoid Telegram retries.
            if str(exc) == "unsupported callback payload":
                return {"ignored": True}
            raise
        return _serialize_result(result)

    return app


def _build_scan_runner(paths: RuntimePaths, runtime_config: RuntimeConfig) -> Runner:
    def _runner():
        with file_lock(paths.scan_lock):
            return execute_scan_flow(paths, runtime_config=runtime_config)

    return _runner


def _build_monitor_runner(paths: RuntimePaths, runtime_config: RuntimeConfig) -> Runner:
    def _runner():
        with file_lock(paths.monitor_lock):
            return execute_monitor_flow(paths, runtime_config=runtime_config)

    return _runner


def _build_report_runner(paths: RuntimePaths) -> Runner:
    def _runner():
        with file_lock(paths.report_lock):
            return run_report(paths)

    return _runner


def _build_callback_runner(paths: RuntimePaths, runtime_config: RuntimeConfig) -> CallbackRunner:
    def _runner(payload: dict[str, object]):
        return execute_callback_flow(paths, payload=payload, runtime_config=runtime_config)

    return _runner


def _run_internal(runner: Runner) -> Any:
    try:
        return runner()
    except RuntimeError as exc:
        if "lock already held" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        raise


def _serialize_result(result: Any) -> dict[str, object]:
    if is_dataclass(result):
        return _normalize_json(asdict(result))
    if isinstance(result, dict):
        return _normalize_json(result)
    if isinstance(result, str):
        return {"result": result}
    raise TypeError(f"unsupported result type: {type(result)!r}")


def _normalize_json(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_normalize_json(item) for item in value]
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_json(item) for key, item in value.items()}
    return value


def _build_status_payload(
    *,
    paths: RuntimePaths,
    scheduler: RuntimeServiceScheduler,
    runtime_config: RuntimeConfig,
    scheduler_enabled: bool,
) -> dict[str, object]:
    conn = connect_db(paths.db_path)
    try:
        apply_migrations(conn)
        latest_runs = {}
        for run_type in ("scan", "monitor", "report"):
            row = conn.execute(
                """
                SELECT id, status, started_at, finished_at, degraded_reason, created_at
                FROM runs
                WHERE run_type = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [run_type],
            ).fetchone()
            latest_runs[run_type] = dict(row) if row else None

        counts = {
            "active_alerts": conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE status = 'active'"
            ).fetchone()[0],
            "open_clusters": conn.execute(
                "SELECT COUNT(*) FROM thesis_clusters WHERE status = 'open'"
            ).fetchone()[0],
            "active_triggers": conn.execute(
                "SELECT COUNT(*) FROM triggers WHERE state IN ('armed', 'rearmed', 'fired', 'snoozed', 'acknowledged')"
            ).fetchone()[0],
        }
    finally:
        conn.close()

    scheduler_snapshot = scheduler.snapshot()
    return {
        "service": {
            "host": runtime_config.service_host,
            "port": runtime_config.service_port,
            "scheduler_enabled": scheduler_enabled,
            "public_base_url": runtime_config.service_public_base_url,
        },
        "paths": {
            "data_dir": str(paths.data_dir),
            "db_path": str(paths.db_path),
        },
        "latest_runs": latest_runs,
        "counts": counts,
        "scheduler": scheduler_snapshot,
    }
