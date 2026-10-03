"""Domain dataclasses. All money fields are integer cents."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

MAX_MEMBERS_PER_GROUP = 20


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Member:
    id: str
    group_id: str
    name: str


@dataclass(frozen=True)
class Share:
    member_id: str
    amount_cents: int


@dataclass(frozen=True)
class Expense:
    id: str
    group_id: str
    description: str
    amount_cents: int
    payer_id: str
    shares: tuple[Share, ...]
    created_at: datetime


@dataclass
class Group:
    id: str
    name: str
    created_at: datetime
    members: list[Member] = field(default_factory=list)
    expenses: list[Expense] = field(default_factory=list)

    def find_member(self, member_id: str) -> Member | None:
        return next((m for m in self.members if m.id == member_id), None)


@dataclass(frozen=True)
class Transfer:
    from_member_id: str
    to_member_id: str
    amount_cents: int
