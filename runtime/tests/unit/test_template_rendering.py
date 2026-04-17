from __future__ import annotations

from pathlib import Path

from polymarket_alert_bot.delivery.callback_router import (
    CallbackRouter,
    build_feedback_keyboard,
)
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


def test_render_heartbeat_snapshot() -> None:
    payload = {
        "degraded": True,
        "scan_run_id": "run-scan-001",
        "monitor_run_id": "run-monitor-001",
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
