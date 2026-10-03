"""HTTP API: create_app(db_path) builds the app; `app` serves EXPENSES_DB_PATH."""

import os
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI

from expense_splitter import repository
from expense_splitter.balances import ExpenseShares, compute_balances
from expense_splitter.db import connect, init_schema
from expense_splitter.errors import ApiError, register_error_handlers
from expense_splitter.money import format_cents, parse_amount
from expense_splitter.schemas import (
    AddMemberRequest,
    BalancesResponse,
    CreateGroupRequest,
    ExpenseListResponse,
    ExpenseResponse,
    GroupResponse,
    MemberBalance,
    MemberResponse,
    RecordExpenseRequest,
    SettleUpResponse,
    ShareResponse,
    TransferResponse,
)
from expense_splitter.settle import settle_up
from expense_splitter.split import split_equally


def create_app(db_path: str | Path) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        conn = connect(db_path)
        init_schema(conn)
        conn.close()
        yield

    def get_conn() -> Iterator[sqlite3.Connection]:
        conn = connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    Conn = Annotated[sqlite3.Connection, Depends(get_conn)]

    app = FastAPI(title="Expense Splitter", lifespan=lifespan)
    register_error_handlers(app)

    def require_group(conn: sqlite3.Connection, group_id: str) -> repository.Group:
        group = repository.get_group(conn, group_id)
        if group is None:
            raise ApiError(404, "GROUP_NOT_FOUND", f"group {group_id} not found")
        return group

    def group_response(conn: sqlite3.Connection, group: repository.Group) -> GroupResponse:
        members = repository.list_members(conn, group.id)
        return GroupResponse(
            id=group.id,
            name=group.name,
            currency=group.currency,
            members=[MemberResponse(id=m.id, name=m.name) for m in members],
        )

    def expense_response(expense: repository.Expense) -> ExpenseResponse:
        return ExpenseResponse(
            id=expense.id,
            payer_id=expense.payer_id,
            amount=format_cents(expense.amount_cents),
            description=expense.description,
            split_type=expense.split_type,
            shares=[
                ShareResponse(member_id=member_id, amount=format_cents(cents))
                for member_id, cents in expense.shares
            ],
            created_at=expense.created_at,
        )

    def member_balances(
        conn: sqlite3.Connection, group_id: str
    ) -> list[tuple[repository.Member, int]]:
        """Each member with their balance in cents, in join order."""
        members = repository.list_members(conn, group_id)
        balances = compute_balances(
            [member.id for member in members],
            [
                ExpenseShares(payer_id=e.payer_id, shares=e.shares)
                for e in repository.list_expenses(conn, group_id)
            ],
        )
        return [(member, balances[member.id]) for member in members]

    @app.post("/groups", status_code=201)
    def create_group(body: CreateGroupRequest, conn: Conn) -> GroupResponse:
        group = repository.create_group(conn, name=body.name, currency=body.currency)
        return group_response(conn, group)

    @app.get("/groups/{group_id}")
    def get_group(group_id: str, conn: Conn) -> GroupResponse:
        return group_response(conn, require_group(conn, group_id))

    @app.post("/groups/{group_id}/members", status_code=201)
    def add_member(group_id: str, body: AddMemberRequest, conn: Conn) -> MemberResponse:
        require_group(conn, group_id)
        try:
            member = repository.add_member(conn, group_id, body.name)
        except repository.DuplicateMemberError:
            raise ApiError(
                409, "DUPLICATE_MEMBER", f"a member named {body.name!r} already exists"
            ) from None
        return MemberResponse(id=member.id, name=member.name)

    @app.post("/groups/{group_id}/expenses", status_code=201)
    def record_expense(group_id: str, body: RecordExpenseRequest, conn: Conn) -> ExpenseResponse:
        require_group(conn, group_id)
        member_ids = {member.id for member in repository.list_members(conn, group_id)}
        unknown = [
            member_id
            for member_id in [body.payer_id, *body.split_between]
            if member_id not in member_ids
        ]
        if unknown:
            raise ApiError(400, "UNKNOWN_MEMBER", f"not a member of this group: {unknown[0]}")
        amount_cents = parse_amount(body.amount)
        expense = repository.add_expense(
            conn,
            group_id=group_id,
            payer_id=body.payer_id,
            amount_cents=amount_cents,
            description=body.description,
            split_type="equal",
            shares=split_equally(amount_cents, body.split_between),
        )
        return expense_response(expense)

    @app.get("/groups/{group_id}/expenses")
    def list_expenses(group_id: str, conn: Conn) -> ExpenseListResponse:
        require_group(conn, group_id)
        expenses = repository.list_expenses(conn, group_id)
        return ExpenseListResponse(expenses=[expense_response(e) for e in expenses])

    @app.get("/groups/{group_id}/balances")
    def get_balances(group_id: str, conn: Conn) -> BalancesResponse:
        group = require_group(conn, group_id)
        return BalancesResponse(
            currency=group.currency,
            balances=[
                MemberBalance(member_id=member.id, name=member.name, balance=format_cents(cents))
                for member, cents in member_balances(conn, group_id)
            ],
        )

    @app.get("/groups/{group_id}/settle-up")
    def get_settle_up(group_id: str, conn: Conn) -> SettleUpResponse:
        group = require_group(conn, group_id)
        balances = [(member.id, cents) for member, cents in member_balances(conn, group_id)]
        return SettleUpResponse(
            currency=group.currency,
            transfers=[
                TransferResponse(
                    from_member_id=t.from_id, to_member_id=t.to_id, amount=format_cents(t.amount)
                )
                for t in settle_up(balances)
            ],
        )

    return app


app = create_app(os.environ.get("EXPENSES_DB_PATH", "expenses.db"))
