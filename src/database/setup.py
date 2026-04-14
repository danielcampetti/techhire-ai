"""Create all TechHire AI database tables."""
from __future__ import annotations

from src.database.connection import get_db


_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    full_name     TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'analyst',
    created_at    TEXT    NOT NULL,
    last_login    TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS job_postings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title          TEXT    NOT NULL,
    company        TEXT,
    description    TEXT    NOT NULL,
    requirements   TEXT,
    desired_skills TEXT,
    seniority_level TEXT,
    work_model     TEXT,
    salary_range   TEXT,
    created_by     INTEGER,
    created_at     TEXT    NOT NULL,
    is_active      BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS candidates (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name        TEXT    NOT NULL,
    email            TEXT,
    phone            TEXT,
    cpf              TEXT,
    location         TEXT,
    current_role     TEXT,
    experience_years INTEGER,
    education        TEXT,
    skills           TEXT,
    resume_filename  TEXT    NOT NULL,
    resume_text      TEXT,
    created_at       TEXT    NOT NULL,
    is_active        BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS matches (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id     INTEGER NOT NULL,
    job_posting_id   INTEGER NOT NULL,
    overall_score    REAL    NOT NULL,
    skills_score     REAL,
    experience_score REAL,
    education_score  REAL,
    semantic_score   REAL,
    analysis         TEXT,
    created_at       TEXT    NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id),
    FOREIGN KEY (job_posting_id) REFERENCES job_postings(id)
);

CREATE TABLE IF NOT EXISTS pipeline (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id     INTEGER NOT NULL,
    job_posting_id   INTEGER NOT NULL,
    stage            TEXT    NOT NULL DEFAULT 'triagem',
    notes            TEXT,
    updated_by       INTEGER,
    updated_at       TEXT    NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id),
    FOREIGN KEY (job_posting_id) REFERENCES job_postings(id),
    FOREIGN KEY (updated_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    title      TEXT    NOT NULL DEFAULT 'Nova conversa',
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id     INTEGER NOT NULL,
    role                TEXT    NOT NULL,
    content             TEXT    NOT NULL,
    agent_used          TEXT,
    provider            TEXT,
    data_classification TEXT,
    pii_detected        BOOLEAN DEFAULT FALSE,
    timestamp           TEXT    NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, timestamp ASC);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS audit_log (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id           TEXT    NOT NULL,
    timestamp            TEXT    NOT NULL,
    agent_name           TEXT    NOT NULL,
    action               TEXT    NOT NULL,
    input_original       TEXT,
    input_masked         TEXT,
    output_original      TEXT,
    output_masked        TEXT,
    input_has_pii        BOOLEAN NOT NULL DEFAULT FALSE,
    output_has_pii       BOOLEAN NOT NULL DEFAULT FALSE,
    pii_types_detected   TEXT,
    data_classification  TEXT    NOT NULL,
    provider             TEXT    NOT NULL,
    model                TEXT    NOT NULL,
    tokens_used          INTEGER NOT NULL DEFAULT 0,
    chunks_count         INTEGER NOT NULL DEFAULT 0,
    retention_expires_at TEXT    NOT NULL,
    pii_purged           BOOLEAN NOT NULL DEFAULT FALSE,
    user_id              INTEGER,
    username             TEXT
);

CREATE TABLE IF NOT EXISTS governance_daily_stats (
    date                        TEXT    PRIMARY KEY,
    total_queries               INTEGER NOT NULL DEFAULT 0,
    queries_with_pii            INTEGER NOT NULL DEFAULT 0,
    classification_public       INTEGER NOT NULL DEFAULT 0,
    classification_internal     INTEGER NOT NULL DEFAULT 0,
    classification_confidential INTEGER NOT NULL DEFAULT 0,
    classification_restricted   INTEGER NOT NULL DEFAULT 0,
    pii_cpf_count               INTEGER NOT NULL DEFAULT 0,
    pii_name_count              INTEGER NOT NULL DEFAULT 0,
    pii_money_count             INTEGER NOT NULL DEFAULT 0
)
"""


def create_tables() -> None:
    """Create all tables if they do not already exist."""
    with get_db() as conn:
        for statement in _DDL.strip().split(";"):
            s = statement.strip()
            if s:
                conn.execute(s)


if __name__ == "__main__":
    create_tables()
    print("Tables created.")
