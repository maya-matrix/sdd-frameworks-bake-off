from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from expense_splitter.db import Database
from expense_splitter.errors import Conflict, DomainError, Invalid, NotFound
from expense_splitter.repository import Repository
from expense_splitter.service import GroupView, Service


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

    return app
