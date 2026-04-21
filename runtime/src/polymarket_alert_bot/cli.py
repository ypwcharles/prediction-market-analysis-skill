import argparse
import json
import sys
from pathlib import Path

from polymarket_alert_bot.archive.promote import promote_archive_artifact
from polymarket_alert_bot.calibration.report_writer import run_report
from polymarket_alert_bot.config.settings import (
    ensure_runtime_dirs,
    load_runtime_config,
    load_runtime_paths,
)
from polymarket_alert_bot.flows import (
    execute_callback_flow,
    execute_monitor_flow,
    execute_scan_flow,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="polymarket-alert-bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("scan")
    subparsers.add_parser("monitor")
    subparsers.add_parser("report")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host")
    serve_parser.add_argument("--port", type=int)
    serve_parser.add_argument("--reload", action="store_true")
    serve_parser.add_argument("--no-scheduler", action="store_true")

    callback_parser = subparsers.add_parser("callback")
    callback_parser.add_argument("--payload-file", required=True)

    promote_parser = subparsers.add_parser("promote")
    promote_parser.add_argument("archive_path")
    promote_parser.add_argument(
        "--destination-dir",
        default=str(Path("docs") / "market-analysis"),
    )

    args = parser.parse_args(argv)
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)
    config = load_runtime_config()

    if args.command == "scan":
        execute_scan_flow(paths, runtime_config=config)
        return 0
    if args.command == "monitor":
        execute_monitor_flow(paths, runtime_config=config)
        return 0
    if args.command == "report":
        run_report(paths)
        return 0
    if args.command == "serve":
        _serve(
            paths,
            runtime_config=config,
            host=args.host,
            port=args.port,
            reload=args.reload,
            enable_scheduler=not args.no_scheduler,
        )
        return 0
    if args.command == "callback":
        execute_callback_flow(
            paths,
            payload=_load_callback_payload(Path(args.payload_file)),
            runtime_config=config,
        )
        return 0
    if args.command == "promote":
        promote_archive_artifact(args.archive_path, args.destination_dir)
        return 0

    raise SystemExit(f"unknown command: {args.command}")


def _serve(
    paths,
    *,
    runtime_config,
    host: str | None,
    port: int | None,
    reload: bool,
    enable_scheduler: bool,
) -> None:
    import uvicorn

    from polymarket_alert_bot.service.app import create_app

    app = create_app(
        paths=paths,
        runtime_config=runtime_config,
        start_scheduler=enable_scheduler,
    )
    uvicorn.run(
        app,
        host=host or runtime_config.service_host,
        port=port or runtime_config.service_port,
        reload=reload,
    )


def _load_callback_payload(payload_path: Path) -> dict[str, object]:
    if str(payload_path) == "-":
        raw = sys.stdin.read()
    else:
        raw = payload_path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise RuntimeError("callback payload must be a JSON object")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
