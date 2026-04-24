from __future__ import annotations

from typing import Any, Mapping

_TRIGGER_LABELS = {
    "price_threshold": "价格阈值",
    "price_reprice": "价格重估",
    "catalyst_checkpoint": "催化剂检查",
    "rule_change_monitor": "规则变化监控",
    "narrative_reassessment": "叙事复核",
    "market_data_recheck": "盘口状态复核",
}


def _as_text(value: Any, *, default: str = "-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _contains_cjk(value: Any) -> bool:
    text = _as_text(value, default="")
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _pick_value(*values: Any, default: str = "-") -> str:
    for value in values:
        text = _as_text(value, default="")
        if text:
            return text
    return default


def _pick_preferred_text(*values: Any, default: str = "-") -> str:
    for value in values:
        text = _as_text(value, default="")
        if text and _contains_cjk(text):
            return text
    for value in values:
        text = _as_text(value, default="")
        if text:
            return text
    return default


def _normalize_triggers(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    trigger_candidates = payload.get("triggers")
    if isinstance(trigger_candidates, list):
        triggers = [_as_mapping(item) for item in trigger_candidates if _as_mapping(item)]
        if triggers:
            return triggers
    trigger = _as_mapping(payload.get("trigger"))
    if trigger:
        return [trigger]
    fallback = {
        "trigger_type": payload.get("trigger_type"),
        "trigger_state": payload.get("trigger_state"),
        "observation": payload.get("observation"),
        "suggested_action": payload.get("suggested_action"),
    }
    if any(value not in (None, "") for value in fallback.values()):
        return [fallback]
    return []


def _format_trigger(trigger: Mapping[str, Any]) -> str:
    trigger_type = _pick_value(
        trigger.get("trigger_type"),
        trigger.get("kind"),
        trigger.get("type"),
    )
    trigger_label = _TRIGGER_LABELS.get(trigger_type, trigger_type)
    trigger_state = _pick_value(trigger.get("trigger_state"), trigger.get("state"), default="")
    suggested_action = _pick_value(
        trigger.get("suggested_action"),
        trigger.get("action_hint"),
        default="",
    )
    observation = _pick_value(
        trigger.get("observation"),
        trigger.get("condition"),
        default="",
    )

    parts = [f"- {trigger_label}"]
    if trigger_type and trigger_label != trigger_type:
        parts.append(f"（{trigger_type}）")
    details: list[str] = []
    if trigger_state:
        details.append(f"状态 {trigger_state}")
    if suggested_action:
        details.append(f"动作 {suggested_action}")
    if observation:
        details.append(f"观察 {observation}")
    if details:
        parts.append("｜" + "｜".join(details))
    return "".join(parts)


def render_monitor_alert(payload: Mapping[str, Any]) -> str:
    triggers = _normalize_triggers(payload)
    summary = _pick_preferred_text(
        payload.get("summary"),
        payload.get("why_now"),
        payload.get("thesis"),
    )
    why_now = _pick_preferred_text(payload.get("why_now"), payload.get("summary"), default="")
    watch_item = _pick_preferred_text(payload.get("watch_item"), default="")
    suggested_action = _pick_preferred_text(payload.get("suggested_action"), default="")

    lines = ["[监控]", f"结论：{summary}"]
    if why_now and why_now != summary:
        lines.append(f"原因：{why_now}")
    if suggested_action:
        lines.append(f"建议动作：{suggested_action}")
    if triggers:
        lines.append("触发项：")
        lines.extend(_format_trigger(trigger) for trigger in triggers)
    market_link = _as_text(payload.get("market_link"), default="")
    if market_link:
        lines.append(f"市场：{market_link}")
    if watch_item:
        lines.append(f"关注点：{watch_item}")
    return "\n".join(lines)
