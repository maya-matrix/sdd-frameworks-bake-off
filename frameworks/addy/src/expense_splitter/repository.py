"""Persistence for groups, members and expenses. Parameterized SQL only."""

import sqlite3
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from expense_splitter.money import Cents
from expense_splitter.split import Share


class DuplicateMemberError(Exception):
    pass


@dataclass(frozen=True)
class Group:
    id: str
    name: str
    currency: str


@dataclass(frozen=True)
class Member:
    id: str
    name: str


@dataclass(frozen=True)
class Expense:
    id: str
    payer_id: str
    amount_cents: Cents
    description: str
    split_type: str
    shares: list[Share]
    created_at: str


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def create_group(conn: sqlite3.Connection, name: str, currency: str) -> Group:
    group = Group(id=_new_id(), name=name, currency=currency)
    with conn:
        conn.execute(
            "INSERT INTO groups (id, name, currency, created_at) VALUES (?, ?, ?, ?)",
            (group.id, group.name, group.currency, _now()),
        )
    return group


def get_group(conn: sqlite3.Connection, group_id: str) -> Group | None:
    row = conn.execute("SELECT id, name, currency FROM groups WHERE id = ?", (group_id,)).fetchone()
    return Group(row["id"], row["name"], row["currency"]) if row else None


def add_member(conn: sqlite3.Connection, group_id: str, name: str) -> Member:
    member = Member(id=_new_id(), name=name)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO members (id, group_id, name, position)
                SELECT ?, ?, ?, COALESCE(MAX(position), 0) + 1 FROM members WHERE group_id = ?
                """,
                (member.id, group_id, name, group_id),
            )
    except sqlite3.IntegrityError as error:
        if "UNIQUE" in str(error):
            raise DuplicateMemberError(name) from error
        raise
    return member


def list_members(conn: sqlite3.Connection, group_id: str) -> list[Member]:
    rows = conn.execute(
        "SELECT id, name FROM members WHERE group_id = ? ORDER BY position", (group_id,)
    )
    return [Member(row["id"], row["name"]) for row in rows]


def add_expense(
    conn: sqlite3.Connection,
    group_id: str,
    payer_id: str,
    amount_cents: Cents,
    description: str,
    split_type: str,
    shares: Sequence[Share],
) -> Expense:
    expense = Expense(
        id=_new_id(),
        payer_id=payer_id,
        amount_cents=amount_cents,
        description=description,
        split_type=split_type,
        shares=list(shares),
        created_at=_now(),
    )
    with conn:
        conn.execute(
            """
            INSERT INTO expenses
                (id, group_id, payer_id, amount_cents, description, split_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                expense.id,
                group_id,
                payer_id,
                amount_cents,
                description,
                split_type,
                expense.created_at,
            ),
        )
        conn.executemany(
            "INSERT INTO expense_shares (expense_id, member_id, position, amount_cents)"
            " VALUES (?, ?, ?, ?)",
            [(expense.id, member_id, i, cents) for i, (member_id, cents) in enumerate(shares)],
        )
    return expense


def list_expenses(conn: sqlite3.Connection, group_id: str) -> list[Expense]:
    expense_rows = conn.execute(
        """
        SELECT id, payer_id, amount_cents, description, split_type, created_at
        FROM expenses WHERE group_id = ? ORDER BY rowid
        """,
        (group_id,),
    ).fetchall()
    share_rows = conn.execute(
        """
        SELECT s.expense_id, s.member_id, s.amount_cents
        FROM expense_shares s JOIN expenses e ON e.id = s.expense_id
        WHERE e.group_id = ? ORDER BY s.expense_id, s.position
        """,
        (group_id,),
    )
    shares: dict[str, list[Share]] = {}
    for row in share_rows:
        shares.setdefault(row["expense_id"], []).append((row["member_id"], row["amount_cents"]))
    return [
        Expense(
            id=row["id"],
            payer_id=row["payer_id"],
            amount_cents=row["amount_cents"],
            description=row["description"],
            split_type=row["split_type"],
            shares=shares.get(row["id"], []),
            created_at=row["created_at"],
        )
        for row in expense_rows
    ]
