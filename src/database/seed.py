"""Database initialisation for TechHire AI.

Seeds only the default users (analyst + manager). Candidates, job postings,
matches, and pipeline entries are created exclusively via PDF upload through
the dashboard — there is no sample/seed data for those tables.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.database.connection import get_db
from src.database.setup import create_tables


def seed_users() -> None:
    """Insert default analyst and manager users if the users table is empty."""
    from src.api.auth import hash_password

    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            "INSERT INTO users (username, password_hash, full_name, role, created_at)"
            " VALUES (?,?,?,?,?)",
            [
                ("analyst", hash_password("analyst123"), "Ana Recrutadora",     "analyst", now),
                ("manager", hash_password("manager123"), "Marcos Gestor de RH", "manager", now),
            ],
        )
    print("=" * 60)
    print("  DEFAULT USERS: analyst/analyst123, manager/manager123")
    print("=" * 60)


def init_db() -> None:
    """Create tables and seed default users. Idempotent."""
    create_tables()
    seed_users()


if __name__ == "__main__":
    init_db()
