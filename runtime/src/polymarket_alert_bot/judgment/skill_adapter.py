from __future__ import annotations

from collections.abc import Callable
from typing import Any

from polymarket_alert_bot.judgment.result_parser import ParsedJudgment, ParseError, parse_judgment_result


SkillRunner = Callable[[dict[str, Any], int], dict[str, Any] | str]


class SkillAdapter:
    """Adapter around the runtime judgment contract."""

    def __init__(self, *, runner: SkillRunner, timeout_seconds: int = 90) -> None:
        self._runner = runner
        self.timeout_seconds = timeout_seconds

    def build_payload(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "contract_version": "runtime.v1",
            "context": context,
            "response_schema": {
                "required": [
                    "alert_kind",
                    "cluster_action",
                    "ttl_hours",
                    "citations",
                    "triggers",
                    "archive_payload",
                ],
                "alert_kind_enum": [
                    "strict",
                    "strict_degraded",
                    "research",
                    "reprice",
                    "monitor",
                    "heartbeat",
                    "degraded",
                ],
            },
        }

    def judge(self, context: dict[str, Any]) -> ParsedJudgment:
        payload = self.build_payload(context)
        try:
            raw = self._runner(payload, self.timeout_seconds)
        except TimeoutError:
            return ParsedJudgment.degraded("skill_timeout")

        try:
            return parse_judgment_result(raw)
        except ParseError:
            return ParsedJudgment.degraded("malformed_skill_output")
