from polymarket_alert_bot.config.source_registry import load_source_registry


def test_load_source_registry_marks_primary_sources():
    registry = load_source_registry("runtime/config/sources.toml")
    assert "reuters.com" in registry.primary_domains
    assert "@polymarket" in registry.x_handles
