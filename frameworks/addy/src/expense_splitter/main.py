"""HTTP API: create_app(db_path) builds the app; `app` serves EXPENSES_DB_PATH."""

import os
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI

from expense_splitter import repository
from expense_splitter.db import connect, init_schema
from expense_splitter.errors import ApiError, register_error_handlers
from expense_splitter.schemas import (
    AddMemberRequest,
    CreateGroupRequest,
    GroupResponse,
    MemberResponse,
)


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

    return app


app = create_app(os.environ.get("EXPENSES_DB_PATH", "expenses.db"))
