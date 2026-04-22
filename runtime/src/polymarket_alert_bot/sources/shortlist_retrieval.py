from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from polymarket_alert_bot.config.settings import RuntimeConfig
from polymarket_alert_bot.scanner.board_scan import AlertSeed
from polymarket_alert_bot.sources.evidence_enricher import EvidenceItem
from polymarket_alert_bot.sources.feed_loader import load_feed_rows
from polymarket_alert_bot.sources.news_client import NewsClient
from polymarket_alert_bot.sources.x_client import XClient

MAX_ITEMS_PER_SOURCE = 4
STOPWORDS = {
    "the",
    "will",
    "with",
    "from",
    "that",
    "this",
    "have",
    "after",
    "before",
    "into",
    "about",
    "candidate",
    "board",
    "market",
}


@dataclass(frozen=True)
class ShortlistRetrievalResult:
    items: tuple[EvidenceItem, ...]
    degraded_reasons: tuple[str, ...]


def retrieve_shortlist_evidence(
    seed: AlertSeed, config: RuntimeConfig, *, registry
) -> ShortlistRetrievalResult:
    phrases, tokens = _build_query_terms(seed)
    if not phrases and not tokens:
        return ShortlistRetrievalResult(items=(), degraded_reasons=())

    retrieved_items: list[EvidenceItem] = []
    degraded_reasons: list[str] = []

    news_source = config.news_feed_url or config.news_samples_path
    if news_source:
        try:
            rows = load_feed_rows(news_source)
            matched_rows = _filter_rows(rows, phrases=phrases, tokens=tokens)
            retrieved_items.extend(
                NewsClient().normalize_items(matched_rows)[:MAX_ITEMS_PER_SOURCE]
            )
        except Exception as exc:
            degraded_reasons.append(f"shortlist_news_failed:{exc.__class__.__name__}")

    x_source = config.x_feed_url or config.x_samples_path
    if x_source:
        try:
            rows = load_feed_rows(x_source)
            filtered_rows = XClient().filter_rows(rows, allowed_handles=registry.x_handles)
            matched_rows = _filter_rows(filtered_rows, phrases=phrases, tokens=tokens)
            retrieved_items.extend(XClient().normalize_items(matched_rows)[:MAX_ITEMS_PER_SOURCE])
        except Exception as exc:
            degraded_reasons.append(f"shortlist_x_failed:{exc.__class__.__name__}")

    return ShortlistRetrievalResult(
        items=tuple(_dedupe_items(retrieved_items)),
        degraded_reasons=tuple(degraded_reasons),
    )


def _build_query_terms(seed: AlertSeed) -> tuple[tuple[str, ...], tuple[str, ...]]:
    raw_phrases = [
        seed.event_title,
        seed.question,
        seed.outcome_name,
        seed.event_category,
        _deadline_phrase(seed.event_end_time),
        *_family_query_phrases(seed),
        _slug_phrase(seed.event_slug),
        _slug_phrase(seed.market_slug),
    ]
    phrases: list[str] = []
    seen_phrases: set[str] = set()
    for raw_phrase in raw_phrases:
        if not raw_phrase:
            continue
        normalized = _normalize_text(raw_phrase)
        if len(normalized) < 4 or normalized in seen_phrases:
            continue
        phrases.append(normalized)
        seen_phrases.add(normalized)

    token_candidates: list[str] = []
    for phrase in phrases:
        token_candidates.extend(re.findall(r"[a-z0-9]{3,}", phrase))
    tokens: list[str] = []
    seen_tokens: set[str] = set()
    for token in token_candidates:
        if token in STOPWORDS or token in seen_tokens:
            continue
        tokens.append(token)
        seen_tokens.add(token)
    return tuple(phrases[:8]), tuple(tokens[:12])


def _filter_rows(
    rows: Iterable[dict[str, object]],
    *,
    phrases: tuple[str, ...],
    tokens: tuple[str, ...],
) -> list[dict[str, object]]:
    scored: list[tuple[int, dict[str, object]]] = []
    for row in rows:
        row_dict = dict(row)
        haystack = _normalize_text(_row_text(row_dict))
        if not haystack:
            continue
        phrase_hits = sum(1 for phrase in phrases if phrase in haystack)
        token_hits = sum(
            1 for token in tokens if re.search(rf"\b{re.escape(token)}\b", haystack) is not None
        )
        score = phrase_hits * 3 + token_hits
        if phrase_hits == 0 and token_hits < 2:
            continue
        row_dict["_retrieval_score"] = score
        scored.append((score, row_dict))
    scored.sort(
        key=lambda item: (
            -item[0],
            -_freshness_rank(item[1].get("fetched_at")),
            str(item[1].get("source_id") or ""),
        )
    )
    return [row for _, row in scored[:MAX_ITEMS_PER_SOURCE]]


def _row_text(row: dict[str, object]) -> str:
    text_parts: list[str] = []
    for key in (
        "title",
        "headline",
        "claim_snippet",
        "summary",
        "description",
        "url",
        "source_id",
        "handle",
        "author_handle",
    ):
        value = row.get(key)
        if value is None:
            continue
        text_parts.append(str(value))
    return " ".join(text_parts)


def _dedupe_items(items: Iterable[EvidenceItem]) -> list[EvidenceItem]:
    deduped: list[EvidenceItem] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (item.source_id, item.url, item.claim_snippet)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _normalize_text(text: object) -> str:
    return " ".join(str(text).replace("-", " ").replace("_", " ").lower().split())


def _slug_phrase(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("-", " ")


def _family_query_phrases(seed: AlertSeed) -> tuple[str, ...]:
    phrases: list[str] = []
    for sibling in seed.family_summary.sibling_markets[:2]:
        if sibling.question:
            phrases.append(sibling.question)
        if sibling.outcome_name:
            phrases.append(sibling.outcome_name)
    return tuple(phrases)


def _deadline_phrase(value: str | None) -> str | None:
    if not value:
        return None
    try:
        deadline = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return deadline.strftime("%B %d %Y").replace(" 0", " ")


def _freshness_rank(value: object) -> float:
    if value is None:
        return -1.0
    text = str(value).strip()
    if not text:
        return -1.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return -1.0
