from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StrictInt

from expense_splitter.db import Database
from expense_splitter.errors import Conflict, DomainError, Invalid, NotFound
from expense_splitter.repository import Repository
from expense_splitter.service import ExpenseView, GroupView, Service


class CreateGroupBody(BaseModel):
    name: str
    currency: str
    members: list[str] = []


class AddMemberBody(BaseModel):
    name: str


class MemberOut(BaseModel):
    id: str
    name: str


class GroupOut(BaseModel):
    id: str
    name: str
    currency: str
    created_at: str
    members: list[MemberOut]

    @classmethod
    def of(cls, view: GroupView) -> "GroupOut":
        return cls(
            id=view.group.id,
            name=view.group.name,
            currency=view.group.currency,
            created_at=view.group.created_at,
            members=[MemberOut(id=m.id, name=m.name) for m in view.members],
        )


class RecordExpenseBody(BaseModel):
    payer_id: str
    amount: StrictInt
    description: str
    participant_ids: list[str]


class ShareOut(BaseModel):
    member_id: str
    amount: int


class ExpenseOut(BaseModel):
    id: str
    payer_id: str
    amount: int
    description: str
    created_at: str
    shares: list[ShareOut]

    @classmethod
    def of(cls, view: ExpenseView) -> "ExpenseOut":
        e = view.expense
        return cls(
            id=e.id,
            payer_id=e.payer_id,
            amount=e.amount,
            description=e.description,
            created_at=e.created_at,
            shares=[ShareOut(member_id=m, amount=a) for m, a in view.shares],
        )


class BalanceOut(BaseModel):
    member_id: str
    name: str
    balance: int


_STATUS = {NotFound: 404, Invalid: 422, Conflict: 409}


def create_app(db_path: Path | str) -> FastAPI:
    db = Database(db_path)
    app = FastAPI(title="Expense Splitter")

    def get_service() -> Iterator[Service]:
        with db.connect() as conn:
            yield Service(Repository(conn))

    ServiceDep = Annotated[Service, Depends(get_service)]

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=_STATUS[type(exc)], content={"detail": str(exc)})

    @app.post("/groups", status_code=201)
    def create_group(body: CreateGroupBody, service: ServiceDep) -> GroupOut:
        return GroupOut.of(service.create_group(body.name, body.currency, body.members))

    @app.get("/groups/{group_id}")
    def get_group(group_id: str, service: ServiceDep) -> GroupOut:
        return GroupOut.of(service.get_group(group_id))

    @app.post("/groups/{group_id}/members", status_code=201)
    def add_member(group_id: str, body: AddMemberBody, service: ServiceDep) -> MemberOut:
        member = service.add_member(group_id, body.name)
        return MemberOut(id=member.id, name=member.name)

    @app.post("/groups/{group_id}/expenses", status_code=201)
    def record_expense(group_id: str, body: RecordExpenseBody, service: ServiceDep) -> ExpenseOut:
        view = service.record_expense(
            group_id, body.payer_id, body.amount, body.description, body.participant_ids
        )
        return ExpenseOut.of(view)

    @app.get("/groups/{group_id}/expenses")
    def list_expenses(group_id: str, service: ServiceDep) -> list[ExpenseOut]:
        return [ExpenseOut.of(v) for v in service.list_expenses(group_id)]

    @app.get("/groups/{group_id}/balances")
    def balances(group_id: str, service: ServiceDep) -> list[BalanceOut]:
        return [
            BalanceOut(member_id=m.id, name=m.name, balance=b)
            for m, b in service.balances(group_id)
        ]

    return app
