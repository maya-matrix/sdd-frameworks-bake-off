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


@dataclass(frozen=True)
class Expense:
    id: str
    group_id: str
    payer_id: str
    amount: int
    description: str
    created_at: str
    participant_ids: list[str]
    """In the Participants' join order."""


@dataclass(frozen=True)
class Payment:
    id: str
    group_id: str
    from_id: str
    to_id: str
    amount: int
    created_at: str


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

    def mark_departed(self, member_id: str) -> None:
        self.conn.execute(
            "UPDATE members SET departed_at = ? WHERE id = ?", (_now(), member_id)
        )

    def list_members(self, group_id: str) -> list[Member]:
        """All Members of the Group, including Departed Members, in join order."""
        rows = self.conn.execute(
            "SELECT id, group_id, name, join_order, departed_at FROM members"
            " WHERE group_id = ? ORDER BY join_order",
            (group_id,),
        ).fetchall()
        return [Member(**row) for row in rows]

    def insert_expense(
        self,
        group_id: str,
        payer_id: str,
        amount: int,
        description: str,
        participant_ids: list[str],
    ) -> str:
        expense_id = _new_id()
        self.conn.execute(
            "INSERT INTO expenses (id, group_id, payer_id, amount, description, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (expense_id, group_id, payer_id, amount, description, _now()),
        )
        self.conn.executemany(
            "INSERT INTO expense_participants (expense_id, member_id) VALUES (?, ?)",
            [(expense_id, member_id) for member_id in participant_ids],
        )
        return expense_id

    def list_expenses(self, group_id: str, expense_id: str | None = None) -> list[Expense]:
        """The Group's Expenses in the order they were recorded (optionally just one)."""
        query = (
            "SELECT id, group_id, payer_id, amount, description, created_at FROM expenses"
            " WHERE group_id = ?"
        )
        params: tuple[str, ...] = (group_id,)
        if expense_id is not None:
            query += " AND id = ?"
            params += (expense_id,)
        rows = self.conn.execute(query + " ORDER BY rowid", params).fetchall()
        participants: dict[str, list[str]] = {row["id"]: [] for row in rows}
        for p in self.conn.execute(
            "SELECT ep.expense_id, ep.member_id FROM expense_participants ep"
            " JOIN expenses e ON e.id = ep.expense_id"
            " JOIN members m ON m.id = ep.member_id"
            " WHERE e.group_id = ? ORDER BY m.join_order",
            (group_id,),
        ):
            if p["expense_id"] in participants:
                participants[p["expense_id"]].append(p["member_id"])
        return [Expense(**row, participant_ids=participants[row["id"]]) for row in rows]

    def insert_payment(self, group_id: str, from_id: str, to_id: str, amount: int) -> Payment:
        payment = Payment(
            id=_new_id(),
            group_id=group_id,
            from_id=from_id,
            to_id=to_id,
            amount=amount,
            created_at=_now(),
        )
        self.conn.execute(
            "INSERT INTO payments (id, group_id, from_id, to_id, amount, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (payment.id, group_id, from_id, to_id, amount, payment.created_at),
        )
        return payment

    def list_payments(self, group_id: str) -> list[Payment]:
        """The Group's Payments in the order they were recorded."""
        rows = self.conn.execute(
            "SELECT id, group_id, from_id, to_id, amount, created_at FROM payments"
            " WHERE group_id = ? ORDER BY rowid",
            (group_id,),
        ).fetchall()
        return [Payment(**row) for row in rows]

    def delete_expense(self, group_id: str, expense_id: str) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM expenses WHERE group_id = ? AND id = ?", (group_id, expense_id)
        )
        return cursor.rowcount == 1

    def delete_payment(self, group_id: str, payment_id: str) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM payments WHERE group_id = ? AND id = ?", (group_id, payment_id)
        )
        return cursor.rowcount == 1
