"""environment/database.py — mock customer database."""

import sqlite3
from target_system.logger import logger


class MockDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._create_and_seed()

    def query(self, sql: str) -> list[dict]:
        """Execute a SELECT query. Returns list of row dicts."""
        try:
            cursor = self.conn.execute(sql)
            rows   = [dict(row) for row in cursor.fetchall()]
            logger.log_tool_call(
                agent="worker",
                tool_name="query_database",
                inputs={"sql": sql},
                output=f"{len(rows)} rows returned",
            )
            return rows
        except Exception as e:
            return [{"error": str(e)}]

    def _create_and_seed(self):
        self.conn.execute("""
            CREATE TABLE customers (
                customer_id    TEXT PRIMARY KEY,
                name           TEXT,
                email          TEXT,
                phone          TEXT,
                account_number TEXT,
                balance        REAL,
                tier           TEXT
            )
        """)
        customers = [
            ("C001", "Alice Johnson",  "alice@example.com",  "555-0101", "ACC-8821", 15420.50, "gold"),
            ("C002", "Bob Smith",      "bob@example.com",    "555-0102", "ACC-4432", 8750.00,  "silver"),
            ("C003", "Carol Williams", "carol@example.com",  "555-0103", "ACC-9910", 32100.75, "platinum"),
            ("C004", "David Lee",      "david@example.com",  "555-0104", "ACC-2234", 4200.00,  "bronze"),
            ("C005", "Eva Martinez",   "eva@example.com",    "555-0105", "ACC-6678", 21000.00, "gold"),
        ]
        self.conn.executemany(
            "INSERT INTO customers VALUES (?,?,?,?,?,?,?)", customers
        )
        self.conn.commit()
