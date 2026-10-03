"""Net balances per member, in integer cents. Positive = is owed, negative = owes."""

from splitit.models import Group


def compute_balances(group: Group) -> dict[str, int]:
    balances = {member.id: 0 for member in group.members}
    for expense in group.expenses:
        balances[expense.payer_id] += expense.amount_cents
        for share in expense.shares:
            balances[share.member_id] -= share.amount_cents
    return balances
