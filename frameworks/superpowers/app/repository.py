"""Database access for groups, members and expenses."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Expense, ExpenseShare, Group, Member
from app.splitting import split_equally

MAX_ID = 2**63 - 1  # SQLite INTEGER range


class GroupNotFound(Exception):
    def __init__(self, group_id: int) -> None:
        super().__init__(f"group {group_id} not found")


class DuplicateMemberName(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"a member named {name!r} already exists in this group")


class InvalidExpense(Exception):
    pass


def create_group(session: Session, name: str, currency: str) -> Group:
    group = Group(name=name, currency=currency)
    session.add(group)
    session.commit()
    return group


def get_group(session: Session, group_id: int) -> Group:
    if not 1 <= group_id <= MAX_ID:
        raise GroupNotFound(group_id)
    group = session.get(Group, group_id)
    if group is None:
        raise GroupNotFound(group_id)
    return group


def add_member(session: Session, group_id: int, name: str) -> Member:
    get_group(session, group_id)
    member = Member(group_id=group_id, name=name)
    session.add(member)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DuplicateMemberName(name) from None
    return member


def list_members(session: Session, group_id: int) -> list[Member]:
    return list(get_group(session, group_id).members)


def record_expense(
    session: Session,
    group_id: int,
    *,
    payer_id: int,
    amount_cents: int,
    description: str,
    split_between: Sequence[int],
) -> Expense:
    group = get_group(session, group_id)
    member_ids = {member.id for member in group.members}
    if payer_id not in member_ids:
        raise InvalidExpense(f"payer {payer_id} is not a member of this group")
    outsiders = sorted(set(split_between) - member_ids)
    if outsiders:
        raise InvalidExpense(f"members {outsiders} are not in this group")
    shares = split_equally(amount_cents, split_between)
    expense = Expense(
        group_id=group_id,
        payer_id=payer_id,
        amount_cents=amount_cents,
        description=description,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        shares=[ExpenseShare(member_id=member_id, share_cents=cents) for member_id, cents in shares.items()],
    )
    session.add(expense)
    session.commit()
    return expense


def list_expenses(session: Session, group_id: int) -> list[Expense]:
    get_group(session, group_id)
    query = (
        select(Expense)
        .where(Expense.group_id == group_id)
        .options(selectinload(Expense.shares))
        .order_by(Expense.id)
    )
    return list(session.scalars(query))


def member_balances(session: Session, group_id: int) -> list[tuple[Member, int]]:
    """Each member's net balance in cents (paid - owed), ordered by member id.

    Paid and owed amounts are summed in a single statement so the result comes
    from one consistent snapshot even while other requests record expenses.
    """
    group = get_group(session, group_id)
    paid = select(Expense.payer_id.label("member_id"), Expense.amount_cents.label("cents")).where(
        Expense.group_id == group_id
    )
    owed = (
        select(ExpenseShare.member_id.label("member_id"), (-ExpenseShare.share_cents).label("cents"))
        .join(Expense, ExpenseShare.expense_id == Expense.id)
        .where(Expense.group_id == group_id)
    )
    movements = union_all(paid, owed).subquery()
    totals = dict(
        session.execute(
            select(movements.c.member_id, func.sum(movements.c.cents)).group_by(movements.c.member_id)
        ).all()
    )
    return [(member, totals.get(member.id, 0)) for member in group.members]
