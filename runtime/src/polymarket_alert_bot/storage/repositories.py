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
        assignments = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "id")
        self.conn.execute(
            f"""
            INSERT INTO alerts ({", ".join(columns)})
            VALUES ({", ".join("?" for _ in columns)})
            ON CONFLICT(id) DO UPDATE SET {assignments}
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

    def upsert_cluster_expression(self, payload: dict[str, Any]) -> None:
        columns = sorted(payload)
        assignments = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "id")
        self.conn.execute(
            f"""
            INSERT INTO cluster_expressions ({", ".join(columns)})
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

    def insert_feedback(self, payload: dict[str, Any]) -> None:
        columns = sorted(payload)
        self.conn.execute(
            f"""
            INSERT INTO feedback ({", ".join(columns)})
            VALUES ({", ".join("?" for _ in columns)})
            """,
            [payload[column] for column in columns],
        )
        self.conn.commit()

    def insert_triggers(self, payloads: list[dict[str, Any]]) -> None:
        if not payloads:
            return
        columns = sorted(payloads[0])
        self.conn.executemany(
            f"""
            INSERT INTO triggers ({", ".join(columns)})
            VALUES ({", ".join("?" for _ in columns)})
            """,
            [[payload[column] for column in columns] for payload in payloads],
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

    def update_alert_delivery(
        self,
        *,
        alert_id: str,
        telegram_chat_id: str | None = None,
        telegram_message_id: str | None = None,
        archive_path: str | None = None,
        status: str | None = None,
    ) -> None:
        assignments: list[str] = []
        values: list[Any] = []
        if telegram_chat_id is not None:
            assignments.append("telegram_chat_id = ?")
            values.append(telegram_chat_id)
        if telegram_message_id is not None:
            assignments.append("telegram_message_id = ?")
            values.append(telegram_message_id)
        if archive_path is not None:
            assignments.append("archive_path = ?")
            values.append(archive_path)
        if status is not None:
            assignments.append("status = ?")
            values.append(status)
        if not assignments:
            return
        values.append(alert_id)
        self.conn.execute(
            f"""
            UPDATE alerts
            SET {", ".join(assignments)}
            WHERE id = ?
            """,
            values,
        )
        self.conn.commit()

    def update_alert(self, *, alert_id: str, payload: dict[str, Any]) -> None:
        if not payload:
            return
        assignments = ", ".join(f"{column} = ?" for column in sorted(payload))
        values = [payload[column] for column in sorted(payload)]
        values.append(alert_id)
        self.conn.execute(
            f"""
            UPDATE alerts
            SET {assignments}
            WHERE id = ?
            """,
            values,
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

    def get_alert(self, alert_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT *
            FROM alerts
            WHERE id = ?
            """,
            [alert_id],
        ).fetchone()

    def list_active_alerts(self, *, alert_kinds: tuple[str, ...] | None = None) -> list[sqlite3.Row]:
        query = """
            SELECT *
            FROM alerts
            WHERE status = 'active'
        """
        params: list[Any] = []
        if alert_kinds:
            query += f" AND alert_kind IN ({', '.join('?' for _ in alert_kinds)})"
            params.extend(alert_kinds)
        return self.conn.execute(query, params).fetchall()

    def list_triggers(self, *, states: tuple[str, ...] | None = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM triggers"
        params: list[Any] = []
        if states:
            query += f" WHERE state IN ({', '.join('?' for _ in states)})"
            params.extend(states)
        return self.conn.execute(query, params).fetchall()
