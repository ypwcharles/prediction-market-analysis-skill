from __future__ import annotations

from pathlib import Path

import pytest

from polymarket_alert_bot.delivery.callback_router import (
    CallbackRouter,
    build_feedback_keyboard,
    make_callback_data,
)
from polymarket_alert_bot.delivery.telegram_client import TelegramClient, TelegramMessageRef
from polymarket_alert_bot.templates.heartbeat import render_heartbeat
from polymarket_alert_bot.templates.monitor_alert import render_monitor_alert
from polymarket_alert_bot.templates.research_digest import render_research_digest
from polymarket_alert_bot.templates.strict_memo import render_strict_memo

SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "snapshots"


def _assert_snapshot(name: str, content: str) -> None:
    snapshot = SNAPSHOT_DIR / name
    expected = snapshot.read_text(encoding="utf-8").rstrip("\n")
    assert content == expected


def test_render_strict_memo_snapshot() -> None:
    payload = {
        "mode": "STRICT-DEGRADED",
        "thesis": "US-Iran headline premium is overstated for this bucket.",
        "thesis_cluster_id": "cluster-iran-001",
        "expression": "US military action against Iran by Apr 30",
        "side": "NO",
        "max_entry_cents": 42.0,
        "suggested_size_usdc": 250.0,
        "executable_edge_cents": 13.4,
        "why_now": "Orderbook skew widened after single-source reposts, while tiered evidence has not confirmed escalation.",
        "kill_criteria_text": "Exit if primary sources confirm direct US strike authorization or if YES re-prices below edge floor.",
        "evidence_fresh_until": "2026-04-17T14:30:00Z",
        "recheck_required_at": "2026-04-17T12:00:00Z",
        "citations": [
            {
                "claim": "Defense officials said no strike order has been issued.",
                "source": {
                    "name": "Reuters",
                    "tier": "primary",
                    "url": "https://example.com/reuters-iran-1",
                    "fetched_at": "2026-04-17T09:45:00Z",
                },
            },
            {
                "claim": "Local outlet reported troop movement rumors without official confirmation.",
                "source": {
                    "name": "RegionalDesk",
                    "tier": "secondary",
                    "url": "https://example.com/regionaldesk-42",
                    "fetched_at": "2026-04-17T09:10:00Z",
                },
            },
        ],
    }
    _assert_snapshot("strict_memo.txt", render_strict_memo(payload))


def test_render_research_digest_snapshot() -> None:
    payload = {
        "thesis": "Potential reprice if shipping-flow narrative weakens.",
        "summary": "Related conflict buckets moved together despite different settlement verbs.",
        "watch_item": "Watch for any wording shift from ceasefire to conflict-ends contracts.",
        "citations": [
            {
                "claim": "Exchange activity concentrated in short-dated buckets overnight.",
                "source": {"name": "Gamma board export"},
            },
            {
                "claim": "No official policy statement supports the most aggressive timeline.",
                "source": {"name": "Primary-wire sweep"},
            },
        ],
    }
    _assert_snapshot("research_digest.txt", render_research_digest(payload))


def test_render_monitor_alert_snapshot() -> None:
    payload = {
        "thesis": "NO position relies on rumor premium mean reversion.",
        "trigger_type": "price_reprice",
        "trigger_state": "fired",
        "observation": "YES ask touched 55c; threshold was 52c.",
        "suggested_action": "Re-check edge and tighten max entry before adding size.",
    }
    _assert_snapshot("monitor_alert.txt", render_monitor_alert(payload))


def test_render_strict_memo_includes_market_link_when_present() -> None:
    rendered = render_strict_memo(
        {
            "mode": "STRICT",
            "thesis": "test thesis",
            "thesis_cluster_id": "cluster-test",
            "expression": "test expression",
            "market_link": "https://polymarket.com/event/test-event/test-market",
        }
    )
    assert "market: https://polymarket.com/event/test-event/test-market" in rendered


def test_render_research_digest_includes_market_link_when_present() -> None:
    rendered = render_research_digest(
        {
            "thesis": "test thesis",
            "summary": "test summary",
            "watch_item": "test watch",
            "market_link": "https://polymarket.com/event/test-event",
        }
    )
    assert "market: https://polymarket.com/event/test-event" in rendered


def test_render_monitor_alert_includes_market_link_when_present() -> None:
    rendered = render_monitor_alert(
        {
            "thesis": "test thesis",
            "trigger_type": "price_reprice",
            "trigger_state": "fired",
            "observation": "test observation",
            "suggested_action": "test action",
            "market_link": "https://polymarket.com/event/test-event/test-market",
        }
    )
    assert "market: https://polymarket.com/event/test-event/test-market" in rendered


def test_render_heartbeat_snapshot() -> None:
    payload = {
        "degraded": True,
        "scan_run_id": "run-scan-001",
        "monitor_run_id": "run-monitor-001",
        "scanned_events": 12,
        "scanned_contracts": 48,
        "shortlisted_candidates": 6,
        "retrieved_shortlist_candidates": 3,
        "promoted_seed_count": 5,
        "strict_count": 2,
        "research_count": 4,
        "skipped_count": 19,
        "degraded_reason": "news source timeout, monitor still healthy",
    }
    _assert_snapshot("heartbeat.txt", render_heartbeat(payload))


def test_feedback_keyboard_and_callback_router_mapping() -> None:
    keyboard = build_feedback_keyboard(alert_id="alert-101", thesis_cluster_id="cluster-iran-001")
    expected_labels = [
        "已看",
        "稍后提醒",
        "已下单",
        "不认同",
        "关闭 thesis",
    ]
    labels = [button["text"] for row in keyboard["inline_keyboard"] for button in row]
    assert labels == expected_labels

    update = {
        "callback_query": {
            "id": "cbq-9001",
            "data": keyboard["inline_keyboard"][1][1]["callback_data"],
            "from": {"id": 7788},
            "message": {"message_id": 55, "chat": {"id": -100123456}},
        }
    }
    event = CallbackRouter().route(update)
    assert event is not None
    assert event.action == "close"
    assert event.feedback_type == "close_thesis"
    assert event.action_label == "关闭 thesis"
    assert event.alert_id == "alert-101"
    assert event.thesis_cluster_id == "cluster-iran-001"
    assert event.telegram_chat_id == "-100123456"
    assert event.telegram_message_id == "55"


def test_callback_router_extracts_update_and_message_refs_for_persistence() -> None:
    callback_data = build_feedback_keyboard(
        alert_id="alert-801",
        thesis_cluster_id="cluster-gaza-001",
    )["inline_keyboard"][0][0]["callback_data"]
    update = {
        "update_id": 99001,
        "callback_query": {
            "id": "cbq-inline-101",
            "data": callback_data,
            "inline_message_id": "AgAAABBBCCC",
            "from": {"id": 12345},
            "message": {
                "message_id": 777,
                "message_thread_id": 88,
                "chat": {"id": -100333444, "type": "supergroup"},
                "text": "STRICT alert body",
            },
        },
    }

    event = CallbackRouter().route(update)

    assert event is not None
    assert event.update_id == "99001"
    assert event.message_text == "STRICT alert body"
    assert event.payload["message_ref"] == {
        "chat_id": "-100333444",
        "message_id": "777",
        "message_thread_id": "88",
        "inline_message_id": "AgAAABBBCCC",
    }
    assert event.payload["message_text"] == "STRICT alert body"
    assert event.payload["callback_answer"] == event.callback_answer


def test_make_callback_data_falls_back_to_short_payload_when_cluster_is_too_long() -> None:
    long_cluster_id = "cluster-" + ("x" * 64)
    callback_data = make_callback_data(
        action="ack",
        alert_id="alert-1",
        thesis_cluster_id=long_cluster_id,
    )
    assert callback_data == "fb:ack:alert-1"


def test_callback_router_trims_callback_data_segments() -> None:
    update = {
        "callback_query": {
            "id": "cbq-trim-1",
            "data": "  fb:ack:alert-321: cluster-abc  ",
            "message": {"message_id": 7, "chat": {"id": -100777}},
        }
    }
    event = CallbackRouter().route(update)
    assert event is not None
    assert event.alert_id == "alert-321"
    assert event.thesis_cluster_id == "cluster-abc"


def test_callback_router_accepts_short_payload_without_cluster_id() -> None:
    update = {
        "callback_query": {
            "id": "cbq-short-1",
            "data": "fb:ack:alert-321",
            "message": {"message_id": 7, "chat": {"id": -100777}},
        }
    }
    event = CallbackRouter().route(update)
    assert event is not None
    assert event.alert_id == "alert-321"
    assert event.thesis_cluster_id is None


def test_telegram_client_send_message_parses_enveloped_result() -> None:
    def request_fn(method: str, payload: dict[str, object]) -> dict[str, object]:
        assert method == "sendMessage"
        assert payload["chat_id"] == "-100123"
        return {
            "ok": True,
            "result": {"chat": {"id": -100123}, "message_id": 91},
        }

    ref = TelegramClient(request_fn=request_fn).send_message(
        chat_id="-100123",
        text="hello",
    )
    assert ref == TelegramMessageRef(chat_id="-100123", message_id="91")


def test_telegram_client_send_message_includes_thread_id_when_provided() -> None:
    def request_fn(method: str, payload: dict[str, object]) -> dict[str, object]:
        assert method == "sendMessage"
        assert payload["chat_id"] == "-100123"
        assert payload["message_thread_id"] == "8369"
        return {
            "ok": True,
            "result": {"chat": {"id": -100123}, "message_id": 92},
        }

    ref = TelegramClient(request_fn=request_fn).send_message(
        chat_id="-100123",
        text="hello topic",
        message_thread_id="8369",
    )
    assert ref == TelegramMessageRef(chat_id="-100123", message_id="92")


def test_telegram_client_upsert_falls_back_to_send_when_edit_target_missing() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def request_fn(method: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append((method, payload))
        if method == "editMessageText":
            return {
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: message to edit not found",
            }
        if method == "sendMessage":
            return {
                "ok": True,
                "result": {"chat": {"id": -100123}, "message_id": 120},
            }
        raise AssertionError(f"unexpected method: {method}")

    client = TelegramClient(request_fn=request_fn)
    updated_ref = client.upsert_message(
        chat_id="-100123",
        text="fresh text",
        message_ref=TelegramMessageRef(chat_id="-100123", message_id="55"),
    )
    assert [name for name, _ in calls] == ["editMessageText", "sendMessage"]
    assert updated_ref == TelegramMessageRef(chat_id="-100123", message_id="120")


def test_telegram_client_edit_message_treats_not_modified_as_success() -> None:
    def request_fn(method: str, _payload: dict[str, object]) -> dict[str, object]:
        assert method == "editMessageText"
        return {
            "ok": False,
            "error_code": 400,
            "description": "Bad Request: message is not modified",
        }

    edited = TelegramClient(request_fn=request_fn).edit_message(
        chat_id="-100123",
        message_id="55",
        text="same text",
    )
    assert edited is True


def test_telegram_client_clear_message_keyboard_sends_null_reply_markup() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def request_fn(method: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append((method, payload))
        return {"ok": True, "result": {"message_id": 55}}

    cleared = TelegramClient(request_fn=request_fn).clear_message_keyboard(
        chat_id="-100123",
        message_id="55",
    )

    assert cleared is True
    assert calls == [
        (
            "editMessageReplyMarkup",
            {
                "chat_id": "-100123",
                "message_id": "55",
                "reply_markup": {"inline_keyboard": []},
            },
        )
    ]


def test_telegram_client_answer_callback_query_treats_stale_query_as_false() -> None:
    def request_fn(method: str, _payload: dict[str, object]) -> dict[str, object]:
        assert method == "answerCallbackQuery"
        return {
            "ok": False,
            "error_code": 400,
            "description": "Bad Request: query is too old and response timeout expired or query id is invalid",
        }

    answered = TelegramClient(request_fn=request_fn).answer_callback_query(
        callback_query_id="cbq-stale-1",
        text="ack",
    )
    assert answered is False


def test_telegram_client_uses_env_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_BASE_URL", "http://127.0.0.1:8081")
    client = TelegramClient(bot_token="token")
    try:
        assert client.base_url == "http://127.0.0.1:8081"
    finally:
        client.close()
