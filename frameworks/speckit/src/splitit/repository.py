"""In-memory storage. Writes are serialized with a lock so each request is all-or-nothing."""

import threading
from collections.abc import Sequence

from splitit.errors import DuplicateMemberNameError, NotFoundError, ValidationFailedError
from splitit.models import MAX_MEMBERS_PER_GROUP, Expense, Group, Member, Share, new_id, utc_now
from splitit.splitting import split_equally


class InMemoryRepository:
    def __init__(self) -> None:
        self._groups: dict[str, Group] = {}
        self._lock = threading.Lock()

    def create_group(self, name: str, member_names: Sequence[str] = ()) -> Group:
        """Create a group, optionally with initial members; all-or-nothing."""
        group = Group(id=new_id(), name=name, created_at=utc_now())
        for member_name in member_names:
            self._check_new_member(group, member_name, field="members")
            group.members.append(Member(id=new_id(), group_id=group.id, name=member_name.strip()))
        with self._lock:
            self._groups[group.id] = group
        return group

    def get_group(self, group_id: str) -> Group:
        group = self._groups.get(group_id)
        if group is None:
            raise NotFoundError(f"group {group_id!r} not found", field="group_id")
        return group

    def add_member(self, group_id: str, name: str) -> Member:
        with self._lock:
            group = self.get_group(group_id)
            self._check_new_member(group, name, field="name")
            member = Member(id=new_id(), group_id=group.id, name=name.strip())
            group.members.append(member)
            return member

    @staticmethod
    def _check_new_member(group: Group, name: str, field: str) -> None:
        key = name.strip().casefold()
        if any(m.name.casefold() == key for m in group.members):
            raise DuplicateMemberNameError(f"a member named {name.strip()!r} already exists in this group", field=field)
        if len(group.members) >= MAX_MEMBERS_PER_GROUP:
            raise ValidationFailedError(f"a group can have at most {MAX_MEMBERS_PER_GROUP} members", field=field)

    def record_expense(
        self,
        group_id: str,
        payer_id: str,
        amount_cents: int,
        description: str,
        participant_ids: list[str],
    ) -> Expense:
        with self._lock:
            group = self.get_group(group_id)
            if group.find_member(payer_id) is None:
                raise NotFoundError(f"payer {payer_id!r} is not a member of this group", field="payer_id")
            for member_id in participant_ids:
                if group.find_member(member_id) is None:
                    raise NotFoundError(
                        f"participant {member_id!r} is not a member of this group", field="participant_ids"
                    )
            amounts = split_equally(amount_cents, len(participant_ids))
            expense = Expense(
                id=new_id(),
                group_id=group.id,
                description=description,
                amount_cents=amount_cents,
                payer_id=payer_id,
                shares=tuple(Share(m, a) for m, a in zip(participant_ids, amounts, strict=True)),
                created_at=utc_now(),
            )
            group.expenses.append(expense)
            return expense
