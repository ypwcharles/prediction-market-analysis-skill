import argparse

from polymarket_alert_bot.calibration.report_writer import run_report
from polymarket_alert_bot.config.settings import ensure_runtime_dirs, load_runtime_paths
from polymarket_alert_bot.monitor.position_sync import run_monitor
from polymarket_alert_bot.scanner.board_scan import run_scan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="polymarket-alert-bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("scan")
    subparsers.add_parser("monitor")
    subparsers.add_parser("report")
    args = parser.parse_args(argv)
    paths = load_runtime_paths()
    ensure_runtime_dirs(paths)

    if args.command == "scan":
        run_scan(paths)
        return 0
    if args.command == "monitor":
        run_monitor(paths)
        return 0
    if args.command == "report":
        run_report(paths)
        return 0

    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
