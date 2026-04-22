from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

MONTH_TO_NUMBER = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
TIME_BUCKET_RE = re.compile(
    r"\b(?:by|before|in|during|on|through|throughout|prior to|by end of|before end of)\s+"
    r"(?:(q[1-4])|"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"(?:\s+(\d{1,2}))?"
    r"(?:,\s*|\s+)?"
    r"(\d{4})?"
    r"|(\d{4}))\b",
    re.IGNORECASE,
)
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
PARTITION_TOLERANCE_CENTS = 2.0
DOMINANCE_TOLERANCE_CENTS = 0.5


@dataclass(frozen=True)
class FamilyStructuralFlag:
    flag_type: str
    detail: str
    peer_market_id: str | None = None
    peer_market_slug: str | None = None
    relation: str | None = None
    focus_price_cents: float | None = None
    peer_price_cents: float | None = None
    price_gap_cents: float | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "flag_type": self.flag_type,
            "detail": self.detail,
            "peer_market_id": self.peer_market_id,
            "peer_market_slug": self.peer_market_slug,
            "relation": self.relation,
            "focus_price_cents": self.focus_price_cents,
            "peer_price_cents": self.peer_price_cents,
            "price_gap_cents": self.price_gap_cents,
        }


@dataclass(frozen=True)
class FamilyMarketSummary:
    market_id: str
    market_slug: str | None
    question: str
    outcome_name: str | None
    liquidity_usd: float | None
    last_price_cents: float | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "market_id": self.market_id,
            "market_slug": self.market_slug,
            "question": self.question,
            "outcome_name": self.outcome_name,
            "liquidity_usd": self.liquidity_usd,
            "last_price_cents": self.last_price_cents,
        }


@dataclass(frozen=True)
class CandidateFamilySummary:
    event_id: str
    event_slug: str | None
    event_title: str | None
    event_category: str | None
    event_end_time: str | None
    total_markets: int
    sibling_count: int
    sibling_markets: tuple[FamilyMarketSummary, ...]
    surface_group_count: int = 0
    price_surface_depth: int = 0
    structural_flag_count: int = 0
    structural_signal_score: int = 0
    dominance_count: int = 0
    dominated_by_count: int = 0
    partition_anomaly_count: int = 0
    negative_implied_hazard_count: int = 0
    rule_scope_adjacency_count: int = 0
    structural_flags: tuple[FamilyStructuralFlag, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_slug": self.event_slug,
            "event_title": self.event_title,
            "event_category": self.event_category,
            "event_end_time": self.event_end_time,
            "total_markets": self.total_markets,
            "sibling_count": self.sibling_count,
            "sibling_markets": [market.as_dict() for market in self.sibling_markets],
            "surface_group_count": self.surface_group_count,
            "price_surface_depth": self.price_surface_depth,
            "structural_flag_count": self.structural_flag_count,
            "structural_signal_score": self.structural_signal_score,
            "dominance_count": self.dominance_count,
            "dominated_by_count": self.dominated_by_count,
            "partition_anomaly_count": self.partition_anomaly_count,
            "negative_implied_hazard_count": self.negative_implied_hazard_count,
            "rule_scope_adjacency_count": self.rule_scope_adjacency_count,
            "structural_flags": [flag.as_dict() for flag in self.structural_flags],
        }


@dataclass(frozen=True)
class _MarketContext:
    summary: FamilyMarketSummary
    normalized_question: str
    normalized_outcome: str | None
    normalized_rules: str
    outcome_template_key: str | None
    temporal_template_key: str | None
    core_question_key: str
    time_rank: int | None


def build_family_summary(
    event: Mapping[str, object],
    *,
    focus_market_id: str,
    sibling_limit: int = 3,
    flag_limit: int = 6,
) -> CandidateFamilySummary:
    raw_markets = event.get("markets")
    markets = raw_markets if isinstance(raw_markets, list) else []
    contexts_list: list[_MarketContext] = []
    for raw_market in markets:
        if not isinstance(raw_market, Mapping):
            continue
        context = _build_market_context(
            raw_market,
            event_end_time=_optional_str(event.get("end_time")),
        )
        if context is not None:
            contexts_list.append(context)
    contexts = tuple(contexts_list)
    siblings = [
        context.summary for context in contexts if context.summary.market_id != focus_market_id
    ]
    siblings.sort(key=lambda item: (-(item.liquidity_usd or 0.0), item.market_id))
    structural_flags, surface_groups, peer_market_ids = _build_structural_flags(
        contexts,
        focus_market_id=focus_market_id,
        flag_limit=flag_limit,
    )
    dominance_count = sum(
        1 for flag in structural_flags if flag.flag_type == "dominates_adjacent_bucket"
    )
    dominated_by_count = sum(
        1 for flag in structural_flags if flag.flag_type == "dominated_by_adjacent_bucket"
    )
    partition_anomaly_count = sum(
        1 for flag in structural_flags if flag.flag_type == "partition_sum_overround"
    )
    negative_implied_hazard_count = sum(
        1 for flag in structural_flags if flag.flag_type == "negative_implied_hazard"
    )
    rule_scope_adjacency_count = sum(
        1 for flag in structural_flags if flag.flag_type == "rule_scope_adjacent"
    )
    structural_signal_score = (
        dominance_count * 3
        + partition_anomaly_count * 2
        + negative_implied_hazard_count * 2
        + rule_scope_adjacency_count
        - dominated_by_count * 2
    )
    return CandidateFamilySummary(
        event_id=_optional_str(event.get("id")) or "unknown-event",
        event_slug=_optional_str(event.get("slug")),
        event_title=_optional_str(event.get("title")),
        event_category=_optional_str(event.get("category")),
        event_end_time=_optional_str(event.get("end_time")),
        total_markets=len(markets),
        sibling_count=len(siblings),
        sibling_markets=tuple(siblings[: max(sibling_limit, 0)]),
        surface_group_count=len(surface_groups),
        price_surface_depth=len(peer_market_ids),
        structural_flag_count=len(structural_flags),
        structural_signal_score=structural_signal_score,
        dominance_count=dominance_count,
        dominated_by_count=dominated_by_count,
        partition_anomaly_count=partition_anomaly_count,
        negative_implied_hazard_count=negative_implied_hazard_count,
        rule_scope_adjacency_count=rule_scope_adjacency_count,
        structural_flags=tuple(structural_flags),
    )


def _build_market_context(
    raw_market: Mapping[str, object],
    *,
    event_end_time: str | None,
) -> _MarketContext | None:
    market_id = _optional_str(raw_market.get("id"))
    if market_id is None:
        return None
    market_slug = _optional_str(raw_market.get("slug"))
    question = _optional_str(raw_market.get("question")) or ""
    outcome_name = _optional_str(raw_market.get("outcome_name"))
    rules_text = _optional_str(raw_market.get("rules_text"))
    summary = FamilyMarketSummary(
        market_id=market_id,
        market_slug=market_slug,
        question=question,
        outcome_name=outcome_name,
        liquidity_usd=_to_float(raw_market.get("liquidity_usd")),
        last_price_cents=_to_market_cents(raw_market.get("last_price")),
    )
    normalized_question = _normalize_text(question)
    normalized_outcome = _normalize_text(outcome_name) if outcome_name else None
    temporal_template_key, time_rank = _extract_time_bucket(
        question=question,
        market_slug=market_slug,
        event_end_time=event_end_time,
    )
    outcome_template_key = _build_outcome_template_key(
        normalized_question=normalized_question,
        normalized_outcome=normalized_outcome,
    )
    core_question_key = _build_core_question_key(
        normalized_question=normalized_question,
        normalized_outcome=normalized_outcome,
        temporal_template_key=temporal_template_key,
    )
    return _MarketContext(
        summary=summary,
        normalized_question=normalized_question,
        normalized_outcome=normalized_outcome,
        normalized_rules=_normalize_text(rules_text),
        outcome_template_key=outcome_template_key,
        temporal_template_key=temporal_template_key,
        core_question_key=core_question_key,
        time_rank=time_rank,
    )


def _build_structural_flags(
    contexts: tuple[_MarketContext, ...],
    *,
    focus_market_id: str,
    flag_limit: int,
) -> tuple[list[FamilyStructuralFlag], set[str], set[str]]:
    by_market_id = {context.summary.market_id: context for context in contexts}
    focus = by_market_id.get(focus_market_id)
    if focus is None:
        return [], set(), set()

    flags: list[FamilyStructuralFlag] = []
    flag_keys: set[tuple[str, str | None]] = set()
    surface_groups: set[str] = set()
    peer_market_ids: set[str] = set()

    def add_flag(
        flag: FamilyStructuralFlag, *, surface_group: str, peer_market_id: str | None
    ) -> None:
        if len(flags) >= max(flag_limit, 0):
            return
        key = (flag.flag_type, peer_market_id)
        if key in flag_keys:
            return
        flag_keys.add(key)
        flags.append(flag)
        surface_groups.add(surface_group)
        if peer_market_id:
            peer_market_ids.add(peer_market_id)

    outcome_group = tuple(
        context
        for context in contexts
        if context.outcome_template_key
        and context.outcome_template_key == focus.outcome_template_key
    )
    if len(outcome_group) >= 2:
        surface_groups.add("partition")
        peer_market_ids.update(
            context.summary.market_id
            for context in outcome_group
            if context.summary.market_id != focus_market_id
        )
        if all(context.summary.last_price_cents is not None for context in outcome_group):
            partition_sum = sum(
                context.summary.last_price_cents or 0.0 for context in outcome_group
            )
            if partition_sum > 100.0 + PARTITION_TOLERANCE_CENTS:
                add_flag(
                    FamilyStructuralFlag(
                        flag_type="partition_sum_overround",
                        detail=f"Comparable outcome surface sums to {partition_sum:.1f}c.",
                        relation="anomaly",
                        focus_price_cents=focus.summary.last_price_cents,
                    ),
                    surface_group="partition",
                    peer_market_id=None,
                )

    temporal_group = tuple(
        context
        for context in contexts
        if context.temporal_template_key
        and context.temporal_template_key == focus.temporal_template_key
        and context.time_rank is not None
    )
    if len(temporal_group) >= 2:
        temporal_chain = tuple(
            sorted(temporal_group, key=lambda item: (item.time_rank, item.summary.market_id))
        )
        surface_groups.add("temporal")
        peer_market_ids.update(
            context.summary.market_id
            for context in temporal_chain
            if context.summary.market_id != focus_market_id
        )
        focus_index = next(
            (
                index
                for index, context in enumerate(temporal_chain)
                if context.summary.market_id == focus_market_id
            ),
            None,
        )
        if focus_index is not None and focus.summary.last_price_cents is not None:
            if focus_index > 0:
                earlier = temporal_chain[focus_index - 1]
                _compare_adjacent_buckets(
                    earlier=earlier,
                    later=focus,
                    add_flag=add_flag,
                    focus_is_later=True,
                )
            if focus_index < len(temporal_chain) - 1:
                later = temporal_chain[focus_index + 1]
                _compare_adjacent_buckets(
                    earlier=focus,
                    later=later,
                    add_flag=add_flag,
                    focus_is_later=False,
                )

    for peer in contexts:
        if peer.summary.market_id == focus_market_id:
            continue
        if not _is_rule_scope_adjacent(focus, peer):
            continue
        add_flag(
            FamilyStructuralFlag(
                flag_type="rule_scope_adjacent",
                detail="Nearby same-outcome expression uses a different rules scope.",
                peer_market_id=peer.summary.market_id,
                peer_market_slug=peer.summary.market_slug,
                relation="adjacent_scope",
                focus_price_cents=focus.summary.last_price_cents,
                peer_price_cents=peer.summary.last_price_cents,
            ),
            surface_group="rule_scope",
            peer_market_id=peer.summary.market_id,
        )

    return flags, surface_groups, peer_market_ids


def _compare_adjacent_buckets(
    *,
    earlier: _MarketContext,
    later: _MarketContext,
    add_flag,
    focus_is_later: bool,
) -> None:
    if earlier.summary.last_price_cents is None or later.summary.last_price_cents is None:
        return
    price_gap = round(
        (later.summary.last_price_cents or 0.0) - (earlier.summary.last_price_cents or 0.0), 4
    )
    if focus_is_later and price_gap < -DOMINANCE_TOLERANCE_CENTS:
        add_flag(
            FamilyStructuralFlag(
                flag_type="negative_implied_hazard",
                detail="Later bucket is cheaper than the adjacent earlier bucket.",
                peer_market_id=earlier.summary.market_id,
                peer_market_slug=earlier.summary.market_slug,
                relation="temporal_inconsistency",
                focus_price_cents=later.summary.last_price_cents,
                peer_price_cents=earlier.summary.last_price_cents,
                price_gap_cents=price_gap,
            ),
            surface_group="temporal",
            peer_market_id=earlier.summary.market_id,
        )
        add_flag(
            FamilyStructuralFlag(
                flag_type="dominates_adjacent_bucket",
                detail="Later bucket is at least as broad and no more expensive than the earlier bucket.",
                peer_market_id=earlier.summary.market_id,
                peer_market_slug=earlier.summary.market_slug,
                relation="dominates",
                focus_price_cents=later.summary.last_price_cents,
                peer_price_cents=earlier.summary.last_price_cents,
                price_gap_cents=price_gap,
            ),
            surface_group="temporal",
            peer_market_id=earlier.summary.market_id,
        )
        return
    if focus_is_later and price_gap <= DOMINANCE_TOLERANCE_CENTS:
        add_flag(
            FamilyStructuralFlag(
                flag_type="dominates_adjacent_bucket",
                detail="Later bucket is at least as broad and no more expensive than the earlier bucket.",
                peer_market_id=earlier.summary.market_id,
                peer_market_slug=earlier.summary.market_slug,
                relation="dominates",
                focus_price_cents=later.summary.last_price_cents,
                peer_price_cents=earlier.summary.last_price_cents,
                price_gap_cents=price_gap,
            ),
            surface_group="temporal",
            peer_market_id=earlier.summary.market_id,
        )
        return
    if (not focus_is_later) and price_gap <= DOMINANCE_TOLERANCE_CENTS:
        add_flag(
            FamilyStructuralFlag(
                flag_type="dominated_by_adjacent_bucket",
                detail="A later, broader bucket is available at a similar or better price.",
                peer_market_id=later.summary.market_id,
                peer_market_slug=later.summary.market_slug,
                relation="dominated_by",
                focus_price_cents=earlier.summary.last_price_cents,
                peer_price_cents=later.summary.last_price_cents,
                price_gap_cents=-price_gap,
            ),
            surface_group="temporal",
            peer_market_id=later.summary.market_id,
        )


def _build_outcome_template_key(
    *,
    normalized_question: str,
    normalized_outcome: str | None,
) -> str | None:
    if not normalized_question or not normalized_outcome:
        return None
    pattern = rf"\b{re.escape(normalized_outcome)}\b"
    if re.search(pattern, normalized_question) is None:
        return None
    return re.sub(pattern, "<outcome>", normalized_question)


def _build_core_question_key(
    *,
    normalized_question: str,
    normalized_outcome: str | None,
    temporal_template_key: str | None,
) -> str:
    text = temporal_template_key or normalized_question
    if normalized_outcome:
        text = re.sub(rf"\b{re.escape(normalized_outcome)}\b", "<outcome>", text)
    return " ".join(text.split())


def _extract_time_bucket(
    *,
    question: str,
    market_slug: str | None,
    event_end_time: str | None,
) -> tuple[str | None, int | None]:
    source = question or market_slug or ""
    match = TIME_BUCKET_RE.search(source)
    if match is None:
        return None, None
    bucket_text = source[: match.start()] + "<time>" + source[match.end() :]
    default_year = _event_year(event_end_time)
    quarter_text, month_name, month_day, explicit_year, bare_year = match.groups()
    if bare_year:
        year = int(bare_year)
        return _normalize_text(bucket_text), year * 10_000
    if quarter_text:
        year = int(explicit_year or default_year or 0)
        quarter = int(quarter_text[1])
        return _normalize_text(bucket_text), year * 10_000 + quarter * 300
    if month_name:
        year = int(explicit_year or default_year or 0)
        month = MONTH_TO_NUMBER[month_name.lower()]
        day = int(month_day or 1)
        return _normalize_text(bucket_text), year * 10_000 + month * 100 + day
    return None, None


def _event_year(event_end_time: str | None) -> int | None:
    if not event_end_time:
        return None
    match = re.search(r"\b(20\d{2})\b", event_end_time)
    if match is None:
        return None
    return int(match.group(1))


def _is_rule_scope_adjacent(focus: _MarketContext, peer: _MarketContext) -> bool:
    if not focus.normalized_outcome or focus.normalized_outcome != peer.normalized_outcome:
        return False
    if not focus.normalized_rules or not peer.normalized_rules:
        return False
    if focus.normalized_rules == peer.normalized_rules:
        return False
    return focus.core_question_key == peer.core_question_key


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(NON_ALNUM_RE.sub(" ", value.lower()).split())


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_market_cents(value: object) -> float | None:
    price = _to_float(value)
    if price is None:
        return None
    if 0.0 <= price <= 1.0:
        return round(price * 100.0, 4)
    return round(price, 4)
