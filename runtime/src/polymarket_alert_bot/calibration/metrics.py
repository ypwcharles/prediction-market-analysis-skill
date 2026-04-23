from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Mapping

HIGH_PRIORITY_ALERT_KINDS = ("strict", "strict_degraded", "reprice")
SHORT_REVIEW_DAYS = 3
MEDIUM_REVIEW_DAYS = 14


def build_calibration_summary(conn: sqlite3.Connection) -> dict[str, int | float | str]:
    total_high_priority_alerts = conn.execute(
        """
        SELECT COUNT(*)
        FROM alerts
        WHERE alert_kind IN (?, ?, ?)
        """,
        HIGH_PRIORITY_ALERT_KINDS,
    ).fetchone()[0]
    distinct_clusters = conn.execute(
        """
        SELECT COUNT(DISTINCT thesis_cluster_id)
        FROM alerts
        WHERE thesis_cluster_id IS NOT NULL
          AND alert_kind IN (?, ?, ?)
        """,
        HIGH_PRIORITY_ALERT_KINDS,
    ).fetchone()[0]
    repeated_cluster_discount = max(total_high_priority_alerts - distinct_clusters, 0)
    coverage_ratio = _ratio(distinct_clusters, total_high_priority_alerts)
    repetition_ratio = _ratio(repeated_cluster_discount, total_high_priority_alerts)
    score = max(0.0, min(1.0, (0.7 * coverage_ratio) + (0.3 * (1 - repetition_ratio))))
    quality_score = int(round(score * 100))
    review_buckets = _load_review_buckets(conn)
    scan_metrics = _load_scan_metrics(conn)
    trust_metrics = _load_operator_trust_metrics(conn)

    production_override = os.environ.get("POLYMARKET_ALERT_BOT_ALLOW_PRODUCTION_REPORT") == "1"

    if total_high_priority_alerts == 0 or distinct_clusters == 0:
        status = "not_ready"
    elif production_override and repeated_cluster_discount == 0:
        status = "ready_for_production"
    else:
        status = "ready_for_limited_trial"

    return {
        "status": status,
        "total_high_priority_alerts": total_high_priority_alerts,
        "distinct_clusters": distinct_clusters,
        "repeated_cluster_discount": repeated_cluster_discount,
        "quality_score": quality_score,
        "cluster_coverage_ratio": coverage_ratio,
        "review_bucket_short": review_buckets["short"],
        "review_bucket_medium": review_buckets["medium"],
        "review_bucket_long": review_buckets["long"],
        **scan_metrics,
        **trust_metrics,
    }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _load_review_buckets(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN age_days <= ? THEN 1 ELSE 0 END), 0) AS short_bucket,
            COALESCE(SUM(CASE WHEN age_days > ? AND age_days <= ? THEN 1 ELSE 0 END), 0) AS medium_bucket,
            COALESCE(SUM(CASE WHEN age_days > ? THEN 1 ELSE 0 END), 0) AS long_bucket
        FROM (
            SELECT (julianday('now') - julianday(created_at)) AS age_days
            FROM alerts
            WHERE alert_kind IN (?, ?, ?)
              AND created_at IS NOT NULL
        )
        """,
        [
            SHORT_REVIEW_DAYS,
            SHORT_REVIEW_DAYS,
            MEDIUM_REVIEW_DAYS,
            MEDIUM_REVIEW_DAYS,
            *HIGH_PRIORITY_ALERT_KINDS,
        ],
    ).fetchone()
    return {
        "short": int(row["short_bucket"]),
        "medium": int(row["medium_bucket"]),
        "long": int(row["long_bucket"]),
    }


def _load_scan_metrics(conn: sqlite3.Connection) -> dict[str, int | float | str]:
    aggregate = conn.execute(
        """
        SELECT
            COUNT(*) AS scan_run_count,
            COALESCE(SUM(CASE WHEN status != 'clean' THEN 1 ELSE 0 END), 0)
                AS degraded_scan_run_count,
            COALESCE(SUM(scanned_contracts), 0) AS scanned_contracts_total,
            COALESCE(SUM(shortlisted_candidates), 0) AS shortlisted_candidates_total,
            COALESCE(SUM(promoted_seed_count), 0) AS promoted_seed_count_total,
            COALESCE(SUM(families_with_structural_flags), 0)
                AS families_with_structural_flags_total,
            COALESCE(SUM(structurally_flagged_candidates), 0)
                AS structurally_flagged_candidates_total,
            COALESCE(SUM(retrieved_shortlist_candidates), 0)
                AS retrieved_shortlist_candidates_total,
            COALESCE(SUM(strict_count), 0) AS strict_count_total,
            COALESCE(SUM(research_count), 0) AS research_count_total,
            COALESCE(SUM(skipped_count), 0) AS skipped_count_total
        FROM runs
        WHERE run_type = 'scan'
        """
    ).fetchone()
    latest = conn.execute(
        """
        SELECT
            scanned_events,
            scanned_contracts,
            shortlisted_candidates,
            promoted_seed_count
        FROM runs
        WHERE run_type = 'scan'
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    sleeve_totals = _load_sleeve_totals(conn)

    scan_run_count = int(aggregate["scan_run_count"])
    degraded_scan_run_count = int(aggregate["degraded_scan_run_count"])
    latest_scan = latest or {}
    return {
        "scan_run_count": scan_run_count,
        "degraded_scan_run_count": degraded_scan_run_count,
        "scan_degraded_rate": _ratio(degraded_scan_run_count, scan_run_count),
        "scanned_contracts_total": int(aggregate["scanned_contracts_total"]),
        "shortlisted_candidates_total": int(aggregate["shortlisted_candidates_total"]),
        "promoted_seed_count_total": int(aggregate["promoted_seed_count_total"]),
        "families_with_structural_flags_total": int(
            aggregate["families_with_structural_flags_total"]
        ),
        "structurally_flagged_candidates_total": int(
            aggregate["structurally_flagged_candidates_total"]
        ),
        "retrieved_shortlist_candidates_total": int(
            aggregate["retrieved_shortlist_candidates_total"]
        ),
        "strict_count_total": int(aggregate["strict_count_total"]),
        "research_count_total": int(aggregate["research_count_total"]),
        "skipped_count_total": int(aggregate["skipped_count_total"]),
        "latest_scan_events": int(latest_scan["scanned_events"]) if latest else 0,
        "latest_scan_contracts": int(latest_scan["scanned_contracts"]) if latest else 0,
        "latest_scan_shortlisted": int(latest_scan["shortlisted_candidates"]) if latest else 0,
        "latest_scan_promoted": int(latest_scan["promoted_seed_count"]) if latest else 0,
        "sleeve_input_totals": _format_sleeve_totals(sleeve_totals["input"]),
        "sleeve_shortlist_totals": _format_sleeve_totals(sleeve_totals["shortlist"]),
        "sleeve_promoted_totals": _format_sleeve_totals(sleeve_totals["promoted"]),
    }


def _load_sleeve_totals(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {
        "input": {},
        "shortlist": {},
        "promoted": {},
    }
    rows = conn.execute(
        """
        SELECT
            sleeve_input_counts_json,
            sleeve_shortlist_counts_json,
            sleeve_promoted_counts_json
        FROM runs
        WHERE run_type = 'scan'
        """
    ).fetchall()
    for row in rows:
        _merge_json_counts(totals["input"], row["sleeve_input_counts_json"])
        _merge_json_counts(totals["shortlist"], row["sleeve_shortlist_counts_json"])
        _merge_json_counts(totals["promoted"], row["sleeve_promoted_counts_json"])
    return totals


def _merge_json_counts(total: dict[str, int], raw_value: object) -> None:
    if not raw_value:
        return
    try:
        payload = json.loads(str(raw_value))
    except json.JSONDecodeError:
        return
    if not isinstance(payload, Mapping):
        return
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, (int, float)):
            continue
        total[key] = total.get(key, 0) + int(value)


def _format_sleeve_totals(totals: Mapping[str, int]) -> str:
    if not totals:
        return "-"
    ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    return " | ".join(f"{key}={value}" for key, value in ordered)


def _load_operator_trust_metrics(conn: sqlite3.Connection) -> dict[str, int | float]:
    feedback = conn.execute(
        """
        SELECT
            COUNT(*) AS feedback_event_count,
            COALESCE(SUM(CASE WHEN feedback_type = 'claimed_buy' THEN 1 ELSE 0 END), 0)
                AS claimed_buy_feedback_count,
            COALESCE(SUM(CASE WHEN feedback_type = 'disagree' THEN 1 ELSE 0 END), 0)
                AS disagree_feedback_count,
            COALESCE(SUM(CASE WHEN feedback_type = 'close_thesis' THEN 1 ELSE 0 END), 0)
                AS close_thesis_feedback_count,
            COALESCE(AVG((julianday(feedback.created_at) - julianday(alerts.created_at)) * 24), 0)
                AS avg_feedback_latency_hours
        FROM feedback
        LEFT JOIN alerts ON alerts.id = feedback.alert_id
        """
    ).fetchone()
    stale_alert_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM alerts
        WHERE status = 'stale'
        """
    ).fetchone()[0]
    feedback_event_count = int(feedback["feedback_event_count"])
    return {
        "stale_alert_count": int(stale_alert_count),
        "feedback_event_count": feedback_event_count,
        "claimed_buy_feedback_count": int(feedback["claimed_buy_feedback_count"]),
        "disagree_feedback_count": int(feedback["disagree_feedback_count"]),
        "close_thesis_feedback_count": int(feedback["close_thesis_feedback_count"]),
        "avg_feedback_latency_hours": round(float(feedback["avg_feedback_latency_hours"]), 2),
        "disagree_feedback_rate": _ratio(
            int(feedback["disagree_feedback_count"]),
            feedback_event_count,
        ),
    }
