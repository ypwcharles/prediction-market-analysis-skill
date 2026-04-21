from __future__ import annotations

import sqlite3


def apply_migrations(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            run_type TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            degraded_reason TEXT,
            scanned_events INTEGER DEFAULT 0,
            scanned_contracts INTEGER DEFAULT 0,
            strict_count INTEGER DEFAULT 0,
            research_count INTEGER DEFAULT 0,
            skipped_count INTEGER DEFAULT 0,
            heartbeat_sent INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS thesis_clusters (
            id TEXT PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            status TEXT NOT NULL,
            cluster_version INTEGER NOT NULL DEFAULT 1,
            cluster_reason TEXT,
            closed_reason TEXT,
            closed_at TEXT,
            reopen_reason TEXT,
            last_alert_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS cluster_expressions (
            id TEXT PRIMARY KEY,
            thesis_cluster_id TEXT NOT NULL,
            condition_id TEXT,
            event_id TEXT,
            market_id TEXT,
            token_id TEXT,
            event_slug TEXT,
            market_slug TEXT,
            expression_label TEXT,
            is_primary_expression INTEGER DEFAULT 0,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            FOREIGN KEY (thesis_cluster_id) REFERENCES thesis_clusters(id)
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            thesis_cluster_id TEXT,
            condition_id TEXT,
            event_id TEXT,
            market_id TEXT,
            token_id TEXT,
            alert_kind TEXT NOT NULL,
            delivery_mode TEXT NOT NULL,
            side TEXT,
            theoretical_edge_cents REAL,
            executable_edge_cents REAL,
            spread_bps REAL,
            slippage_bps REAL,
            max_entry_cents REAL,
            suggested_size_usdc REAL,
            why_now TEXT,
            kill_criteria_text TEXT,
            evidence_fresh_until TEXT,
            recheck_required_at TEXT,
            status TEXT NOT NULL,
            telegram_chat_id TEXT,
            telegram_message_id TEXT,
            archive_path TEXT,
            dedupe_key TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(id),
            FOREIGN KEY (thesis_cluster_id) REFERENCES thesis_clusters(id)
        );

        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY,
            source_name TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            source_tier TEXT NOT NULL,
            domain_or_handle TEXT NOT NULL,
            is_primary_allowed INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            config_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS claim_source_mappings (
            id TEXT PRIMARY KEY,
            alert_id TEXT NOT NULL,
            thesis_cluster_id TEXT NOT NULL,
            claim_type TEXT NOT NULL,
            claim_text TEXT NOT NULL,
            source_id TEXT NOT NULL,
            url TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            conflict_status TEXT NOT NULL DEFAULT 'active',
            superseded_by_mapping_id TEXT,
            FOREIGN KEY (alert_id) REFERENCES alerts(id),
            FOREIGN KEY (thesis_cluster_id) REFERENCES thesis_clusters(id),
            FOREIGN KEY (source_id) REFERENCES sources(id),
            FOREIGN KEY (superseded_by_mapping_id) REFERENCES claim_source_mappings(id)
        );

        CREATE TABLE IF NOT EXISTS triggers (
            id TEXT PRIMARY KEY,
            thesis_cluster_id TEXT NOT NULL,
            alert_id TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            threshold_kind TEXT NOT NULL,
            comparison TEXT NOT NULL,
            threshold_value TEXT NOT NULL,
            suggested_action TEXT NOT NULL,
            requires_llm_recheck INTEGER NOT NULL DEFAULT 0,
            human_note TEXT,
            state TEXT NOT NULL,
            cooldown_until TEXT,
            last_fired_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (thesis_cluster_id) REFERENCES thesis_clusters(id),
            FOREIGN KEY (alert_id) REFERENCES alerts(id)
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            alert_id TEXT NOT NULL,
            thesis_cluster_id TEXT NOT NULL,
            feedback_type TEXT NOT NULL,
            payload_json TEXT,
            telegram_chat_id TEXT,
            telegram_message_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (alert_id) REFERENCES alerts(id),
            FOREIGN KEY (thesis_cluster_id) REFERENCES thesis_clusters(id)
        );

        CREATE TABLE IF NOT EXISTS positions (
            id TEXT PRIMARY KEY,
            condition_id TEXT NOT NULL,
            token_id TEXT NOT NULL,
            market_id TEXT,
            thesis_cluster_id TEXT,
            side TEXT NOT NULL,
            size_shares REAL NOT NULL,
            avg_entry_cents REAL,
            status TEXT NOT NULL,
            truth_source TEXT NOT NULL,
            snapshot_as_of TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (thesis_cluster_id) REFERENCES thesis_clusters(id)
        );

        CREATE TABLE IF NOT EXISTS calibration_reports (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            status TEXT NOT NULL,
            total_high_priority_alerts INTEGER NOT NULL,
            distinct_clusters INTEGER NOT NULL,
            repeated_cluster_discount INTEGER NOT NULL,
            report_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );
        """
    )
    _ensure_column(conn, "cluster_expressions", "condition_id", "TEXT")
    _ensure_column(conn, "alerts", "condition_id", "TEXT")
    _dedupe_alert_rows(conn)
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS alerts_dedupe_key_unique
        ON alerts(dedupe_key)
        """
    )
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
    columns = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name in columns:
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _dedupe_alert_rows(conn: sqlite3.Connection) -> None:
    duplicate_keys = conn.execute(
        """
        SELECT dedupe_key
        FROM alerts
        GROUP BY dedupe_key
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    for row in duplicate_keys:
        dedupe_key = row[0]
        alert_rows = conn.execute(
            """
            SELECT id
            FROM alerts
            WHERE dedupe_key = ?
            ORDER BY created_at DESC, rowid DESC
            """,
            [dedupe_key],
        ).fetchall()
        keep_id = alert_rows[0][0]
        duplicate_ids = [alert_row[0] for alert_row in alert_rows[1:]]
        if not duplicate_ids:
            continue
        placeholders = ", ".join("?" for _ in duplicate_ids)
        for table_name in ("claim_source_mappings", "triggers", "feedback"):
            conn.execute(
                f"""
                UPDATE {table_name}
                SET alert_id = ?
                WHERE alert_id IN ({placeholders})
                """,
                [keep_id, *duplicate_ids],
            )
        conn.execute(
            f"""
            UPDATE thesis_clusters
            SET last_alert_id = ?
            WHERE last_alert_id IN ({placeholders})
            """,
            [keep_id, *duplicate_ids],
        )
        conn.execute(
            f"""
            DELETE FROM alerts
            WHERE id IN ({placeholders})
            """,
            duplicate_ids,
        )
