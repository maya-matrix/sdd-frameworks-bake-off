"""HTTP routes. A thin layer over the repository and the pure domain functions."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from splitit.balances import compute_balances
from splitit.models import Expense, Group, Member
from splitit.repository import InMemoryRepository
from splitit.schemas import (
    BalanceListOut,
    BalanceOut,
    CreateExpense,
    CreateGroup,
    CreateMember,
    ExpenseListOut,
    ExpenseOut,
    GroupOut,
    MemberOut,
    SettleUpOut,
    ShareOut,
    TransferOut,
    money_out,
)
from splitit.settle import minimum_transfers

router = APIRouter()


def get_repository(request: Request) -> InMemoryRepository:
    return request.app.state.repository


Repo = Annotated[InMemoryRepository, Depends(get_repository)]


def _member_out(member: Member) -> MemberOut:
    return MemberOut(id=member.id, name=member.name)


def _group_out(group: Group) -> GroupOut:
    return GroupOut(id=group.id, name=group.name, members=[_member_out(m) for m in group.members])


def _expense_out(expense: Expense) -> ExpenseOut:
    return ExpenseOut(
        id=expense.id,
        payer_id=expense.payer_id,
        amount=money_out(expense.amount_cents),
        description=expense.description,
        shares=[ShareOut(member_id=s.member_id, amount=money_out(s.amount_cents)) for s in expense.shares],
        created_at=expense.created_at,
    )


@router.post("/groups", status_code=201, response_model=GroupOut)
def create_group(payload: CreateGroup, repo: Repo) -> GroupOut:
    return _group_out(repo.create_group(payload.name, payload.members))


@router.get("/groups/{group_id}", response_model=GroupOut)
def get_group(group_id: str, repo: Repo) -> GroupOut:
    return _group_out(repo.get_group(group_id))


@router.post("/groups/{group_id}/members", status_code=201, response_model=MemberOut)
def add_member(group_id: str, payload: CreateMember, repo: Repo) -> MemberOut:
    return _member_out(repo.add_member(group_id, payload.name))


@router.post("/groups/{group_id}/expenses", status_code=201, response_model=ExpenseOut)
def record_expense(group_id: str, payload: CreateExpense, repo: Repo) -> ExpenseOut:
    expense = repo.record_expense(
        group_id,
        payer_id=payload.payer_id,
        amount_cents=payload.amount,
        description=payload.description,
        participant_ids=payload.participant_ids,
    )
    return _expense_out(expense)


@router.get("/groups/{group_id}/expenses", response_model=ExpenseListOut)
def list_expenses(group_id: str, repo: Repo) -> ExpenseListOut:
    group = repo.get_group(group_id)
    return ExpenseListOut(expenses=[_expense_out(e) for e in group.expenses])


@router.get("/groups/{group_id}/balances", response_model=BalanceListOut)
def get_balances(group_id: str, repo: Repo) -> BalanceListOut:
    group = repo.get_group(group_id)
    balances = compute_balances(group)
    return BalanceListOut(
        balances=[BalanceOut(member_id=m.id, name=m.name, balance=money_out(balances[m.id])) for m in group.members]
    )


@router.get("/groups/{group_id}/settle-up", response_model=SettleUpOut)
def settle_up(group_id: str, repo: Repo) -> SettleUpOut:
    group = repo.get_group(group_id)
    transfers = minimum_transfers(compute_balances(group))
    return SettleUpOut(
        transfers=[
            TransferOut(from_member_id=t.from_member_id, to_member_id=t.to_member_id, amount=money_out(t.amount_cents))
            for t in transfers
        ]
    )
