"""HTTP request/response models. JSON keys are camelCase; money is a decimal string."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictStr, StringConstraints
from pydantic.alias_generators import to_camel

from expense_splitter.money import parse_amount

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


def _valid_amount(text: str) -> str:
    parse_amount(text)
    return text


def _unique(member_ids: list[str]) -> list[str]:
    if len(set(member_ids)) != len(member_ids):
        raise ValueError("must not contain duplicate member ids")
    return member_ids


# A JSON string such as "10.50"; JSON numbers are rejected so no float ever touches money.
Amount = Annotated[StrictStr, AfterValidator(_valid_amount)]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CreateGroupRequest(CamelModel):
    name: Name
    currency: Currency = "EUR"


class AddMemberRequest(CamelModel):
    name: Name


class MemberResponse(CamelModel):
    id: str
    name: str


class GroupResponse(CamelModel):
    id: str
    name: str
    currency: str
    members: list[MemberResponse]


class RecordExpenseRequest(CamelModel):
    payer_id: StrictStr
    amount: Amount
    description: Description
    split_between: Annotated[list[StrictStr], Field(min_length=1), AfterValidator(_unique)]


class ShareResponse(CamelModel):
    member_id: str
    amount: str


class ExpenseResponse(CamelModel):
    id: str
    payer_id: str
    amount: str
    description: str
    split_type: str
    shares: list[ShareResponse]
    created_at: str


class ExpenseListResponse(CamelModel):
    expenses: list[ExpenseResponse]
