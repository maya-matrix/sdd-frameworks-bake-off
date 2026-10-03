import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Group:
    id: str
    name: str
    currency: str
    created_at: str


@dataclass(frozen=True)
class Member:
    id: str
    group_id: str
    name: str
    join_order: int
    departed_at: str | None


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Repository:
    """All SQL lives here. Callers own the transaction via the connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def insert_group(self, name: str, currency: str) -> Group:
        group = Group(id=_new_id(), name=name, currency=currency, created_at=_now())
        self.conn.execute(
            "INSERT INTO groups (id, name, currency, created_at) VALUES (?, ?, ?, ?)",
            (group.id, group.name, group.currency, group.created_at),
        )
        return group

    def get_group(self, group_id: str) -> Group | None:
        row = self.conn.execute(
            "SELECT id, name, currency, created_at FROM groups WHERE id = ?", (group_id,)
        ).fetchone()
        return Group(**row) if row else None

    def insert_member(self, group_id: str, name: str) -> Member:
        (next_order,) = self.conn.execute(
            "SELECT COALESCE(MAX(join_order), 0) + 1 FROM members WHERE group_id = ?",
            (group_id,),
        ).fetchone()
        member = Member(
            id=_new_id(), group_id=group_id, name=name, join_order=next_order, departed_at=None
        )
        self.conn.execute(
            "INSERT INTO members (id, group_id, name, join_order, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (member.id, group_id, name, next_order, _now()),
        )
        return member

    def list_members(self, group_id: str) -> list[Member]:
        """All Members of the Group, including Departed Members, in join order."""
        rows = self.conn.execute(
            "SELECT id, group_id, name, join_order, departed_at FROM members"
            " WHERE group_id = ? ORDER BY join_order",
            (group_id,),
        ).fetchall()
        return [Member(**row) for row in rows]
