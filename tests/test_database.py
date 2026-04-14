"""Tests for database setup and connection."""
import sqlite3

import pytest

from src.database.connection import get_db
from src.database.setup import create_tables


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Redirect all DB operations to a temp path."""
    import src.database.connection as conn_mod
    monkeypatch.setattr(conn_mod.settings, "db_path", str(tmp_path / "test.db"))
    yield str(tmp_path / "test.db")


def test_get_db_yields_connection(tmp_db):
    with get_db() as conn:
        assert isinstance(conn, sqlite3.Connection)


def test_create_tables_creates_recruitment_tables(tmp_db):
    create_tables()
    with get_db() as conn:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert {"candidates", "job_postings", "matches", "pipeline"} <= tables


def test_create_tables_keeps_auth_and_governance_tables(tmp_db):
    create_tables()
    with get_db() as conn:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert {"users", "conversations", "messages", "audit_log", "governance_daily_stats"} <= tables


def test_create_tables_does_not_create_compliance_tables(tmp_db):
    create_tables()
    with get_db() as conn:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert "transactions" not in tables
    assert "alerts" not in tables
    assert "agent_log" not in tables


def test_get_db_commits_on_success(tmp_db):
    create_tables()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO candidates (full_name, resume_filename, created_at) VALUES (?, ?, ?)",
            ("Test User", "test.pdf", "2026-01-01T10:00:00"),
        )
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    assert count == 1


def test_get_db_rolls_back_on_exception(tmp_db):
    create_tables()
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO candidates (full_name, resume_filename, created_at) VALUES (?, ?, ?)",
                ("Test User", "test.pdf", "2026-01-01T10:00:00"),
            )
            raise ValueError("forced error")
    except ValueError:
        pass
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    assert count == 0


def test_row_factory_is_set(tmp_db):
    with get_db() as conn:
        assert conn.row_factory == sqlite3.Row


from src.database.seed import init_db


def test_seed_inserts_20_candidates(tmp_db):
    init_db()
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    assert count == 20


def test_seed_inserts_2_job_postings(tmp_db):
    init_db()
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0]
    assert count == 2


def test_seed_inserts_matches(tmp_db):
    init_db()
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    assert count == 40


def test_seed_inserts_pipeline_entries(tmp_db):
    init_db()
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM pipeline").fetchone()[0]
    assert count == 20


def test_seed_is_idempotent(tmp_db):
    init_db()
    init_db()
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    assert count == 20


def test_seed_users_creates_analyst_and_manager(tmp_db):
    init_db()
    with get_db() as conn:
        users = {r["username"] for r in conn.execute("SELECT username FROM users").fetchall()}
    assert "analyst" in users
    assert "manager" in users


def test_top_candidates_have_high_scores(tmp_db):
    init_db()
    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM matches WHERE overall_score >= 0.85"
        ).fetchone()[0]
    assert count >= 5


def test_pipeline_has_approved_candidates(tmp_db):
    init_db()
    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM pipeline WHERE stage = 'aprovado'"
        ).fetchone()[0]
    assert count >= 1
