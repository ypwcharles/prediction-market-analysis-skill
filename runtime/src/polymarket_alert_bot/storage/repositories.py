from __future__ import annotations

import sqlite3
from typing import Any


class RuntimeRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert_run(self, payload: dict[str, Any]) -> None:
        columns = sorted(payload)
        assignments = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "id")
        self.conn.execute(
            f"""
            INSERT INTO runs ({", ".join(columns)})
            VALUES ({", ".join("?" for _ in columns)})
            ON CONFLICT(id) DO UPDATE SET {assignments}
            """,
            [payload[column] for column in columns],
        )
        self.conn.commit()

    def insert_alert(self, payload: dict[str, Any]) -> None:
        columns = sorted(payload)
        self.conn.execute(
            f"""
            INSERT INTO alerts ({", ".join(columns)})
            VALUES ({", ".join("?" for _ in columns)})
            """,
            [payload[column] for column in columns],
        )
        self.conn.commit()

    def upsert_thesis_cluster(self, payload: dict[str, Any]) -> None:
        columns = sorted(payload)
        assignments = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "id")
        self.conn.execute(
            f"""
            INSERT INTO thesis_clusters ({", ".join(columns)})
            VALUES ({", ".join("?" for _ in columns)})
            ON CONFLICT(id) DO UPDATE SET {assignments}
            """,
            [payload[column] for column in columns],
        )
        self.conn.commit()

    def upsert_source(self, payload: dict[str, Any]) -> None:
        columns = sorted(payload)
        assignments = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "id")
        self.conn.execute(
            f"""
            INSERT INTO sources ({", ".join(columns)})
            VALUES ({", ".join("?" for _ in columns)})
            ON CONFLICT(id) DO UPDATE SET {assignments}
            """,
            [payload[column] for column in columns],
        )
        self.conn.commit()

    def insert_claim_mapping(self, payload: dict[str, Any]) -> None:
        columns = sorted(payload)
        self.conn.execute(
            f"""
            INSERT INTO claim_source_mappings ({", ".join(columns)})
            VALUES ({", ".join("?" for _ in columns)})
            """,
            [payload[column] for column in columns],
        )
        self.conn.commit()

    def update_trigger_state(self, trigger_id: str, state: str) -> None:
        self.conn.execute(
            """
            UPDATE triggers
            SET state = ?
            WHERE id = ?
            """,
            [state, trigger_id],
        )
        self.conn.commit()

    def replace_positions(self, rows: list[dict[str, Any]]) -> None:
        self.conn.execute("DELETE FROM positions WHERE truth_source = 'official_api'")
        if rows:
            columns = sorted(rows[0])
            self.conn.executemany(
                f"""
                INSERT INTO positions ({", ".join(columns)})
                VALUES ({", ".join("?" for _ in columns)})
                """,
                [[row[column] for column in columns] for row in rows],
            )
        self.conn.commit()
