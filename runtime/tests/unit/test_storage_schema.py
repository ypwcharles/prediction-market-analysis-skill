from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations


def test_schema_creates_expected_tables(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    conn = connect_db(db_path)
    apply_migrations(conn)
    rows = conn.execute(
        "select name from sqlite_master where type='table'"
    ).fetchall()
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
