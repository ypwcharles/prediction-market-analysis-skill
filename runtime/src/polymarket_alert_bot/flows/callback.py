from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from uuid import uuid4

from polymarket_alert_bot.config.settings import RuntimeConfig, RuntimePaths, load_runtime_config
from polymarket_alert_bot.delivery.callback_router import CallbackRouter
from polymarket_alert_bot.delivery.telegram_client import TelegramClient
from polymarket_alert_bot.flows.shared import _now_iso
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations
from polymarket_alert_bot.storage.repositories import RuntimeRepository


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CallbackFlowSummary:
    alert_id: str
    thesis_cluster_id: str
    feedback_type: str


def execute_callback_flow(
    paths: RuntimePaths,
    *,
    payload: dict[str, object],
    runtime_config: RuntimeConfig | None = None,
) -> CallbackFlowSummary:
    event = CallbackRouter().route(payload)
    if event is None:
        raise RuntimeError("unsupported callback payload")

    timestamp = _now_iso()
    conn = connect_db(paths.db_path)
    apply_migrations(conn)
    repo = RuntimeRepository(conn)
    existing_feedback = repo.get_feedback_by_callback_query_id(event.callback_query_id)
    if existing_feedback is not None:
        return _feedback_summary(existing_feedback)
    alert_row = repo.get_alert(event.alert_id)
    if alert_row is None:
        raise RuntimeError(f"unknown alert_id in callback payload: {event.alert_id}")
    resolved_thesis_cluster_id = event.thesis_cluster_id or alert_row["thesis_cluster_id"]
    if not resolved_thesis_cluster_id:
        raise RuntimeError(f"unable to resolve thesis_cluster_id for alert_id: {event.alert_id}")

    try:
        repo.insert_feedback(
            {
                "id": str(uuid4()),
                "alert_id": event.alert_id,
                "thesis_cluster_id": resolved_thesis_cluster_id,
                "feedback_type": event.feedback_type,
                "callback_query_id": event.callback_query_id,
                "payload_json": json.dumps(event.payload, sort_keys=True),
                "telegram_chat_id": event.telegram_chat_id,
                "telegram_message_id": event.telegram_message_id,
                "created_at": timestamp,
            },
            commit=False,
        )
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        if "feedback.callback_query_id" not in str(exc):
            raise
        existing_feedback = repo.get_feedback_by_callback_query_id(event.callback_query_id)
        if existing_feedback is None:
            raise
        return _feedback_summary(existing_feedback)

    try:
        _apply_feedback_side_effects(
            conn,
            event=event,
            alert_row=alert_row,
            thesis_cluster_id=resolved_thesis_cluster_id,
            now_iso=timestamp,
            commit=False,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    config = runtime_config or load_runtime_config()
    if os.environ.get("TELEGRAM_BOT_TOKEN") and (config.telegram_chat_id or event.telegram_chat_id):
        with TelegramClient() as telegram:
            _deliver_callback_feedback_side_effects(telegram=telegram, event=event)

    return CallbackFlowSummary(
        alert_id=event.alert_id,
        thesis_cluster_id=resolved_thesis_cluster_id,
        feedback_type=event.feedback_type,
    )


def _feedback_summary(feedback_row) -> CallbackFlowSummary:
    return CallbackFlowSummary(
        alert_id=str(feedback_row["alert_id"]),
        thesis_cluster_id=str(feedback_row["thesis_cluster_id"]),
        feedback_type=str(feedback_row["feedback_type"]),
    )


def _apply_feedback_side_effects(
    conn, *, event, alert_row, thesis_cluster_id: str, now_iso: str, commit: bool = True
) -> None:
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
    if commit:
        conn.commit()


def _confirm_callback_feedback(*, telegram: TelegramClient, event) -> None:
    if not event.telegram_chat_id:
        return

    status_line = _callback_status_line(event.action_label)
    keyboard_cleared = False
    if event.telegram_message_id:
        keyboard_cleared = telegram.clear_message_keyboard(
            chat_id=event.telegram_chat_id,
            message_id=event.telegram_message_id,
        )
        if event.message_text:
            updated_text = _append_callback_status_line(event.message_text, status_line)
            edited = telegram.edit_message(
                chat_id=event.telegram_chat_id,
                message_id=event.telegram_message_id,
                text=updated_text,
            )
            if edited:
                return
    if keyboard_cleared:
        return
    telegram.send_message(
        chat_id=event.telegram_chat_id,
        text=f"{status_line}\n已记录到 runtime。",
    )


def _deliver_callback_feedback_side_effects(*, telegram: TelegramClient, event) -> None:
    try:
        telegram.answer_callback_query(
            callback_query_id=event.callback_query_id,
            text=event.callback_answer,
        )
    except Exception as exc:
        logger.warning(
            "callback query acknowledgement failed for alert %s (callback_query_id=%s): %s",
            event.alert_id,
            event.callback_query_id,
            exc,
        )

    try:
        _confirm_callback_feedback(telegram=telegram, event=event)
    except Exception as exc:
        logger.warning(
            "callback feedback confirmation failed for alert %s (callback_query_id=%s): %s",
            event.alert_id,
            event.callback_query_id,
            exc,
        )


def _callback_status_line(action_label: str) -> str:
    return f"反馈状态：{action_label}"


def _append_callback_status_line(message_text: str, status_line: str) -> str:
    normalized = message_text.rstrip()
    if status_line in normalized:
        return normalized
    return f"{normalized}\n\n{status_line}"
