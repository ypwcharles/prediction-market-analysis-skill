from __future__ import annotations

from fastapi import HTTPException, Request, status

from polymarket_alert_bot.config.settings import RuntimeConfig

TELEGRAM_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


def require_internal_bearer(request: Request, config: RuntimeConfig) -> None:
    expected = config.service_bearer_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="service bearer token is not configured",
        )
    authorization = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    provided = authorization[len(prefix) :].strip()
    if provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid bearer token",
        )


def require_telegram_webhook_secret(request: Request, config: RuntimeConfig) -> None:
    expected = config.telegram_webhook_secret
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="telegram webhook secret is not configured",
        )
    provided = request.headers.get(TELEGRAM_SECRET_HEADER, "").strip()
    if provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid telegram webhook secret",
        )
