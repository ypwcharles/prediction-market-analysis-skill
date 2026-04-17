from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Iterable

import httpx


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def build_inline_keyboard(rows: Iterable[Iterable[tuple[str, str]]]) -> dict[str, list[list[dict[str, str]]]]:
    keyboard_rows: list[list[dict[str, str]]] = []
    for row in rows:
        keyboard_rows.append([{"text": text, "callback_data": callback_data} for text, callback_data in row])
    return {"inline_keyboard": keyboard_rows}


@dataclass(frozen=True)
class TelegramMessageRef:
    chat_id: str
    message_id: str


class TelegramClient:
    def __init__(
        self,
        *,
        bot_token: str | None = None,
        base_url: str = "https://api.telegram.org",
        timeout_seconds: float = 10.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.disabled = _env_flag("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM")
        self.base_url = base_url.rstrip("/")
        self._own_client = http_client is None
        self._client = http_client or httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        if self._own_client:
            self._client.close()

    def __enter__(self) -> TelegramClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        inline_keyboard: dict[str, Any] | None = None,
        parse_mode: str | None = None,
    ) -> TelegramMessageRef | None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if inline_keyboard:
            payload["reply_markup"] = inline_keyboard
        if parse_mode:
            payload["parse_mode"] = parse_mode
        result = self._request("sendMessage", payload)
        if result is None:
            return None
        return TelegramMessageRef(chat_id=str(result["chat"]["id"]), message_id=str(result["message_id"]))

    def edit_message(
        self,
        *,
        chat_id: str,
        message_id: str,
        text: str,
        inline_keyboard: dict[str, Any] | None = None,
        parse_mode: str | None = None,
    ) -> bool:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if inline_keyboard:
            payload["reply_markup"] = inline_keyboard
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return self._request("editMessageText", payload) is not None

    def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> bool:
        payload: dict[str, Any] = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }
        if text:
            payload["text"] = text
        return self._request("answerCallbackQuery", payload) is not None

    def _request(self, method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if self.disabled:
            return None
        if not self.bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required when Telegram delivery is enabled.")
        response = self._client.post(
            f"{self.base_url}/bot{self.bot_token}/{method}",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API call failed for {method}: {data}")
        result = data.get("result")
        return result if isinstance(result, dict) else {}
