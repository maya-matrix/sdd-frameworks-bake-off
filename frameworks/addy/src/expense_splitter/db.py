"""SQLite connection setup and schema. All money columns hold integer cents."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    currency TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS members (
    id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL REFERENCES groups(id),
    name TEXT NOT NULL,
    position INTEGER NOT NULL,
    UNIQUE (group_id, name COLLATE NOCASE)
);
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL REFERENCES groups(id),
    payer_id TEXT NOT NULL REFERENCES members(id),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    description TEXT NOT NULL,
    split_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS expense_shares (
    expense_id TEXT NOT NULL REFERENCES expenses(id),
    member_id TEXT NOT NULL REFERENCES members(id),
    position INTEGER NOT NULL,
    amount_cents INTEGER NOT NULL,
    PRIMARY KEY (expense_id, member_id)
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    # FastAPI may run a request's dependency and handler on different worker threads.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
