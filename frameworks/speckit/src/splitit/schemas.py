"""Pydantic request/response models. Money crosses the API only as two-decimal strings."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, StrictStr, StringConstraints

from splitit.money import MAX_EXPENSE_CENTS, MIN_EXPENSE_CENTS, MoneyFormatError, format_money, parse_money


def _to_cents(value: object) -> int:
    if not isinstance(value, str):
        raise ValueError('must be a string with exactly two decimals, e.g. "10.00" (numbers are not accepted)')
    try:
        return parse_money(value)
    except MoneyFormatError as exc:
        raise ValueError(str(exc)) from None


# Input money: a strict string converted to integer cents. JSON numbers fail validation.
MoneyIn = Annotated[int, BeforeValidator(_to_cents)]


def money_out(cents: int) -> str:
    return format_money(cents)


Name = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=100)]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateGroup(_Input):
    name: Name
    members: list[Name] = []


class CreateMember(_Input):
    name: Name


class MemberOut(BaseModel):
    id: str
    name: str


class GroupOut(BaseModel):
    id: str
    name: str
    members: list[MemberOut]


def _check_expense_amount(cents: int) -> int:
    if cents < MIN_EXPENSE_CENTS:
        raise ValueError("amount must be at least 0.01")
    if cents > MAX_EXPENSE_CENTS:
        raise ValueError(f"amount must be at most {format_money(MAX_EXPENSE_CENTS)}")
    return cents


def _check_distinct(ids: list[str]) -> list[str]:
    if len(set(ids)) != len(ids):
        raise ValueError("participants must be distinct")
    return ids


ExpenseAmount = Annotated[MoneyIn, AfterValidator(_check_expense_amount)]
Description = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=200)]
ParticipantIds = Annotated[list[StrictStr], Field(min_length=1), AfterValidator(_check_distinct)]


class CreateExpense(_Input):
    payer_id: StrictStr
    amount: ExpenseAmount
    description: Description
    participant_ids: ParticipantIds


class ShareOut(BaseModel):
    member_id: str
    amount: str


class ExpenseOut(BaseModel):
    id: str
    payer_id: str
    amount: str
    description: str
    shares: list[ShareOut]
    created_at: datetime


class ExpenseListOut(BaseModel):
    expenses: list[ExpenseOut]


class BalanceOut(BaseModel):
    member_id: str
    name: str
    balance: str


class BalanceListOut(BaseModel):
    balances: list[BalanceOut]


class TransferOut(BaseModel):
    from_member_id: str
    to_member_id: str
    amount: str


class SettleUpOut(BaseModel):
    transfers: list[TransferOut]
