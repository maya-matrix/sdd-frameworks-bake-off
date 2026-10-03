"""HTTP request/response models. JSON keys are camelCase; money is a decimal string."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints
from pydantic.alias_generators import to_camel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CreateGroupRequest(CamelModel):
    name: Name
    currency: Currency = "EUR"


class MemberResponse(CamelModel):
    id: str
    name: str


class GroupResponse(CamelModel):
    id: str
    name: str
    currency: str
    members: list[MemberResponse]
