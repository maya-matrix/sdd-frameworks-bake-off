"""Net balance per member: positive means the member is owed money, negative means they owe."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from expense_splitter.money import Cents
from expense_splitter.split import Share


@dataclass(frozen=True)
class ExpenseShares:
    payer_id: str
    shares: Sequence[Share]


def compute_balances(
    member_ids: Sequence[str], expenses: Iterable[ExpenseShares]
) -> dict[str, Cents]:
    """Balance = cents paid - cents owed, keyed in `member_ids` order. Always sums to zero."""
    balances = dict.fromkeys(member_ids, 0)
    for expense in expenses:
        for member_id, amount in expense.shares:
            balances[expense.payer_id] += amount
            balances[member_id] -= amount
    return balances
