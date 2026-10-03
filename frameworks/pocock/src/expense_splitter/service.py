from dataclasses import dataclass

from expense_splitter.errors import Conflict, Invalid, NotFound
from expense_splitter.money import MAX_AMOUNT, SUPPORTED_CURRENCIES, split_equally
from expense_splitter.repository import Expense, Group, Member, Payment, Repository
from expense_splitter.settle_up import SettleUpResult, settle_up


@dataclass(frozen=True)
class GroupView:
    group: Group
    members: list[Member]


@dataclass(frozen=True)
class ExpenseView:
    expense: Expense
    shares: list[tuple[str, int]]
    """(member_id, Share) in the Participants' join order."""

    @classmethod
    def of(cls, expense: Expense) -> "ExpenseView":
        return cls(expense, split_equally(expense.amount, expense.participant_ids))


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

    def record_expense(
        self,
        group_id: str,
        payer_id: str,
        amount: int,
        description: str,
        participant_ids: list[str],
    ) -> ExpenseView:
        self._require_group(group_id)
        _check_amount(amount)
        description = description.strip()
        if not 1 <= len(description) <= 200:
            raise Invalid("Description must be 1-200 characters")
        if not participant_ids:
            raise Invalid("An Expense needs at least one Participant")
        if len(set(participant_ids)) != len(participant_ids):
            raise Invalid("Participants must not repeat")
        current = self._current_member_ids(group_id)
        if payer_id not in current:
            raise Invalid("Payer is not a Member of this Group")
        if not set(participant_ids) <= current:
            raise Invalid("Every Participant must be a Member of this Group")
        expense_id = self.repo.insert_expense(
            group_id, payer_id, amount, description, participant_ids
        )
        (expense,) = self.repo.list_expenses(group_id, expense_id)
        return ExpenseView.of(expense)

    def list_expenses(self, group_id: str) -> list[ExpenseView]:
        self._require_group(group_id)
        return [ExpenseView.of(e) for e in self.repo.list_expenses(group_id)]

    def record_payment(self, group_id: str, from_id: str, to_id: str, amount: int) -> Payment:
        self._require_group(group_id)
        _check_amount(amount)
        if from_id == to_id:
            raise Invalid("A Member cannot pay themselves")
        if not {from_id, to_id} <= self._current_member_ids(group_id):
            raise Invalid("Sender and recipient must be Members of this Group")
        return self.repo.insert_payment(group_id, from_id, to_id, amount)

    def list_payments(self, group_id: str) -> list[Payment]:
        self._require_group(group_id)
        return self.repo.list_payments(group_id)

    def balances(self, group_id: str) -> list[tuple[Member, int]]:
        """Every current Member's Balance, in join order. Positive means they are owed."""
        self._require_group(group_id)
        balances = self._all_balances(group_id)
        return [
            (m, balances[m.id]) for m in self.repo.list_members(group_id) if m.departed_at is None
        ]

    def settle_up(self, group_id: str) -> SettleUpResult:
        return settle_up([(m.id, balance) for m, balance in self.balances(group_id)])

    def _all_balances(self, group_id: str) -> dict[str, int]:
        """Balances of every Member, including Departed Members."""
        balances = {m.id: 0 for m in self.repo.list_members(group_id)}
        for expense in self.repo.list_expenses(group_id):
            balances[expense.payer_id] += expense.amount
            for member_id, share in split_equally(expense.amount, expense.participant_ids):
                balances[member_id] -= share
        for payment in self.repo.list_payments(group_id):
            balances[payment.from_id] += payment.amount
            balances[payment.to_id] -= payment.amount
        return balances

    def _current_member_ids(self, group_id: str) -> set[str]:
        return {m.id for m in self.repo.list_members(group_id) if m.departed_at is None}

    def _require_group(self, group_id: str) -> Group:
        group = self.repo.get_group(group_id)
        if group is None:
            raise NotFound("Group not found")
        return group


def _check_amount(amount: int) -> None:
    if not 0 < amount <= MAX_AMOUNT:
        raise Invalid("Amount must be a positive whole number of minor units")
