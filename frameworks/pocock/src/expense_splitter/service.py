from dataclasses import dataclass

from expense_splitter.errors import Conflict, Invalid, NotFound
from expense_splitter.money import SUPPORTED_CURRENCIES
from expense_splitter.repository import Group, Member, Repository


@dataclass(frozen=True)
class GroupView:
    group: Group
    members: list[Member]


class Service:
    """Applies the domain rules on top of the Repository."""

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def create_group(self, name: str, currency: str, member_names: list[str]) -> GroupView:
        name = name.strip()
        if not 1 <= len(name) <= 100:
            raise Invalid("Group name must be 1-100 characters")
        if currency not in SUPPORTED_CURRENCIES:
            raise Invalid(f"Unsupported currency: {currency!r}")
        group = self.repo.insert_group(name, currency)
        for member_name in member_names:
            self._add_member(group.id, member_name)
        return self.get_group(group.id)

    def add_member(self, group_id: str, name: str) -> Member:
        self._require_group(group_id)
        return self._add_member(group_id, name)

    def _add_member(self, group_id: str, name: str) -> Member:
        name = name.strip()
        if not 1 <= len(name) <= 50:
            raise Invalid("Member name must be 1-50 characters")
        # Departed Members keep their name reserved, so check against everyone.
        taken = {m.name.casefold() for m in self.repo.list_members(group_id)}
        if name.casefold() in taken:
            raise Conflict(f"A Member named {name!r} already exists in this Group")
        return self.repo.insert_member(group_id, name)

    def get_group(self, group_id: str) -> GroupView:
        group = self._require_group(group_id)
        members = [m for m in self.repo.list_members(group_id) if m.departed_at is None]
        return GroupView(group=group, members=members)

    def _require_group(self, group_id: str) -> Group:
        group = self.repo.get_group(group_id)
        if group is None:
            raise NotFound("Group not found")
        return group
