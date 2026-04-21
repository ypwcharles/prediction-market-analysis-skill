from __future__ import annotations

from polymarket_alert_bot.config.settings import load_runtime_config


def test_load_runtime_config_uses_real_hermes_safe_timeout_default(monkeypatch) -> None:
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_JUDGMENT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES", raising=False)

    config = load_runtime_config()

    assert config.judgment_timeout_seconds == 600
    assert config.scan_max_judgment_candidates == 2


def test_load_runtime_config_allows_timeout_override(monkeypatch) -> None:
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_JUDGMENT_TIMEOUT_SECONDS", "420")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES", "7")

    config = load_runtime_config()

    assert config.judgment_timeout_seconds == 420
    assert config.scan_max_judgment_candidates == 7
