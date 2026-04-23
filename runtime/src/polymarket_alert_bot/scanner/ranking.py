from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from polymarket_alert_bot.scanner.normalizer import ScanCandidate

UNKNOWN_DEADLINE_RANK = 2**62
SECONDS_PER_DAY = 86_400.0
PRIMARY_SLEEVE_ORDER = (
    "family_inconsistency",
    "short_dated",
    "newly_listed",
    "anchor_gap",
    "hot_board",
    "unassigned",
)


@dataclass(frozen=True)
class CandidateRankingSummary:
    supported_runtime_domain: bool
    deadline_available: bool
    deadline_rank: int
    days_to_deadline: float | None
    family_sibling_count: int
    family_surface_group_count: int
    family_price_surface_depth: int
    family_structural_flag_count: int
    family_structural_signal_score: int
    family_dominance_count: int
    family_dominated_by_count: int
    family_partition_anomaly_count: int
    family_negative_implied_hazard_count: int
    family_rule_scope_adjacency_count: int
    liquidity_usd: float
    volume_24h_usd: float
    spread_bps: float | None
    is_degraded: bool
    missing_deadline: bool
    missing_category: bool
    missing_outcome_name: bool
    missing_family_context: bool
    scan_sleeves: tuple[str, ...]
    primary_scan_sleeve: str
    conservative_executable_edge_score: float
    confidence_score: float
    fill_probability_score: float
    uniqueness_score: float
    research_cost_score: float
    catalyst_proximity_score: float
    ambiguity_penalty: float
    crowding_penalty: float
    overlap_penalty: float
    external_anchor_gap_score: float
    category_execution_haircut_cents: float
    theoretical_edge_proxy_cents: float
    execution_adjusted_edge_proxy_cents: float
    alpha_type: str
    execution_style: str
    ranking_score: float
    top_positive_factors: tuple[str, ...]
    top_negative_factors: tuple[str, ...]

    def priority_key(self, *, market_id: str) -> tuple[int, float, float, int, str]:
        return (
            1 if self.is_degraded else 0,
            -self.ranking_score,
            self.spread_bps if self.spread_bps is not None else 1_000_000.0,
            self.deadline_rank,
            market_id,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "supported_runtime_domain": self.supported_runtime_domain,
            "deadline_available": self.deadline_available,
            "deadline_rank": self.deadline_rank,
            "days_to_deadline": self.days_to_deadline,
            "family_sibling_count": self.family_sibling_count,
            "family_surface_group_count": self.family_surface_group_count,
            "family_price_surface_depth": self.family_price_surface_depth,
            "family_structural_flag_count": self.family_structural_flag_count,
            "family_structural_signal_score": self.family_structural_signal_score,
            "family_dominance_count": self.family_dominance_count,
            "family_dominated_by_count": self.family_dominated_by_count,
            "family_partition_anomaly_count": self.family_partition_anomaly_count,
            "family_negative_implied_hazard_count": self.family_negative_implied_hazard_count,
            "family_rule_scope_adjacency_count": self.family_rule_scope_adjacency_count,
            "liquidity_usd": self.liquidity_usd,
            "volume_24h_usd": self.volume_24h_usd,
            "spread_bps": self.spread_bps,
            "is_degraded": self.is_degraded,
            "missing_deadline": self.missing_deadline,
            "missing_category": self.missing_category,
            "missing_outcome_name": self.missing_outcome_name,
            "missing_family_context": self.missing_family_context,
            "scan_sleeves": list(self.scan_sleeves),
            "primary_scan_sleeve": self.primary_scan_sleeve,
            "conservative_executable_edge_score": round(self.conservative_executable_edge_score, 4),
            "confidence_score": round(self.confidence_score, 4),
            "fill_probability_score": round(self.fill_probability_score, 4),
            "uniqueness_score": round(self.uniqueness_score, 4),
            "research_cost_score": round(self.research_cost_score, 4),
            "catalyst_proximity_score": round(self.catalyst_proximity_score, 4),
            "ambiguity_penalty": round(self.ambiguity_penalty, 4),
            "crowding_penalty": round(self.crowding_penalty, 4),
            "overlap_penalty": round(self.overlap_penalty, 4),
            "external_anchor_gap_score": round(self.external_anchor_gap_score, 4),
            "category_execution_haircut_cents": round(self.category_execution_haircut_cents, 4),
            "theoretical_edge_proxy_cents": round(self.theoretical_edge_proxy_cents, 4),
            "execution_adjusted_edge_proxy_cents": round(
                self.execution_adjusted_edge_proxy_cents, 4
            ),
            "alpha_type": self.alpha_type,
            "execution_style": self.execution_style,
            "ranking_score": round(self.ranking_score, 4),
            "top_positive_factors": list(self.top_positive_factors),
            "top_negative_factors": list(self.top_negative_factors),
        }


def candidate_priority_key(candidate: ScanCandidate) -> tuple[int, float, float, int, str]:
    return build_ranking_summary(candidate).priority_key(market_id=candidate.market_id)


def select_judgment_candidates(
    candidates: Sequence[ScanCandidate],
    *,
    max_candidates: int | None,
) -> tuple[ScanCandidate, ...]:
    summaries = {candidate.market_id: build_ranking_summary(candidate) for candidate in candidates}
    ordered_candidates = tuple(
        sorted(
            candidates,
            key=lambda candidate: summaries[candidate.market_id].priority_key(
                market_id=candidate.market_id
            ),
        )
    )
    if max_candidates is None or max_candidates <= 0:
        return ordered_candidates

    selected: list[ScanCandidate] = []
    remaining = list(ordered_candidates)
    while remaining and len(selected) < max_candidates:
        remaining.sort(
            key=lambda candidate: (
                -(
                    summaries[candidate.market_id].ranking_score
                    - _dynamic_overlap_penalty(
                        candidate,
                        summary=summaries[candidate.market_id],
                        selected=selected,
                        summaries=summaries,
                    )
                ),
                summaries[candidate.market_id].priority_key(market_id=candidate.market_id),
            )
        )
        selected.append(remaining.pop(0))
    return tuple(selected)


def build_ranking_summary(candidate: ScanCandidate) -> CandidateRankingSummary:
    deadline_rank = _deadline_rank(candidate.event_end_time)
    days_to_deadline = _days_to_deadline(candidate.event_end_time)
    scan_sleeves = candidate.scan_sleeves or ("unassigned",)
    primary_scan_sleeve = _primary_scan_sleeve(scan_sleeves)
    supported_runtime_domain = _is_supported_runtime_domain(candidate)
    catalyst_proximity_score = _catalyst_proximity_score(days_to_deadline, scan_sleeves)
    confidence_score = _confidence_score(
        candidate,
        deadline_rank=deadline_rank,
        supported_runtime_domain=supported_runtime_domain,
    )
    fill_probability_score = _fill_probability_score(candidate)
    uniqueness_score = _uniqueness_score(candidate, primary_scan_sleeve=primary_scan_sleeve)
    research_cost_score = _research_cost_score(
        candidate,
        supported_runtime_domain=supported_runtime_domain,
    )
    ambiguity_penalty = _ambiguity_penalty(candidate)
    crowding_penalty = _crowding_penalty(candidate, primary_scan_sleeve=primary_scan_sleeve)
    overlap_penalty = _overlap_penalty(candidate)
    external_anchor_gap_score = _external_anchor_gap_score(candidate)
    category_execution_haircut_cents = _category_execution_haircut_cents(
        candidate,
        primary_scan_sleeve=primary_scan_sleeve,
    )
    structural_score = _structural_edge_score(candidate, primary_scan_sleeve=primary_scan_sleeve)
    conservative_executable_edge_score = min(
        100.0,
        structural_score * 0.7
        + catalyst_proximity_score * 0.15
        + fill_probability_score * 0.1
        + external_anchor_gap_score * 0.05,
    )
    confidence_factor = 0.35 + (confidence_score / 100.0) * 0.65
    fill_factor = 0.30 + (fill_probability_score / 100.0) * 0.70
    uniqueness_factor = 0.30 + (uniqueness_score / 100.0) * 0.70
    research_cost_factor = 1.0 + (research_cost_score / 100.0) * 1.5
    penalty_points = (
        ambiguity_penalty
        + crowding_penalty
        + overlap_penalty
        + category_execution_haircut_cents * 4.0
    )
    ranking_score = (
        conservative_executable_edge_score
        * confidence_factor
        * fill_factor
        * uniqueness_factor
        / research_cost_factor
    ) - penalty_points
    ranking_score += 8.0 if supported_runtime_domain else -18.0
    ranking_score += min(candidate.family_summary.sibling_count * 4.0, 12.0)
    alpha_type = _alpha_type(candidate, primary_scan_sleeve=primary_scan_sleeve)
    execution_style = _execution_style(
        candidate,
        fill_probability_score=fill_probability_score,
        crowding_penalty=crowding_penalty,
        category_execution_haircut_cents=category_execution_haircut_cents,
    )
    top_positive_factors, top_negative_factors = _top_factors(
        candidate,
        primary_scan_sleeve=primary_scan_sleeve,
        conservative_executable_edge_score=conservative_executable_edge_score,
        catalyst_proximity_score=catalyst_proximity_score,
        fill_probability_score=fill_probability_score,
        uniqueness_score=uniqueness_score,
        external_anchor_gap_score=external_anchor_gap_score,
        confidence_score=confidence_score,
        ambiguity_penalty=ambiguity_penalty,
        crowding_penalty=crowding_penalty,
        overlap_penalty=overlap_penalty,
        category_execution_haircut_cents=category_execution_haircut_cents,
    )
    return CandidateRankingSummary(
        supported_runtime_domain=supported_runtime_domain,
        deadline_available=deadline_rank != UNKNOWN_DEADLINE_RANK,
        deadline_rank=deadline_rank,
        days_to_deadline=days_to_deadline,
        family_sibling_count=candidate.family_summary.sibling_count,
        family_surface_group_count=candidate.family_summary.surface_group_count,
        family_price_surface_depth=candidate.family_summary.price_surface_depth,
        family_structural_flag_count=candidate.family_summary.structural_flag_count,
        family_structural_signal_score=candidate.family_summary.structural_signal_score,
        family_dominance_count=candidate.family_summary.dominance_count,
        family_dominated_by_count=candidate.family_summary.dominated_by_count,
        family_partition_anomaly_count=candidate.family_summary.partition_anomaly_count,
        family_negative_implied_hazard_count=candidate.family_summary.negative_implied_hazard_count,
        family_rule_scope_adjacency_count=candidate.family_summary.rule_scope_adjacency_count,
        liquidity_usd=candidate.liquidity_usd or 0.0,
        volume_24h_usd=candidate.volume_24h_usd or 0.0,
        spread_bps=candidate.spread_bps,
        is_degraded=candidate.is_degraded,
        missing_deadline=not candidate.event_end_time,
        missing_category=not candidate.event_category,
        missing_outcome_name=not candidate.outcome_name,
        missing_family_context=candidate.family_summary.sibling_count <= 0,
        scan_sleeves=scan_sleeves,
        primary_scan_sleeve=primary_scan_sleeve,
        conservative_executable_edge_score=conservative_executable_edge_score,
        confidence_score=confidence_score,
        fill_probability_score=fill_probability_score,
        uniqueness_score=uniqueness_score,
        research_cost_score=research_cost_score,
        catalyst_proximity_score=catalyst_proximity_score,
        ambiguity_penalty=ambiguity_penalty,
        crowding_penalty=crowding_penalty,
        overlap_penalty=overlap_penalty,
        external_anchor_gap_score=external_anchor_gap_score,
        category_execution_haircut_cents=category_execution_haircut_cents,
        theoretical_edge_proxy_cents=conservative_executable_edge_score,
        execution_adjusted_edge_proxy_cents=max(
            0.0,
            conservative_executable_edge_score - category_execution_haircut_cents * 6.0,
        ),
        alpha_type=alpha_type,
        execution_style=execution_style,
        ranking_score=ranking_score,
        top_positive_factors=top_positive_factors,
        top_negative_factors=top_negative_factors,
    )


def _deadline_rank(event_end_time: str | None) -> int:
    if not event_end_time:
        return UNKNOWN_DEADLINE_RANK
    try:
        return int(datetime.fromisoformat(event_end_time.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return UNKNOWN_DEADLINE_RANK


def _days_to_deadline(event_end_time: str | None) -> float | None:
    if not event_end_time:
        return None
    try:
        deadline = datetime.fromisoformat(event_end_time.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (deadline - datetime.now(UTC)).total_seconds() / SECONDS_PER_DAY)


def _is_supported_runtime_domain(candidate: ScanCandidate) -> bool:
    text = " ".join(
        filter(
            None,
            [
                candidate.event_title or "",
                candidate.question,
                candidate.rules_text or "",
                candidate.event_category or "",
            ],
        )
    ).lower()
    sports_markers = (
        "nba",
        "nfl",
        "mlb",
        "nhl",
        "world cup",
        "premier league",
        "uefa",
        "lineup",
        "injury report",
    )
    crypto_markers = (
        "bitcoin",
        "btc",
        "ethereum",
        "eth",
        "solana",
        "sol",
        "crypto",
        "etf",
        "on-chain",
    )
    politics_macro_markers = (
        "president",
        "election",
        "ceasefire",
        "taiwan",
        "trump",
        "fed",
        "tariff",
        "senate",
        "house",
        "ukraine",
        "china",
        "court",
        "cpi",
        "inflation",
        "rate cut",
    )
    return any(
        _text_matches_marker(text, marker)
        for marker in sports_markers + crypto_markers + politics_macro_markers
    )


def _text_matches_marker(text: str, marker: str) -> bool:
    if " " in marker or "-" in marker:
        return marker in text
    return re.search(rf"\b{re.escape(marker)}\b", text) is not None


def _primary_scan_sleeve(scan_sleeves: Sequence[str]) -> str:
    for sleeve in PRIMARY_SLEEVE_ORDER:
        if sleeve in scan_sleeves:
            return sleeve
    return scan_sleeves[0] if scan_sleeves else "unassigned"


def _catalyst_proximity_score(
    days_to_deadline: float | None,
    scan_sleeves: Sequence[str],
) -> float:
    bonus = 10.0 if "short_dated" in scan_sleeves else 0.0
    if days_to_deadline is None:
        return bonus
    if days_to_deadline <= 7:
        return 40.0 + bonus
    if days_to_deadline <= 30:
        return 30.0 + bonus
    if days_to_deadline <= 90:
        return 18.0 + bonus
    if days_to_deadline <= 180:
        return 8.0 + bonus
    return bonus


def _confidence_score(
    candidate: ScanCandidate,
    *,
    deadline_rank: int,
    supported_runtime_domain: bool,
) -> float:
    score = 18.0 if supported_runtime_domain else 6.0
    if deadline_rank != UNKNOWN_DEADLINE_RANK:
        score += 12.0
    if candidate.event_category:
        score += 8.0
    if candidate.outcome_name:
        score += 6.0
    if candidate.rules_text:
        score += 12.0
    if candidate.family_summary.sibling_count > 0:
        score += 12.0
    if not candidate.is_degraded:
        score += 8.0
    if candidate.family_summary.rule_scope_adjacency_count == 0:
        score += 6.0
    return min(score, 100.0)


def _fill_probability_score(candidate: ScanCandidate) -> float:
    liquidity_score = min((candidate.liquidity_usd or 0.0) / 250.0, 50.0)
    spread_bps = candidate.spread_bps if candidate.spread_bps is not None else 1_200.0
    spread_score = max(0.0, 38.0 - spread_bps / 18.0)
    slippage_bps = candidate.slippage_bps if candidate.slippage_bps is not None else 900.0
    slippage_score = max(0.0, 22.0 - slippage_bps / 25.0)
    degraded_penalty = 20.0 if candidate.is_degraded else 0.0
    return max(0.0, min(liquidity_score + spread_score + slippage_score - degraded_penalty, 100.0))


def _uniqueness_score(candidate: ScanCandidate, *, primary_scan_sleeve: str) -> float:
    score = 8.0
    if primary_scan_sleeve == "family_inconsistency":
        score += 28.0
    elif primary_scan_sleeve == "newly_listed":
        score += 18.0
    elif primary_scan_sleeve == "anchor_gap":
        score += 24.0
    elif primary_scan_sleeve == "short_dated":
        score += 12.0
    score += min(candidate.family_summary.structural_flag_count * 5.0, 24.0)
    score += min(candidate.family_summary.price_surface_depth * 3.0, 12.0)
    score += min(candidate.family_summary.sibling_count * 3.5, 14.0)
    return max(0.0, min(score, 100.0))


def _research_cost_score(
    candidate: ScanCandidate,
    *,
    supported_runtime_domain: bool,
) -> float:
    score = 18.0
    if not candidate.event_end_time:
        score += 12.0
    if not candidate.event_category:
        score += 8.0
    if not candidate.outcome_name:
        score += 8.0
    if not candidate.rules_text:
        score += 12.0
    if candidate.family_summary.sibling_count <= 0:
        score += 8.0
    if not supported_runtime_domain:
        score += 10.0
    return min(score, 100.0)


def _ambiguity_penalty(candidate: ScanCandidate) -> float:
    penalty = candidate.family_summary.rule_scope_adjacency_count * 8.0
    if not candidate.outcome_name:
        penalty += 8.0
    if not candidate.rules_text:
        penalty += 10.0
    if candidate.family_summary.dominated_by_count > 0:
        penalty += candidate.family_summary.dominated_by_count * 4.0
    return min(penalty, 60.0)


def _crowding_penalty(candidate: ScanCandidate, *, primary_scan_sleeve: str) -> float:
    penalty = 12.0 if primary_scan_sleeve == "hot_board" else 0.0
    penalty += min((candidate.volume_24h_usd or 0.0) / 2_500.0, 18.0)
    return min(penalty, 40.0)


def _overlap_penalty(candidate: ScanCandidate) -> float:
    return min(
        max(candidate.family_summary.sibling_count - 1, 0) * 2.0
        + candidate.family_summary.surface_group_count * 3.0,
        28.0,
    )


def _external_anchor_gap_score(candidate: ScanCandidate) -> float:
    if "anchor_gap" not in candidate.scan_sleeves:
        return 0.0
    if candidate.external_anchor_gap_cents is None:
        return 0.0
    return min(abs(candidate.external_anchor_gap_cents) * 3.0, 80.0)


def _structural_edge_score(candidate: ScanCandidate, *, primary_scan_sleeve: str) -> float:
    score = max(candidate.family_summary.structural_signal_score * 10.0, 0.0)
    score += candidate.family_summary.structural_flag_count * 4.0
    score += candidate.family_summary.price_surface_depth * 2.0
    if primary_scan_sleeve == "family_inconsistency":
        score += 18.0
    if primary_scan_sleeve == "newly_listed":
        score += 6.0
    if primary_scan_sleeve == "anchor_gap":
        score += 22.0
    return min(score, 100.0)


def _category_execution_haircut_cents(
    candidate: ScanCandidate,
    *,
    primary_scan_sleeve: str,
) -> float:
    category = (candidate.event_category or "").strip().lower()
    base = 1.5
    if category in {"sports", "entertainment"}:
        base = 3.0
    elif category == "crypto":
        base = 2.0
    elif category in {"politics", "world", "macro", "economy"}:
        base = 1.0
    if primary_scan_sleeve == "newly_listed":
        base += 0.8
    if candidate.spread_bps is not None and candidate.spread_bps > 500:
        base += 0.8
    return round(base, 4)


def _alpha_type(candidate: ScanCandidate, *, primary_scan_sleeve: str) -> str:
    if (
        primary_scan_sleeve == "family_inconsistency"
        or primary_scan_sleeve == "anchor_gap"
        or candidate.family_summary.structural_flag_count
    ):
        return "structure"
    if primary_scan_sleeve == "newly_listed":
        return "behavior"
    if candidate.spread_bps is not None and candidate.spread_bps > 500:
        return "execution"
    return "direction"


def _execution_style(
    candidate: ScanCandidate,
    *,
    fill_probability_score: float,
    crowding_penalty: float,
    category_execution_haircut_cents: float,
) -> str:
    if fill_probability_score >= 70.0 and crowding_penalty <= 12.0:
        return "taker_ok"
    if fill_probability_score >= 50.0 and category_execution_haircut_cents <= 2.0:
        return "maker_bias"
    if candidate.is_degraded or fill_probability_score < 35.0:
        return "monitor_then_work"
    return "wait_for_fill"


def _top_factors(
    candidate: ScanCandidate,
    *,
    primary_scan_sleeve: str,
    conservative_executable_edge_score: float,
    catalyst_proximity_score: float,
    fill_probability_score: float,
    uniqueness_score: float,
    external_anchor_gap_score: float,
    confidence_score: float,
    ambiguity_penalty: float,
    crowding_penalty: float,
    overlap_penalty: float,
    category_execution_haircut_cents: float,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    positive_candidates = [
        (conservative_executable_edge_score, "structural edge proxy"),
        (catalyst_proximity_score, "catalyst proximity"),
        (fill_probability_score, "fill probability"),
        (uniqueness_score, f"unique sleeve:{primary_scan_sleeve}"),
        (external_anchor_gap_score, "external anchor gap"),
        (confidence_score, "metadata confidence"),
    ]
    negative_candidates = [
        (ambiguity_penalty, "semantic/rules ambiguity"),
        (crowding_penalty, "crowding penalty"),
        (overlap_penalty, "overlap penalty"),
        (category_execution_haircut_cents * 8.0, "category execution haircut"),
        (12.0 if candidate.is_degraded else 0.0, "book degraded"),
    ]
    positives = tuple(
        label
        for score, label in sorted(positive_candidates, key=lambda item: item[0], reverse=True)
        if score > 0
    )[:3]
    negatives = tuple(
        label
        for score, label in sorted(negative_candidates, key=lambda item: item[0], reverse=True)
        if score > 0
    )[:3]
    return positives, negatives


def _dynamic_overlap_penalty(
    candidate: ScanCandidate,
    *,
    summary: CandidateRankingSummary,
    selected: Sequence[ScanCandidate],
    summaries: dict[str, CandidateRankingSummary],
) -> float:
    penalty = 0.0
    for selected_candidate in selected:
        selected_summary = summaries[selected_candidate.market_id]
        if candidate.event_id == selected_candidate.event_id:
            penalty += 12.0
        if (
            candidate.event_category
            and candidate.event_category == selected_candidate.event_category
        ):
            penalty += 4.0
        if summary.primary_scan_sleeve == selected_summary.primary_scan_sleeve:
            penalty += 4.0
        if summary.alpha_type == selected_summary.alpha_type:
            penalty += 3.0
    return penalty
