from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations


def test_schema_creates_expected_tables(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    conn = connect_db(db_path)
    apply_migrations(conn)
    rows = conn.execute("select name from sqlite_master where type='table'").fetchall()
    names = {row[0] for row in rows}
    assert {
        "runs",
        "alerts",
        "thesis_clusters",
        "cluster_expressions",
        "triggers",
        "feedback",
        "positions",
        "sources",
        "claim_source_mappings",
    } <= names


def test_schema_includes_runtime_reconciliation_columns(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    conn = connect_db(db_path)
    apply_migrations(conn)

    alert_columns = {row["name"] for row in conn.execute("PRAGMA table_info(alerts)").fetchall()}
    expression_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(cluster_expressions)").fetchall()
    }
    feedback_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(feedback)").fetchall()
    }

    assert {"condition_id", "market_id", "token_id"} <= alert_columns
    assert {"condition_id", "market_id", "token_id"} <= expression_columns
    assert {"payload_json", "telegram_chat_id", "telegram_message_id"} <= feedback_columns


def test_schema_enforces_unique_alert_dedupe_keys(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    conn = connect_db(db_path)
    apply_migrations(conn)

    indexes = {
        row["name"]: row["unique"] for row in conn.execute("PRAGMA index_list(alerts)").fetchall()
    }

    assert indexes["alerts_dedupe_key_unique"] == 1
