"""Request and response bodies. Money is always a decimal string on the wire."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StrictInt, StrictStr, StringConstraints, field_validator

from app.money import parse_amount

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class GroupCreate(BaseModel):
    name: Name
    currency: Currency = "EUR"


class MemberCreate(BaseModel):
    name: Name


class MemberOut(BaseModel):
    id: int
    name: str


class GroupOut(BaseModel):
    id: int
    name: str
    currency: str
    members: list[MemberOut]


class ExpenseCreate(BaseModel):
    payer_id: StrictInt
    amount: StrictStr
    description: Description
    split_between: Annotated[list[StrictInt], Field(min_length=1)]

    @field_validator("amount")
    @classmethod
    def _amount_is_exact(cls, value: str) -> str:
        parse_amount(value)
        return value

    @field_validator("split_between")
    @classmethod
    def _no_duplicate_members(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("split_between must not contain duplicate member ids")
        return value

    @property
    def amount_cents(self) -> int:
        return parse_amount(self.amount)


class ShareOut(BaseModel):
    member_id: int
    amount: str


class ExpenseOut(BaseModel):
    id: int
    payer_id: int
    amount: str
    description: str
    created_at: datetime
    shares: list[ShareOut]


class BalanceOut(BaseModel):
    member_id: int
    name: str
    balance: str


class BalancesOut(BaseModel):
    currency: str
    balances: list[BalanceOut]


class TransferOut(BaseModel):
    from_member_id: int
    to_member_id: int
    amount: str


class SettleUpOut(BaseModel):
    currency: str
    optimal: bool
    transfers: list[TransferOut]
