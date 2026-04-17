import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

from polymarket_alert_bot.archive.promote import promote_archive_artifact
from polymarket_alert_bot.calibration.report_writer import run_report
from polymarket_alert_bot.config.settings import ensure_runtime_dirs, load_runtime_config, load_runtime_paths
from polymarket_alert_bot.delivery.callback_router import CallbackRouter
from polymarket_alert_bot.delivery.telegram_client import TelegramClient
from polymarket_alert_bot.runtime_flow import execute_monitor_flow, execute_scan_flow
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations
from polymarket_alert_bot.storage.repositories import RuntimeRepository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="polymarket-alert-bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("scan")
    subparsers.add_parser("monitor")
    subparsers.add_parser("report")
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

    if args.command == "scan":
        execute_scan_flow(paths, runtime_config=load_runtime_config())
        return 0
    if args.command == "monitor":
        execute_monitor_flow(paths, runtime_config=load_runtime_config())
        return 0
    if args.command == "report":
        run_report(paths)
        return 0
    if args.command == "callback":
        _handle_callback(paths, Path(args.payload_file))
        return 0
    if args.command == "promote":
        promote_archive_artifact(args.archive_path, args.destination_dir)
        return 0

    raise SystemExit(f"unknown command: {args.command}")


def _handle_callback(paths, payload_path: Path) -> None:
    payload = _load_callback_payload(payload_path)
    event = CallbackRouter().route(payload)
    if event is None:
        raise RuntimeError(f"unsupported callback payload: {payload_path}")

    timestamp = datetime.now(UTC).isoformat()
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    repo = RuntimeRepository(conn)
    alert_row = repo.get_alert(event.alert_id)
    if alert_row is None:
        raise RuntimeError(f"unknown alert_id in callback payload: {event.alert_id}")
    resolved_thesis_cluster_id = event.thesis_cluster_id or alert_row["thesis_cluster_id"]
    if not resolved_thesis_cluster_id:
        raise RuntimeError(f"unable to resolve thesis_cluster_id for alert_id: {event.alert_id}")

    repo.insert_feedback(
        {
            "id": str(uuid4()),
            "alert_id": event.alert_id,
            "thesis_cluster_id": resolved_thesis_cluster_id,
            "feedback_type": event.feedback_type,
            "payload_json": json.dumps(event.payload, sort_keys=True),
            "telegram_chat_id": event.telegram_chat_id,
            "telegram_message_id": event.telegram_message_id,
            "created_at": timestamp,
        }
    )

    _apply_feedback_side_effects(
        conn,
        event=event,
        alert_row=alert_row,
        thesis_cluster_id=resolved_thesis_cluster_id,
        now_iso=timestamp,
    )

    config = load_runtime_config()
    if os.environ.get("TELEGRAM_BOT_TOKEN") and (config.telegram_chat_id or event.telegram_chat_id):
        with TelegramClient() as telegram:
            telegram.answer_callback_query(
                callback_query_id=event.callback_query_id,
                text=event.callback_answer,
            )


def _apply_feedback_side_effects(conn, *, event, alert_row, thesis_cluster_id: str, now_iso: str) -> None:
    if event.feedback_type == "claimed_buy":
        existing = conn.execute(
            """
            SELECT id
            FROM positions
            WHERE condition_id = ?
              AND token_id = ?
              AND truth_source = 'telegram_claim'
            """,
            [alert_row["condition_id"], alert_row["token_id"]],
        ).fetchone()
        if existing is None and alert_row["condition_id"] and alert_row["token_id"]:
            conn.execute(
                """
                INSERT INTO positions (
                    id,
                    condition_id,
                    token_id,
                    market_id,
                    thesis_cluster_id,
                    side,
                    size_shares,
                    avg_entry_cents,
                    status,
                    truth_source,
                    snapshot_as_of,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    f"claim-{uuid4()}",
                    alert_row["condition_id"],
                    alert_row["token_id"],
                    alert_row["market_id"],
                    alert_row["thesis_cluster_id"],
                    alert_row["side"] or "YES",
                    0.0,
                    alert_row["max_entry_cents"],
                    "claimed_only",
                    "telegram_claim",
                    now_iso,
                    now_iso,
                ],
            )
    if event.feedback_type == "close_thesis":
        conn.execute(
            """
            UPDATE thesis_clusters
            SET status = 'closed',
                closed_reason = 'telegram_close_thesis',
                closed_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            [now_iso, now_iso, thesis_cluster_id],
        )
        conn.execute(
            """
            UPDATE triggers
            SET state = 'closed',
                updated_at = ?
            WHERE thesis_cluster_id = ?
            """,
            [now_iso, thesis_cluster_id],
        )
    if event.feedback_type == "seen":
        conn.execute(
            """
            UPDATE triggers
            SET state = 'acknowledged',
                updated_at = ?
            WHERE alert_id = ?
              AND state = 'fired'
            """,
            [now_iso, event.alert_id],
        )
    if event.feedback_type == "snooze":
        conn.execute(
            """
            UPDATE triggers
            SET state = 'snoozed',
                cooldown_until = datetime(?, '+60 minutes'),
                updated_at = ?
            WHERE alert_id = ?
              AND state = 'fired'
            """,
            [now_iso, now_iso, event.alert_id],
        )
    conn.commit()


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
