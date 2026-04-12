"""Create all compliance database tables."""
from __future__ import annotations

from src.database.connection import get_db


_DDL = """
CREATE TABLE IF NOT EXISTS transactions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name        TEXT    NOT NULL,
    client_cpf         TEXT    NOT NULL,
    transaction_type   TEXT    NOT NULL,
    amount             REAL    NOT NULL,
    date               TEXT    NOT NULL,
    branch             TEXT,
    channel            TEXT,
    reported_to_coaf   BOOLEAN DEFAULT FALSE,
    pep_flag           BOOLEAN DEFAULT FALSE,
    notes              TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id   INTEGER,
    alert_type       TEXT NOT NULL,
    severity         TEXT NOT NULL,
    description      TEXT NOT NULL,
    status           TEXT DEFAULT 'open',
    created_at       TEXT NOT NULL,
    resolved_at      TEXT,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id)
);

CREATE TABLE IF NOT EXISTS agent_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    action          TEXT NOT NULL,
    input_summary   TEXT,
    output_summary  TEXT,
    tokens_used     INTEGER
);
"""


def create_tables() -> None:
    """Create all tables if they do not already exist."""
    with get_db() as conn:
        conn.executescript(_DDL)


if __name__ == "__main__":
    create_tables()
    print("Tables created.")
