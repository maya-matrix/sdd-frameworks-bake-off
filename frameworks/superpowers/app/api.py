"""HTTP routes: JSON with decimal-string money on the outside, integer cents inside."""

from collections.abc import Iterator
from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import repository, schemas
from app.models import Expense, Group, Member
from app.money import format_cents
from app.settlement import minimize_transfers

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

_ERROR_STATUS: dict[type[Exception], int] = {
    repository.GroupNotFound: 404,
    repository.DuplicateMemberName: 409,
    repository.InvalidExpense: 422,
}


def register_error_handlers(app: FastAPI) -> None:
    for error_type, status_code in _ERROR_STATUS.items():
        app.add_exception_handler(error_type, _error_handler(status_code))


def _error_handler(status_code: int):
    async def handle(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handle


def _member_out(member: Member) -> schemas.MemberOut:
    return schemas.MemberOut(id=member.id, name=member.name)


def _group_out(group: Group) -> schemas.GroupOut:
    return schemas.GroupOut(
        id=group.id,
        name=group.name,
        currency=group.currency,
        members=[_member_out(member) for member in group.members],
    )


def _expense_out(expense: Expense) -> schemas.ExpenseOut:
    return schemas.ExpenseOut(
        id=expense.id,
        payer_id=expense.payer_id,
        amount=format_cents(expense.amount_cents),
        description=expense.description,
        created_at=expense.created_at.replace(tzinfo=UTC),
        shares=[
            schemas.ShareOut(member_id=share.member_id, amount=format_cents(share.share_cents))
            for share in expense.shares
        ],
    )


@router.post("/groups", status_code=201)
def create_group(body: schemas.GroupCreate, session: SessionDep) -> schemas.GroupOut:
    return _group_out(repository.create_group(session, body.name, body.currency))


@router.get("/groups/{group_id}")
def get_group(group_id: int, session: SessionDep) -> schemas.GroupOut:
    return _group_out(repository.get_group(session, group_id))


@router.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: schemas.MemberCreate, session: SessionDep) -> schemas.MemberOut:
    return _member_out(repository.add_member(session, group_id, body.name))


@router.get("/groups/{group_id}/members")
def list_members(group_id: int, session: SessionDep) -> list[schemas.MemberOut]:
    return [_member_out(member) for member in repository.list_members(session, group_id)]


@router.post("/groups/{group_id}/expenses", status_code=201)
def record_expense(group_id: int, body: schemas.ExpenseCreate, session: SessionDep) -> schemas.ExpenseOut:
    expense = repository.record_expense(
        session,
        group_id,
        payer_id=body.payer_id,
        amount_cents=body.amount_cents,
        description=body.description,
        split_between=body.split_between,
    )
    return _expense_out(expense)


@router.get("/groups/{group_id}/expenses")
def list_expenses(group_id: int, session: SessionDep) -> list[schemas.ExpenseOut]:
    return [_expense_out(expense) for expense in repository.list_expenses(session, group_id)]


@router.get("/groups/{group_id}/balances")
def get_balances(group_id: int, session: SessionDep) -> schemas.BalancesOut:
    group = repository.get_group(session, group_id)
    return schemas.BalancesOut(
        currency=group.currency,
        balances=[
            schemas.BalanceOut(member_id=member.id, name=member.name, balance=format_cents(cents))
            for member, cents in repository.member_balances(session, group_id)
        ],
    )


@router.get("/groups/{group_id}/settle-up")
def settle_up(group_id: int, session: SessionDep) -> schemas.SettleUpOut:
    group = repository.get_group(session, group_id)
    balances = {member.id: cents for member, cents in repository.member_balances(session, group_id)}
    transfers, optimal = minimize_transfers(balances)
    return schemas.SettleUpOut(
        currency=group.currency,
        optimal=optimal,
        transfers=[
            schemas.TransferOut(
                from_member_id=transfer.from_member_id,
                to_member_id=transfer.to_member_id,
                amount=format_cents(transfer.amount_cents),
            )
            for transfer in transfers
        ],
    )
