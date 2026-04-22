from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

import httpx


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def build_inline_keyboard(
    rows: Iterable[Iterable[tuple[str, str]]],
) -> dict[str, list[list[dict[str, str]]]]:
    keyboard_rows: list[list[dict[str, str]]] = []
    for row in rows:
        keyboard_rows.append(
            [{"text": text, "callback_data": callback_data} for text, callback_data in row]
        )
    return {"inline_keyboard": keyboard_rows}


@dataclass(frozen=True)
class TelegramMessageRef:
    chat_id: str
    message_id: str


class TelegramAPIError(RuntimeError):
    def __init__(
        self,
        *,
        method: str,
        description: str,
        error_code: int | None = None,
        parameters: Mapping[str, Any] | None = None,
    ) -> None:
        self.method = method
        self.description = description
        self.error_code = error_code
        self.parameters = dict(parameters or {})
        detail = f"Telegram API call failed for {method}: {description}"
        if error_code is not None:
            detail = f"{detail} (code={error_code})"
        super().__init__(detail)


TelegramRequestFn = Callable[[str, dict[str, Any]], dict[str, Any] | None]


class TelegramClient:
    def __init__(
        self,
        *,
        bot_token: str | None = None,
        base_url: str = "https://api.telegram.org",
        timeout_seconds: float = 10.0,
        http_client: httpx.Client | None = None,
        request_fn: TelegramRequestFn | None = None,
    ) -> None:
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.disabled = _env_flag("POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM")
        self.base_url = base_url.rstrip("/")
        self._request_fn = request_fn
        self._own_client = request_fn is None and http_client is None
        self._client = (
            None
            if request_fn is not None
            else (http_client or httpx.Client(timeout=timeout_seconds))
        )

    def close(self) -> None:
        if self._own_client and self._client is not None:
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
        message_thread_id: str | None = None,
    ) -> TelegramMessageRef | None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if message_thread_id:
            payload["message_thread_id"] = message_thread_id
        if inline_keyboard:
            payload["reply_markup"] = inline_keyboard
        if parse_mode:
            payload["parse_mode"] = parse_mode
        result = self._request("sendMessage", payload)
        if result is None:
            return None
        chat = result.get("chat")
        chat_from_result = chat.get("id") if isinstance(chat, Mapping) else result.get("chat_id")
        resolved_chat_id = self._optional_text(chat_from_result) or self._optional_text(chat_id)
        resolved_message_id = self._optional_text(result.get("message_id"))
        if not resolved_chat_id or not resolved_message_id:
            return None
        return TelegramMessageRef(chat_id=resolved_chat_id, message_id=resolved_message_id)

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
        try:
            return self._request("editMessageText", payload) is not None
        except TelegramAPIError as exc:
            if self._is_message_not_modified(exc):
                return True
            if self._is_edit_target_unavailable(exc):
                return False
            raise

    def edit_message_ref(
        self,
        *,
        message_ref: TelegramMessageRef,
        text: str,
        inline_keyboard: dict[str, Any] | None = None,
        parse_mode: str | None = None,
    ) -> bool:
        return self.edit_message(
            chat_id=message_ref.chat_id,
            message_id=message_ref.message_id,
            text=text,
            inline_keyboard=inline_keyboard,
            parse_mode=parse_mode,
        )

    def edit_message_reply_markup(
        self,
        *,
        chat_id: str,
        message_id: str,
        inline_keyboard: dict[str, Any] | None = None,
    ) -> bool:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": inline_keyboard
            if inline_keyboard is not None
            else {"inline_keyboard": []},
        }
        try:
            return self._request("editMessageReplyMarkup", payload) is not None
        except TelegramAPIError as exc:
            if self._is_message_not_modified(exc):
                return True
            if self._is_edit_target_unavailable(exc):
                return False
            raise

    def clear_message_keyboard(
        self,
        *,
        chat_id: str,
        message_id: str,
    ) -> bool:
        return self.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            inline_keyboard=None,
        )

    def upsert_message(
        self,
        *,
        chat_id: str,
        text: str,
        message_ref: TelegramMessageRef | None = None,
        inline_keyboard: dict[str, Any] | None = None,
        parse_mode: str | None = None,
        message_thread_id: str | None = None,
    ) -> TelegramMessageRef | None:
        if message_ref is not None:
            edited = self.edit_message_ref(
                message_ref=message_ref,
                text=text,
                inline_keyboard=inline_keyboard,
                parse_mode=parse_mode,
            )
            if edited:
                return message_ref
        return self.send_message(
            chat_id=chat_id,
            text=text,
            inline_keyboard=inline_keyboard,
            parse_mode=parse_mode,
            message_thread_id=message_thread_id,
        )

    def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
        cache_time: int | None = None,
        url: str | None = None,
    ) -> bool:
        payload: dict[str, Any] = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }
        if text:
            payload["text"] = text
        if cache_time is not None:
            payload["cache_time"] = cache_time
        if url:
            payload["url"] = url
        try:
            return self._request("answerCallbackQuery", payload) is not None
        except TelegramAPIError as exc:
            if self._is_callback_query_stale(exc):
                return False
            raise

    def _request(self, method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if self.disabled:
            return None
        if self._request_fn is not None:
            result = self._request_fn(method, payload)
            if result is None:
                return None
            if isinstance(result, Mapping):
                if "ok" in result:
                    if not bool(result.get("ok")):
                        self._raise_api_error(method=method, data=result)
                    payload_result = result.get("result")
                    return payload_result if isinstance(payload_result, dict) else {}
                return dict(result)
            return {}
        if not self.bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required when Telegram delivery is enabled.")
        if self._client is None:
            raise RuntimeError("Telegram HTTP client is not available.")
        try:
            response = self._client.post(
                f"{self.base_url}/bot{self.bot_token}/{method}",
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Telegram transport failure for {method}: {exc}") from exc
        data: Mapping[str, Any] | None
        try:
            decoded = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Telegram API call failed for {method}: non-JSON response (status={response.status_code})"
            ) from exc
        if not isinstance(decoded, Mapping):
            raise RuntimeError(
                f"Telegram API call failed for {method}: invalid payload type {type(decoded).__name__}"
            )
        data = decoded
        if response.status_code >= 400 or not bool(data.get("ok")):
            self._raise_api_error(method=method, data=data)
        result = data.get("result")
        return result if isinstance(result, dict) else {}

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    @staticmethod
    def _contains_phrase(exc: TelegramAPIError, phrase: str) -> bool:
        return phrase.lower() in exc.description.lower()

    @classmethod
    def _is_message_not_modified(cls, exc: TelegramAPIError) -> bool:
        return cls._contains_phrase(exc, "message is not modified")

    @classmethod
    def _is_edit_target_unavailable(cls, exc: TelegramAPIError) -> bool:
        return (
            cls._contains_phrase(exc, "message to edit not found")
            or cls._contains_phrase(exc, "message can't be edited")
            or cls._contains_phrase(exc, "there is no text in the message to edit")
        )

    @classmethod
    def _is_callback_query_stale(cls, exc: TelegramAPIError) -> bool:
        return cls._contains_phrase(exc, "query is too old") or cls._contains_phrase(
            exc, "query id is invalid"
        )

    @staticmethod
    def _raise_api_error(*, method: str, data: Mapping[str, Any]) -> None:
        description = (
            str(data.get("description", "unknown telegram error")).strip()
            or "unknown telegram error"
        )
        error_code_value = data.get("error_code")
        error_code: int | None = None
        if isinstance(error_code_value, int):
            error_code = error_code_value
        parameters = data.get("parameters")
        if not isinstance(parameters, Mapping):
            parameters = {}
        raise TelegramAPIError(
            method=method,
            description=description,
            error_code=error_code,
            parameters=parameters,
        )
