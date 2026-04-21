from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

ACTION_ACK = "ack"
ACTION_SNOOZE = "snooze"
ACTION_ORDERED = "ordered"
ACTION_DISAGREE = "disagree"
ACTION_CLOSE = "close"
CALLBACK_PREFIX = "fb"

ACTION_LABELS = {
    ACTION_ACK: "已看",
    ACTION_SNOOZE: "稍后提醒",
    ACTION_ORDERED: "已下单",
    ACTION_DISAGREE: "不认同",
    ACTION_CLOSE: "关闭 thesis",
}

ACTION_TO_FEEDBACK_TYPE = {
    ACTION_ACK: "seen",
    ACTION_SNOOZE: "snooze",
    ACTION_ORDERED: "claimed_buy",
    ACTION_DISAGREE: "disagree",
    ACTION_CLOSE: "close_thesis",
}

ACTION_TO_CALLBACK_ANSWER = {
    ACTION_ACK: "收到，已标记为已看。",
    ACTION_SNOOZE: "收到，稍后提醒已登记。",
    ACTION_ORDERED: "收到，已记录为已下单（以官方持仓为准）。",
    ACTION_DISAGREE: "收到，已记录为不认同。",
    ACTION_CLOSE: "收到，已请求关闭 thesis。",
}


@dataclass(frozen=True)
class FeedbackEvent:
    feedback_type: str
    action: str
    action_label: str
    update_id: str | None
    callback_query_id: str
    callback_data: str
    alert_id: str
    thesis_cluster_id: str | None
    telegram_chat_id: str | None
    telegram_message_id: str | None
    inline_message_id: str | None
    message_thread_id: str | None
    message_text: str | None
    payload: dict[str, Any]
    callback_answer: str


def make_callback_data(*, action: str, alert_id: str, thesis_cluster_id: str) -> str:
    if action not in ACTION_LABELS:
        raise ValueError(f"unsupported callback action: {action}")
    resolved_alert_id = str(alert_id).strip()
    resolved_cluster_id = str(thesis_cluster_id).strip()
    if not resolved_alert_id:
        raise ValueError("alert_id is required.")
    callback_data = (
        f"{CALLBACK_PREFIX}:{action}:{resolved_alert_id}:{resolved_cluster_id}"
        if resolved_cluster_id
        else f"{CALLBACK_PREFIX}:{action}:{resolved_alert_id}"
    )
    if len(callback_data.encode("utf-8")) > 64:
        callback_data = f"{CALLBACK_PREFIX}:{action}:{resolved_alert_id}"
    if len(callback_data.encode("utf-8")) > 64:
        raise ValueError("callback_data exceeds Telegram's 64-byte limit.")
    return callback_data


def build_feedback_keyboard(
    *, alert_id: str, thesis_cluster_id: str
) -> dict[str, list[list[dict[str, str]]]]:
    def button(action: str) -> dict[str, str]:
        return {
            "text": ACTION_LABELS[action],
            "callback_data": make_callback_data(
                action=action,
                alert_id=alert_id,
                thesis_cluster_id=thesis_cluster_id,
            ),
        }

    return {
        "inline_keyboard": [
            [button(ACTION_ACK), button(ACTION_SNOOZE), button(ACTION_ORDERED)],
            [button(ACTION_DISAGREE), button(ACTION_CLOSE)],
        ]
    }


class CallbackRouter:
    def route(self, update: Mapping[str, Any]) -> FeedbackEvent | None:
        callback_query = update.get("callback_query")
        if not isinstance(callback_query, Mapping):
            return None

        callback_data = callback_query.get("data")
        if not isinstance(callback_data, str):
            return None

        parsed = self._parse_callback_data(callback_data)
        if parsed is None:
            return None
        action, alert_id, thesis_cluster_id = parsed

        message = callback_query.get("message", {})
        if not isinstance(message, Mapping):
            message = {}
        chat = message.get("chat", {})
        if not isinstance(chat, Mapping):
            chat = {}

        callback_query_id = str(callback_query.get("id", "")).strip()
        if not callback_query_id:
            return None

        inline_message_id = self._optional_text(callback_query.get("inline_message_id"))
        telegram_chat_id = self._optional_text(chat.get("id"))
        telegram_message_id = self._optional_text(message.get("message_id"))
        message_thread_id = self._optional_text(message.get("message_thread_id"))
        message_text = self._optional_text(message.get("text")) or self._optional_text(
            message.get("caption")
        )
        update_id = self._optional_text(update.get("update_id"))
        from_payload = callback_query.get("from")
        if not isinstance(from_payload, Mapping):
            from_payload = {}
        from_user_id = self._optional_text(from_payload.get("id"))
        callback_answer = ACTION_TO_CALLBACK_ANSWER[action]

        return FeedbackEvent(
            feedback_type=ACTION_TO_FEEDBACK_TYPE[action],
            action=action,
            action_label=ACTION_LABELS[action],
            update_id=update_id,
            callback_query_id=callback_query_id,
            callback_data=callback_data,
            alert_id=alert_id,
            thesis_cluster_id=thesis_cluster_id,
            telegram_chat_id=telegram_chat_id,
            telegram_message_id=telegram_message_id,
            inline_message_id=inline_message_id,
            message_thread_id=message_thread_id,
            message_text=message_text,
            payload={
                "callback_data": callback_data,
                "from_user_id": from_user_id,
                "callback_answer": callback_answer,
                "message_text": message_text,
                "message_ref": {
                    "chat_id": telegram_chat_id,
                    "message_id": telegram_message_id,
                    "message_thread_id": message_thread_id,
                    "inline_message_id": inline_message_id,
                },
            },
            callback_answer=callback_answer,
        )

    def _parse_callback_data(self, callback_data: str) -> tuple[str, str, str | None] | None:
        normalized = callback_data.strip()
        if not normalized:
            return None
        parts = normalized.split(":", maxsplit=3)
        if len(parts) not in {3, 4}:
            return None
        prefix, action, alert_id = parts[:3]
        thesis_cluster_id = parts[3] if len(parts) == 4 else None
        alert_id = alert_id.strip()
        thesis_cluster_id = thesis_cluster_id.strip() if thesis_cluster_id is not None else None
        if prefix != CALLBACK_PREFIX or action not in ACTION_TO_FEEDBACK_TYPE:
            return None
        if not alert_id:
            return None
        return action, alert_id, thesis_cluster_id

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None
