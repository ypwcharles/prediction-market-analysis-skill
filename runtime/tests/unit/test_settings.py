from __future__ import annotations

from polymarket_alert_bot.config.settings import load_runtime_config


def test_load_runtime_config_uses_real_hermes_safe_timeout_default(monkeypatch) -> None:
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_JUDGMENT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_TELEGRAM_MESSAGE_THREAD_ID", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_ENABLED", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_MAX_ITEMS", raising=False)
    monkeypatch.delenv("POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_RUNNER_CMD", raising=False)

    config = load_runtime_config()

    assert config.judgment_timeout_seconds == 600
    assert config.scan_max_judgment_candidates == 2
    assert config.telegram_message_thread_id is None
    assert config.semantic_relevance_enabled is False
    assert config.semantic_relevance_timeout_seconds == 60
    assert config.semantic_relevance_max_items == 12
    assert config.semantic_relevance_command == ()


def test_load_runtime_config_allows_timeout_override(monkeypatch) -> None:
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_JUDGMENT_TIMEOUT_SECONDS", "420")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES", "7")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_TELEGRAM_MESSAGE_THREAD_ID", "8369")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_ENABLED", "true")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_MAX_ITEMS", "5")
    monkeypatch.setenv(
        "POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_RUNNER_CMD",
        "python -c import json,sys;json.dump({},sys.stdout)",
    )

    config = load_runtime_config()

    assert config.judgment_timeout_seconds == 420
    assert config.scan_max_judgment_candidates == 7
    assert config.telegram_message_thread_id == "8369"
    assert config.semantic_relevance_enabled is True
    assert config.semantic_relevance_timeout_seconds == 45
    assert config.semantic_relevance_max_items == 5
    assert config.semantic_relevance_command[:2] == ("python", "-c")
