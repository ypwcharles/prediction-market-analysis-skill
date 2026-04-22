from __future__ import annotations

import json

import pytest

from polymarket_alert_bot.cli import main
from polymarket_alert_bot.delivery.callback_router import FeedbackEvent
from polymarket_alert_bot.delivery.telegram_client import TelegramMessageRef
from polymarket_alert_bot.flows import callback as callback_flow
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations


def test_callback_command_persists_feedback_and_claim(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))

    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    apply_migrations(conn)
    conn.execute(
        """
        INSERT INTO thesis_clusters (
            id, canonical_name, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        [
            "cluster-1",
            "Sample thesis",
            "open",
            "2026-04-17T00:00:00+00:00",
            "2026-04-17T00:00:00+00:00",
        ],
    )
    conn.execute(
        """
        INSERT INTO runs (
            id, run_type, status, started_at, finished_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            "run-1",
            "scan",
            "clean",
            "2026-04-17T00:00:00+00:00",
            "2026-04-17T00:00:00+00:00",
            "2026-04-17T00:00:00+00:00",
        ],
    )
    conn.execute(
        """
        INSERT INTO alerts (
            id, run_id, thesis_cluster_id, condition_id, market_id, token_id,
            alert_kind, delivery_mode, status, dedupe_key, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "alert-1",
            "run-1",
            "cluster-1",
            "cond-1",
            "market-1",
            "token-1",
            "strict",
            "immediate",
            "active",
            "dedupe-1",
            "2026-04-17T00:00:00+00:00",
        ],
    )
    conn.commit()

    payload_path = tmp_path / "callback.json"
    payload_path.write_text(
        json.dumps(
            {
                "callback_query": {
                    "id": "cb-1",
                    "data": "fb:ordered:alert-1:cluster-1",
                    "from": {"id": 12345},
                    "message": {
                        "message_id": 55,
                        "chat": {"id": -100123456},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    assert main(["callback", "--payload-file", str(payload_path)]) == 0

    feedback_row = conn.execute(
        "SELECT feedback_type, telegram_chat_id, telegram_message_id FROM feedback"
    ).fetchone()
    assert dict(feedback_row) == {
        "feedback_type": "claimed_buy",
        "telegram_chat_id": "-100123456",
        "telegram_message_id": "55",
    }

    claim_row = conn.execute(
        """
        SELECT condition_id, token_id, truth_source, status
        FROM positions
        WHERE truth_source = 'telegram_claim'
        """
    ).fetchone()
    assert dict(claim_row) == {
        "condition_id": "cond-1",
        "token_id": "token-1",
        "truth_source": "telegram_claim",
        "status": "claimed_only",
    }


def test_callback_command_persists_feedback_even_if_telegram_side_effects_fail(
    tmp_path, monkeypatch
):
    data_dir = tmp_path / ".runtime-data"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    apply_migrations(conn)
    _seed_alert_context(
        conn, alert_id="alert-sidefx", run_id="run-sidefx", cluster_id="cluster-sidefx"
    )
    conn.commit()

    calls: list[tuple[str, dict[str, object]]] = []

    class FlakyTelegramClient:
        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def answer_callback_query(self, **kwargs):
            calls.append(("answer_callback_query", kwargs))
            raise RuntimeError("telegram callback ack timeout")

        def clear_message_keyboard(self, **kwargs):
            calls.append(("clear_message_keyboard", kwargs))
            return True

        def edit_message(self, **kwargs):
            calls.append(("edit_message", kwargs))
            return True

        def send_message(self, **kwargs):
            calls.append(("send_message", kwargs))
            return TelegramMessageRef(chat_id=str(kwargs["chat_id"]), message_id="fallback-sidefx")

    monkeypatch.setattr(callback_flow, "TelegramClient", FlakyTelegramClient)

    payload_path = tmp_path / "callback-sidefx.json"
    payload_path.write_text(
        json.dumps(
            {
                "callback_query": {
                    "id": "cb-sidefx",
                    "data": "fb:ack:alert-sidefx:cluster-sidefx",
                    "from": {"id": 12345},
                    "message": {
                        "message_id": 60,
                        "chat": {"id": -100123456},
                        "text": "STRICT memo body",
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    assert main(["callback", "--payload-file", str(payload_path)]) == 0

    feedback_row = conn.execute(
        "SELECT callback_query_id, feedback_type, telegram_message_id FROM feedback WHERE callback_query_id = 'cb-sidefx'"
    ).fetchone()
    assert dict(feedback_row) == {
        "callback_query_id": "cb-sidefx",
        "feedback_type": "seen",
        "telegram_message_id": "60",
    }
    assert [name for name, _ in calls] == [
        "answer_callback_query",
        "clear_message_keyboard",
        "edit_message",
    ]


def test_callback_fallback_confirmation_preserves_message_thread_id() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeTelegramClient:
        def clear_message_keyboard(self, **kwargs):
            calls.append(("clear_message_keyboard", kwargs))
            return False

        def send_message(self, **kwargs):
            calls.append(("send_message", kwargs))
            return TelegramMessageRef(chat_id=str(kwargs["chat_id"]), message_id="fallback-thread")

    event = FeedbackEvent(
        feedback_type="seen",
        action="ack",
        action_label="已看",
        update_id="upd-1",
        callback_query_id="cb-thread",
        callback_data="fb:ack:alert-thread:cluster-thread",
        alert_id="alert-thread",
        thesis_cluster_id="cluster-thread",
        telegram_chat_id="-100123456",
        telegram_message_id="58",
        inline_message_id=None,
        message_thread_id="8369",
        message_text=None,
        payload={},
        callback_answer="收到，已标记为已看。",
    )

    callback_flow._confirm_callback_feedback(telegram=FakeTelegramClient(), event=event)

    assert calls == [
        ("clear_message_keyboard", {"chat_id": "-100123456", "message_id": "58"}),
        (
            "send_message",
            {
                "chat_id": "-100123456",
                "text": "反馈状态：已看\n已记录到 runtime。",
                "message_thread_id": "8369",
            },
        ),
    ]


def test_promote_command_copies_archive_artifact(tmp_path):
    archive_path = tmp_path / "strict-alert-1.md"
    archive_path.write_text("# strict memo\n", encoding="utf-8")
    destination_dir = tmp_path / "promoted"

    assert (
        main(
            [
                "promote",
                str(archive_path),
                "--destination-dir",
                str(destination_dir),
            ]
        )
        == 0
    )

    promoted_path = destination_dir / archive_path.name
    assert promoted_path.exists()
    assert promoted_path.read_text(encoding="utf-8") == "# strict memo\n"


def test_callback_seen_acknowledges_fired_trigger(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    apply_migrations(conn)
    _seed_alert_context(conn, alert_id="alert-ack", run_id="run-ack", cluster_id="cluster-ack")
    conn.execute(
        """
        INSERT INTO triggers (
            id, thesis_cluster_id, alert_id, trigger_type, threshold_kind,
            comparison, threshold_value, suggested_action, state, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "trigger-ack",
            "cluster-ack",
            "alert-ack",
            "price_reprice",
            "price",
            "<=",
            "40",
            "buy",
            "fired",
            "2026-04-17T00:00:00+00:00",
            "2026-04-17T00:00:00+00:00",
        ],
    )
    conn.commit()

    payload_path = tmp_path / "ack.json"
    payload_path.write_text(
        json.dumps(
            {
                "callback_query": {
                    "id": "cb-ack",
                    "data": "fb:ack:alert-ack:cluster-ack",
                    "message": {"message_id": 56, "chat": {"id": -100123456}},
                }
            }
        ),
        encoding="utf-8",
    )

    assert main(["callback", "--payload-file", str(payload_path)]) == 0

    trigger_row = conn.execute("SELECT state FROM triggers WHERE id = 'trigger-ack'").fetchone()
    assert trigger_row["state"] == "acknowledged"


def test_callback_seen_edits_message_for_visible_confirmation(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    apply_migrations(conn)
    _seed_alert_context(
        conn, alert_id="alert-visible", run_id="run-visible", cluster_id="cluster-visible"
    )
    conn.commit()

    calls: list[tuple[str, dict[str, object]]] = []

    class FakeTelegramClient:
        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def answer_callback_query(self, **kwargs):
            calls.append(("answer_callback_query", kwargs))
            return True

        def clear_message_keyboard(self, **kwargs):
            calls.append(("clear_message_keyboard", kwargs))
            return True

        def edit_message(self, **kwargs):
            calls.append(("edit_message", kwargs))
            return True

        def send_message(self, **kwargs):
            calls.append(("send_message", kwargs))
            return TelegramMessageRef(chat_id=str(kwargs["chat_id"]), message_id="fallback-1")

    monkeypatch.setattr(callback_flow, "TelegramClient", FakeTelegramClient)

    payload_path = tmp_path / "ack-visible.json"
    payload_path.write_text(
        json.dumps(
            {
                "callback_query": {
                    "id": "cb-visible",
                    "data": "fb:ack:alert-visible:cluster-visible",
                    "message": {
                        "message_id": 58,
                        "chat": {"id": -100123456},
                        "text": "STRICT memo body",
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    assert main(["callback", "--payload-file", str(payload_path)]) == 0

    assert calls == [
        (
            "answer_callback_query",
            {
                "callback_query_id": "cb-visible",
                "text": "收到，已标记为已看。",
            },
        ),
        (
            "clear_message_keyboard",
            {
                "chat_id": "-100123456",
                "message_id": "58",
            },
        ),
        (
            "edit_message",
            {
                "chat_id": "-100123456",
                "message_id": "58",
                "text": "STRICT memo body\n\n反馈状态：已看",
            },
        ),
    ]


def test_callback_replay_is_idempotent(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))

    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    apply_migrations(conn)
    _seed_alert_context(
        conn, alert_id="alert-replay", run_id="run-replay", cluster_id="cluster-replay"
    )
    conn.commit()

    payload_path = tmp_path / "callback-replay.json"
    payload_path.write_text(
        json.dumps(
            {
                "callback_query": {
                    "id": "cb-replay",
                    "data": "fb:ordered:alert-replay:cluster-replay",
                    "from": {"id": 12345},
                    "message": {
                        "message_id": 59,
                        "chat": {"id": -100123456},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    assert main(["callback", "--payload-file", str(payload_path)]) == 0
    assert main(["callback", "--payload-file", str(payload_path)]) == 0

    feedback_rows = conn.execute(
        """
        SELECT callback_query_id, feedback_type, telegram_message_id
        FROM feedback
        ORDER BY created_at, id
        """
    ).fetchall()
    assert [dict(row) for row in feedback_rows] == [
        {
            "callback_query_id": "cb-replay",
            "feedback_type": "claimed_buy",
            "telegram_message_id": "59",
        }
    ]

    claim_rows = conn.execute(
        """
        SELECT COUNT(*)
        FROM positions
        WHERE truth_source = 'telegram_claim'
        """
    ).fetchone()[0]
    assert claim_rows == 1


def test_callback_replay_retries_when_previous_attempt_failed_before_side_effects(
    tmp_path, monkeypatch
):
    data_dir = tmp_path / ".runtime-data"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))

    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    apply_migrations(conn)
    _seed_alert_context(
        conn, alert_id="alert-retry", run_id="run-retry", cluster_id="cluster-retry"
    )
    conn.commit()

    original_apply = callback_flow._apply_feedback_side_effects
    attempts = {"count": 0}

    def _flaky_apply(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("crash-after-feedback-insert")
        return original_apply(*args, **kwargs)

    monkeypatch.setattr(callback_flow, "_apply_feedback_side_effects", _flaky_apply)

    payload_path = tmp_path / "callback-retry.json"
    payload_path.write_text(
        json.dumps(
            {
                "callback_query": {
                    "id": "cb-retry",
                    "data": "fb:close:alert-retry:cluster-retry",
                    "message": {"message_id": 60, "chat": {"id": -100123456}},
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="crash-after-feedback-insert"):
        main(["callback", "--payload-file", str(payload_path)])

    feedback_count = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    cluster_status = conn.execute(
        "SELECT status FROM thesis_clusters WHERE id = 'cluster-retry'"
    ).fetchone()["status"]
    assert feedback_count == 0
    assert cluster_status == "open"

    assert main(["callback", "--payload-file", str(payload_path)]) == 0

    feedback_rows = conn.execute("SELECT callback_query_id, feedback_type FROM feedback").fetchall()
    assert [dict(row) for row in feedback_rows] == [
        {
            "callback_query_id": "cb-retry",
            "feedback_type": "close_thesis",
        }
    ]
    cluster_status = conn.execute(
        "SELECT status FROM thesis_clusters WHERE id = 'cluster-retry'"
    ).fetchone()["status"]
    assert cluster_status == "closed"


def test_callback_close_thesis_closes_cluster_and_triggers(tmp_path, monkeypatch):
    data_dir = tmp_path / ".runtime-data"
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_DATA_DIR", str(data_dir))
    conn = connect_db(data_dir / "sqlite" / "runtime.sqlite3")
    apply_migrations(conn)
    _seed_alert_context(
        conn, alert_id="alert-close", run_id="run-close", cluster_id="cluster-close"
    )
    conn.execute(
        """
        INSERT INTO triggers (
            id, thesis_cluster_id, alert_id, trigger_type, threshold_kind,
            comparison, threshold_value, suggested_action, state, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "trigger-close",
            "cluster-close",
            "alert-close",
            "price_reprice",
            "price",
            "<=",
            "40",
            "reduce",
            "fired",
            "2026-04-17T00:00:00+00:00",
            "2026-04-17T00:00:00+00:00",
        ],
    )
    conn.commit()

    payload_path = tmp_path / "close.json"
    payload_path.write_text(
        json.dumps(
            {
                "callback_query": {
                    "id": "cb-close",
                    "data": "fb:close:alert-close:cluster-close",
                    "message": {"message_id": 57, "chat": {"id": -100123456}},
                }
            }
        ),
        encoding="utf-8",
    )

    assert main(["callback", "--payload-file", str(payload_path)]) == 0

    cluster_row = conn.execute(
        "SELECT status, closed_reason FROM thesis_clusters WHERE id = 'cluster-close'"
    ).fetchone()
    trigger_row = conn.execute("SELECT state FROM triggers WHERE id = 'trigger-close'").fetchone()
    assert dict(cluster_row) == {
        "status": "closed",
        "closed_reason": "telegram_close_thesis",
    }
    assert trigger_row["state"] == "closed"


def _seed_alert_context(conn, *, alert_id: str, run_id: str, cluster_id: str) -> None:
    conn.execute(
        """
        INSERT INTO thesis_clusters (
            id, canonical_name, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        [
            cluster_id,
            "Sample thesis",
            "open",
            "2026-04-17T00:00:00+00:00",
            "2026-04-17T00:00:00+00:00",
        ],
    )
    conn.execute(
        """
        INSERT INTO runs (
            id, run_type, status, started_at, finished_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            "scan",
            "clean",
            "2026-04-17T00:00:00+00:00",
            "2026-04-17T00:00:00+00:00",
            "2026-04-17T00:00:00+00:00",
        ],
    )
    conn.execute(
        """
        INSERT INTO alerts (
            id, run_id, thesis_cluster_id, condition_id, market_id, token_id,
            alert_kind, delivery_mode, status, dedupe_key, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            alert_id,
            run_id,
            cluster_id,
            "cond-1",
            "market-1",
            "token-1",
            "strict",
            "immediate",
            "active",
            f"dedupe-{alert_id}",
            "2026-04-17T00:00:00+00:00",
        ],
    )
    conn.commit()
