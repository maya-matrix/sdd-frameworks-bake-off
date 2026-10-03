import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
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
    join_order INTEGER NOT NULL,
    departed_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (group_id, join_order)
);
CREATE UNIQUE INDEX IF NOT EXISTS members_group_name
    ON members (group_id, name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL REFERENCES groups(id),
    payer_id TEXT NOT NULL REFERENCES members(id),
    amount INTEGER NOT NULL CHECK (amount > 0),
    description TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS expense_participants (
    expense_id TEXT NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    member_id TEXT NOT NULL REFERENCES members(id),
    PRIMARY KEY (expense_id, member_id)
);

CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL REFERENCES groups(id),
    from_id TEXT NOT NULL REFERENCES members(id),
    to_id TEXT NOT NULL REFERENCES members(id),
    amount INTEGER NOT NULL CHECK (amount > 0),
    created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        conn = sqlite3.connect(self.path)
        try:
            conn.executescript(SCHEMA)
        finally:
            conn.close()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """One connection per unit of work; commits on success, rolls back on error.

        The transaction takes SQLite's write lock up front (BEGIN IMMEDIATE), so units
        of work are serialised and check-then-insert rules (unique Member names, join
        order) cannot race. Concurrent callers wait for the lock up to `timeout`.
        """
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
        finally:
            conn.close()
