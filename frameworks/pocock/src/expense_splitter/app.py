from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StrictInt

from expense_splitter.db import Database
from expense_splitter.errors import Conflict, DomainError, Invalid, NotFound
from expense_splitter.repository import Payment, Repository
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


class RecordPaymentBody(BaseModel):
    from_id: str
    to_id: str
    amount: StrictInt


class PaymentOut(BaseModel):
    id: str
    from_id: str
    to_id: str
    amount: int
    created_at: str

    @classmethod
    def of(cls, p: Payment) -> "PaymentOut":
        return cls(
            id=p.id, from_id=p.from_id, to_id=p.to_id, amount=p.amount, created_at=p.created_at
        )


class TransferOut(BaseModel):
    from_id: str
    to_id: str
    amount: int


class SettleUpOut(BaseModel):
    transfers: list[TransferOut]
    optimal: bool


_STATUS = {NotFound: 404, Invalid: 422, Conflict: 409}


def create_app(db_path: Path | str) -> FastAPI:
    db = Database(db_path)
    app = FastAPI(title="Expense Splitter")

    @contextmanager
    def unit_of_work() -> Iterator[Service]:
        # Opened inside each (synchronous) route body rather than as a yield
        # dependency, so the transaction and its write lock live and die on the
        # request's worker thread.
        with db.connect() as conn:
            yield Service(Repository(conn))

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=_STATUS[type(exc)], content={"detail": str(exc)})

    @app.post("/groups", status_code=201)
    def create_group(body: CreateGroupBody) -> GroupOut:
        with unit_of_work() as service:
            return GroupOut.of(service.create_group(body.name, body.currency, body.members))

    @app.get("/groups/{group_id}")
    def get_group(group_id: str) -> GroupOut:
        with unit_of_work() as service:
            return GroupOut.of(service.get_group(group_id))

    @app.post("/groups/{group_id}/members", status_code=201)
    def add_member(group_id: str, body: AddMemberBody) -> MemberOut:
        with unit_of_work() as service:
            member = service.add_member(group_id, body.name)
            return MemberOut(id=member.id, name=member.name)

    @app.delete("/groups/{group_id}/members/{member_id}", status_code=204)
    def remove_member(group_id: str, member_id: str) -> None:
        with unit_of_work() as service:
            service.remove_member(group_id, member_id)

    @app.post("/groups/{group_id}/expenses", status_code=201)
    def record_expense(group_id: str, body: RecordExpenseBody) -> ExpenseOut:
        with unit_of_work() as service:
            view = service.record_expense(
                group_id, body.payer_id, body.amount, body.description, body.participant_ids
            )
            return ExpenseOut.of(view)

    @app.get("/groups/{group_id}/expenses")
    def list_expenses(group_id: str) -> list[ExpenseOut]:
        with unit_of_work() as service:
            return [ExpenseOut.of(v) for v in service.list_expenses(group_id)]

    @app.delete("/groups/{group_id}/expenses/{expense_id}", status_code=204)
    def delete_expense(group_id: str, expense_id: str) -> None:
        with unit_of_work() as service:
            service.delete_expense(group_id, expense_id)

    @app.post("/groups/{group_id}/payments", status_code=201)
    def record_payment(group_id: str, body: RecordPaymentBody) -> PaymentOut:
        with unit_of_work() as service:
            return PaymentOut.of(
                service.record_payment(group_id, body.from_id, body.to_id, body.amount)
            )

    @app.get("/groups/{group_id}/payments")
    def list_payments(group_id: str) -> list[PaymentOut]:
        with unit_of_work() as service:
            return [PaymentOut.of(p) for p in service.list_payments(group_id)]

    @app.delete("/groups/{group_id}/payments/{payment_id}", status_code=204)
    def delete_payment(group_id: str, payment_id: str) -> None:
        with unit_of_work() as service:
            service.delete_payment(group_id, payment_id)

    @app.get("/groups/{group_id}/balances")
    def balances(group_id: str) -> list[BalanceOut]:
        with unit_of_work() as service:
            return [
                BalanceOut(member_id=m.id, name=m.name, balance=b)
                for m, b in service.balances(group_id)
            ]

    @app.get("/groups/{group_id}/settle-up")
    def settle_up(group_id: str) -> SettleUpOut:
        with unit_of_work() as service:
            result = service.settle_up(group_id)
            return SettleUpOut(
                transfers=[
                    TransferOut(from_id=t.from_id, to_id=t.to_id, amount=t.amount)
                    for t in result.transfers
                ],
                optimal=result.optimal,
            )

    return app
