from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen
from uuid import uuid4

from polymarket_alert_bot.config.settings import RuntimeConfig, RuntimePaths, load_runtime_config
from polymarket_alert_bot.models.enums import RunStatus, RunType
from polymarket_alert_bot.monitor.staleness import mark_stale_alerts
from polymarket_alert_bot.monitor.trigger_engine import (
    condition_met,
    evaluate_stored_trigger,
    is_narrative_trigger,
    observation_key_for_threshold,
    rearm_trigger,
)
from polymarket_alert_bot.scanner.clob_client import BookSnapshot, degraded_snapshot, fetch_book
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations
from polymarket_alert_bot.storage.repositories import RuntimeRepository


@dataclass(frozen=True)
class MonitorOutcome:
    run_id: str
    stale_alert_ids: list[str]
    fired_actions: list[dict[str, object]]
    pending_recheck_actions: list[dict[str, object]]
    requires_llm_recheck_trigger_ids: list[str]
    reconciled_claim_ids: list[str]
    synced_official_positions: int


_ORDERBOOK_OBSERVATION_THRESHOLD_KINDS = {
    "price",
    "price_cents",
    "spread",
    "spread_bps",
    "slippage",
    "slippage_bps",
    "execution_cost",
    "execution_cost_bps",
}


def sync_official_positions(conn: sqlite3.Connection, rows: list[dict[str, object]]) -> None:
    RuntimeRepository(conn).replace_positions(rows)


def reconcile_claimed_position(
    conn: sqlite3.Connection,
    *,
    condition_id: str,
    token_id: str,
    snapshot_as_of: str,
) -> list[str]:
    claim_rows = conn.execute(
        """
        SELECT id
        FROM positions
        WHERE condition_id = ?
          AND token_id = ?
          AND truth_source = 'telegram_claim'
        """,
        [condition_id, token_id],
    ).fetchall()
    claim_ids = [str(row["id"]) for row in claim_rows]
    if not claim_ids:
        return []

    conn.execute(
        """
        UPDATE positions
        SET status = 'open',
            truth_source = 'official_api',
            snapshot_as_of = ?,
            updated_at = ?
        WHERE condition_id = ?
          AND token_id = ?
          AND truth_source = 'telegram_claim'
        """,
        [snapshot_as_of, snapshot_as_of, condition_id, token_id],
    )
    conn.execute(
        """
        DELETE FROM positions
        WHERE condition_id = ?
          AND token_id = ?
          AND truth_source = 'official_api'
          AND id NOT IN ({})
        """.format(", ".join("?" for _ in claim_ids)),
        [condition_id, token_id, *claim_ids],
    )
    conn.commit()
    return claim_ids


def _coalesce(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _normalize_avg_entry_cents(row: dict[str, Any]) -> float | None:
    avg = _parse_float(
        _coalesce(
            row,
            "avg_entry_cents",
            "avgEntryCents",
            "avg_price_cents",
            "avgPriceCents",
            "avg_entry",
            "avgEntry",
            "avg_price",
            "avgPrice",
        )
    )
    if avg is None:
        return None
    return avg * 100.0 if avg <= 1.0 else avg


def normalize_official_positions(
    payload: object,
    *,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    timestamp = (now or datetime.now(UTC)).isoformat()
    if isinstance(payload, dict):
        raw_rows = payload.get("positions") or payload.get("data") or payload.get("result") or []
    else:
        raw_rows = payload

    if not isinstance(raw_rows, list):
        return []

    normalized: list[dict[str, object]] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        condition_id = _coalesce(item, "condition_id", "conditionId", "condition")
        token_id = _coalesce(item, "token_id", "tokenId", "asset")
        if not condition_id or not token_id:
            continue

        size_shares = _parse_float(
            _coalesce(item, "size_shares", "sizeShares", "size", "shares", "amount")
        )
        if size_shares is None:
            continue

        snapshot_as_of = str(
            _coalesce(item, "snapshot_as_of", "snapshotAsOf", "asOf", "fetched_at") or timestamp
        )
        side_text = str(_coalesce(item, "side", "outcome", "positionSide") or "YES").strip().upper()
        status = (
            str(_coalesce(item, "status", "position_status", "positionStatus") or "")
            .strip()
            .lower()
        )
        if not status:
            status = "open" if size_shares > 0 else "closed"

        position_id = str(_coalesce(item, "id") or f"official-{condition_id}-{token_id}")
        normalized.append(
            {
                "id": position_id,
                "condition_id": str(condition_id),
                "token_id": str(token_id),
                "market_id": _coalesce(item, "market_id", "marketId", "market"),
                "thesis_cluster_id": _coalesce(item, "thesis_cluster_id", "thesisClusterId"),
                "side": side_text,
                "size_shares": size_shares,
                "avg_entry_cents": _normalize_avg_entry_cents(item),
                "status": status,
                "truth_source": "official_api",
                "snapshot_as_of": snapshot_as_of,
                "updated_at": str(_coalesce(item, "updated_at", "updatedAt") or timestamp),
            }
        )
    return normalized


def _request_json(
    url: str,
    *,
    params: dict[str, str],
    http_client: Any | None = None,
) -> object:
    if http_client is not None:
        if callable(http_client):
            return http_client(url=url, params=params)
        if hasattr(http_client, "get_json"):
            return http_client.get_json(url, params=params)
        if hasattr(http_client, "get"):
            response = http_client.get(url, params=params)
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            if hasattr(response, "json"):
                return response.json()
            return response
    query = urlencode(params)
    target_url = f"{url}?{query}" if query else url
    with urlopen(target_url) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_official_positions(
    *,
    runtime_config: RuntimeConfig | None = None,
    http_client: Any | None = None,
    payload: object | None = None,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    if payload is None:
        config = runtime_config or load_runtime_config()
        params: dict[str, str] = {}
        if config.positions_user:
            params["user"] = config.positions_user
        payload = _request_json(config.positions_url, params=params, http_client=http_client)
    return normalize_official_positions(payload, now=now)


def _normalize_threshold_kind(value: Any) -> str:
    return str(value or "").strip().lower()


def _requires_live_orderbook(trigger_row: sqlite3.Row) -> bool:
    return (
        _normalize_threshold_kind(trigger_row["threshold_kind"])
        in _ORDERBOOK_OBSERVATION_THRESHOLD_KINDS
    )


def _fetch_live_book(token_id: str, *, url: str) -> BookSnapshot:
    try:
        snapshot = fetch_book(token_id, url=url)
    except TypeError:
        # Support simplified monkeypatch stubs that only accept token_id.
        snapshot = fetch_book(token_id)
    except Exception:
        return degraded_snapshot(token_id, "book_fetch_error")
    if not isinstance(snapshot, BookSnapshot):
        return degraded_snapshot(token_id, "book_malformed")
    return snapshot


def _load_live_book_snapshots(
    rows: list[sqlite3.Row],
    *,
    runtime_config: RuntimeConfig,
) -> dict[str, BookSnapshot]:
    token_ids: set[str] = set()
    for row in rows:
        token_id = str(row["token_id"] or "").strip()
        if token_id and _requires_live_orderbook(row):
            token_ids.add(token_id)
    return {
        token_id: _fetch_live_book(token_id, url=runtime_config.clob_book_url)
        for token_id in token_ids
    }


def _price_cents_from_snapshot(snapshot: BookSnapshot | None) -> float | None:
    if snapshot is None or snapshot.is_degraded:
        return None
    if snapshot.best_ask is not None:
        return snapshot.best_ask * 100.0
    if snapshot.best_bid is not None:
        return snapshot.best_bid * 100.0
    return None


def _build_observations(
    conn: sqlite3.Connection,
    trigger_row: sqlite3.Row,
    *,
    book_snapshot: BookSnapshot | None = None,
) -> dict[str, object]:
    token_id = trigger_row["token_id"]
    position_row = None
    if token_id:
        position_row = conn.execute(
            """
            SELECT
                SUM(size_shares) AS position_size_shares,
                MAX(CASE WHEN status = 'open' THEN 'open' ELSE status END) AS position_status
            FROM positions
            WHERE token_id = ?
              AND truth_source = 'official_api'
            """,
            [token_id],
        ).fetchone()
    live_price_cents = _price_cents_from_snapshot(book_snapshot)
    live_spread_bps = (
        None if book_snapshot is None or book_snapshot.is_degraded else book_snapshot.spread_bps
    )
    live_slippage_bps = (
        None if book_snapshot is None or book_snapshot.is_degraded else book_snapshot.slippage_bps
    )
    spread_bps = live_spread_bps if live_spread_bps is not None else trigger_row["spread_bps"]
    slippage_bps = live_slippage_bps if live_slippage_bps is not None else trigger_row["slippage_bps"]
    execution_cost_bps = None
    if live_spread_bps is not None and live_slippage_bps is not None:
        execution_cost_bps = float(live_spread_bps) + float(live_slippage_bps)
    return {
        "price_cents": live_price_cents,
        "executable_edge_cents": trigger_row["executable_edge_cents"],
        "theoretical_edge_cents": trigger_row["theoretical_edge_cents"],
        "spread_bps": spread_bps,
        "slippage_bps": slippage_bps,
        "execution_cost_bps": execution_cost_bps,
        "position_size_shares": position_row["position_size_shares"] if position_row else None,
        "position_status": position_row["position_status"] if position_row else None,
        "book_state": "quotes_missing"
        if book_snapshot is None or book_snapshot.is_degraded
        else "quotes_available",
        "narrative": trigger_row["why_now"],
    }


def _select_trigger_rows(
    conn: sqlite3.Connection,
    *,
    states: tuple[str, ...],
) -> list[sqlite3.Row]:
    placeholders = ", ".join("?" for _ in states)
    return conn.execute(
        f"""
        SELECT
            t.*,
            a.market_id,
            a.token_id,
            a.theoretical_edge_cents,
            a.executable_edge_cents,
            a.spread_bps,
            a.slippage_bps,
            a.max_entry_cents,
            a.why_now
        FROM triggers AS t
        JOIN alerts AS a ON a.id = t.alert_id
        WHERE a.status = 'active'
          AND t.state IN ({placeholders})
        ORDER BY t.created_at, t.id
        """,
        list(states),
    ).fetchall()


def _condition_still_met(trigger: dict[str, Any], *, observations: dict[str, object]) -> bool:
    if is_narrative_trigger(trigger):
        return False
    observation = observations.get(observation_key_for_threshold(trigger.get("threshold_kind")))
    observed_state = str(observation) if observation is not None else None
    observed_value: float | str | None
    if isinstance(observation, (int, float)):
        observed_value = float(observation)
    elif isinstance(observation, str):
        observed_value = observation
    else:
        observed_value = None
    return condition_met(trigger, observed_value=observed_value, observed_state=observed_state)


def _rearm_snoozed_triggers(
    conn: sqlite3.Connection,
    *,
    now: datetime,
    runtime_config: RuntimeConfig,
) -> None:
    rows = _select_trigger_rows(conn, states=("snoozed",))
    if not rows:
        return
    book_snapshots = _load_live_book_snapshots(rows, runtime_config=runtime_config)
    for row in rows:
        trigger = dict(row)
        book_snapshot = book_snapshots.get(str(row["token_id"] or "").strip())
        observations = _build_observations(conn, row, book_snapshot=book_snapshot)
        updated = rearm_trigger(
            trigger,
            now=now,
            condition_still_met=_condition_still_met(trigger, observations=observations),
        )
        if updated.get("state") == row["state"]:
            continue
        conn.execute(
            """
            UPDATE triggers
            SET state = ?, cooldown_until = ?, updated_at = ?
            WHERE id = ?
            """,
            [
                updated.get("state", row["state"]),
                updated.get("cooldown_until"),
                now.isoformat(),
                row["id"],
            ],
        )
    conn.commit()


def _evaluate_triggers(
    conn: sqlite3.Connection,
    *,
    now: datetime,
    runtime_config: RuntimeConfig,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows = _select_trigger_rows(conn, states=("armed", "rearmed"))
    book_snapshots = _load_live_book_snapshots(rows, runtime_config=runtime_config)
    fired_actions: list[dict[str, object]] = []
    pending_recheck_actions: list[dict[str, object]] = []
    for row in rows:
        trigger = dict(row)
        book_snapshot = book_snapshots.get(str(row["token_id"] or "").strip())
        observations = _build_observations(conn, row, book_snapshot=book_snapshot)
        evaluation = evaluate_stored_trigger(trigger, observations=observations, now=now)
        updated_trigger = evaluation["updated_trigger"]
        conn.execute(
            """
            UPDATE triggers
            SET state = ?, cooldown_until = ?, last_fired_at = ?, updated_at = ?
            WHERE id = ?
            """,
            [
                updated_trigger.get("state", row["state"]),
                updated_trigger.get("cooldown_until"),
                updated_trigger.get("last_fired_at"),
                now.isoformat(),
                row["id"],
            ],
        )
        action_payload = {
            "trigger_id": row["id"],
            "alert_id": row["alert_id"],
            "thesis_cluster_id": row["thesis_cluster_id"],
            "trigger_type": row["trigger_type"],
            "trigger_state": updated_trigger.get("state", row["state"]),
            "suggested_action": row["suggested_action"],
            "observation": evaluation["observation"],
            "requires_llm_recheck": evaluation["requires_llm_recheck"],
        }
        if evaluation["requires_llm_recheck"]:
            pending_recheck_actions.append(action_payload)
        elif evaluation["fired"]:
            fired_actions.append(action_payload)
    conn.commit()
    return fired_actions, pending_recheck_actions


def _reconcile_claims_with_official_rows(
    conn: sqlite3.Connection,
    *,
    official_rows: list[dict[str, object]],
    snapshot_as_of: str,
) -> list[str]:
    reconciled_claim_ids: list[str] = []
    seen_keys: set[tuple[str, str]] = set()
    for row in official_rows:
        key = (str(row["condition_id"]), str(row["token_id"]))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        reconciled_claim_ids.extend(
            reconcile_claimed_position(
                conn,
                condition_id=key[0],
                token_id=key[1],
                snapshot_as_of=snapshot_as_of,
            )
        )
    return reconciled_claim_ids


def run_monitor(
    paths: RuntimePaths,
    *,
    runtime_config: RuntimeConfig | None = None,
    positions_http_client: Any | None = None,
    official_positions_payload: object | None = None,
    now: datetime | None = None,
) -> MonitorOutcome:
    monitor_now = now or datetime.now(UTC)
    timestamp = monitor_now.isoformat()
    run_id = str(uuid4())
    conn = connect_db(paths.db_path)
    apply_migrations(conn)

    config = runtime_config or load_runtime_config()
    should_sync_positions = bool(
        official_positions_payload is not None
        or positions_http_client is not None
        or config.positions_user
    )
    official_rows: list[dict[str, object]] = []
    degraded_reason: str | None = None
    status = RunStatus.CLEAN
    if should_sync_positions:
        try:
            official_rows = fetch_official_positions(
                runtime_config=config,
                http_client=positions_http_client,
                payload=official_positions_payload,
                now=monitor_now,
            )
            sync_official_positions(conn, official_rows)
        except Exception as exc:  # pragma: no cover - external integration path
            degraded_reason = f"official_positions_sync_failed:{exc.__class__.__name__}"
            status = RunStatus.DEGRADED

    reconciled_claim_ids = _reconcile_claims_with_official_rows(
        conn,
        official_rows=official_rows,
        snapshot_as_of=timestamp,
    )
    _rearm_snoozed_triggers(conn, now=monitor_now, runtime_config=config)
    stale_alert_ids = mark_stale_alerts(conn, now=monitor_now)
    fired_actions, pending_recheck_actions = _evaluate_triggers(
        conn,
        now=monitor_now,
        runtime_config=config,
    )
    outcome = MonitorOutcome(
        run_id=run_id,
        stale_alert_ids=stale_alert_ids,
        fired_actions=fired_actions,
        pending_recheck_actions=pending_recheck_actions,
        requires_llm_recheck_trigger_ids=[
            str(item["trigger_id"]) for item in pending_recheck_actions
        ],
        reconciled_claim_ids=reconciled_claim_ids,
        synced_official_positions=len(official_rows),
    )
    RuntimeRepository(conn).upsert_run(
        {
            "id": run_id,
            "run_type": RunType.MONITOR.value,
            "status": status.value,
            "started_at": timestamp,
            "finished_at": timestamp,
            "degraded_reason": degraded_reason,
            "scanned_events": len(stale_alert_ids),
            "scanned_contracts": len(fired_actions) + len(pending_recheck_actions),
            "strict_count": len(fired_actions),
            "research_count": len(pending_recheck_actions),
            "skipped_count": len(stale_alert_ids),
            "heartbeat_sent": 0,
            "created_at": timestamp,
        }
    )
    return outcome
