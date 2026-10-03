"""Property-based checks of the money invariants required by Constitution II."""

from hypothesis import given
from hypothesis import strategies as st

from splitit.splitting import split_equally


@given(st.integers(min_value=1, max_value=100_000_000_000), st.integers(min_value=1, max_value=20))
def test_split_shares_sum_to_amount(amount, n):
    shares = split_equally(amount, n)
    assert sum(shares) == amount
    assert len(shares) == n
    assert max(shares) - min(shares) <= 1
    assert shares == sorted(shares, reverse=True)
    assert all(isinstance(s, int) for s in shares)


from splitit.balances import compute_balances  # noqa: E402
from splitit.models import Expense, Group, Member, Share, utc_now  # noqa: E402


@st.composite
def groups_with_expenses(draw):
    n = draw(st.integers(min_value=2, max_value=20))
    group = Group(id="g", name="G", created_at=utc_now())
    group.members = [Member(id=f"m{i}", group_id="g", name=f"m{i}") for i in range(n)]
    ids = [m.id for m in group.members]
    for _ in range(draw(st.integers(min_value=0, max_value=15))):
        payer = draw(st.sampled_from(ids))
        participants = draw(st.lists(st.sampled_from(ids), min_size=1, unique=True))
        amount = draw(st.integers(min_value=1, max_value=10**9))
        shares = tuple(Share(p, a) for p, a in zip(participants, split_equally(amount, len(participants))))
        group.expenses.append(Expense("e", "g", "x", amount, payer, shares, utc_now()))
    return group


@given(groups_with_expenses())
def test_balances_sum_to_zero(group):
    balances = compute_balances(group)
    assert sum(balances.values()) == 0
    assert list(balances) == [m.id for m in group.members]


from splitit.settle import minimum_transfers  # noqa: E402


def _brute_force_min_transfers(values: list[int]) -> int:
    """Independent reference: classic backtracking search for the minimum transfer count."""
    debts = [v for v in values if v != 0]

    def search(start: int) -> int:
        while start < len(debts) and debts[start] == 0:
            start += 1
        if start == len(debts):
            return 0
        best = len(debts)
        for j in range(start + 1, len(debts)):
            if debts[j] * debts[start] < 0:
                debts[j] += debts[start]
                best = min(best, 1 + search(start + 1))
                debts[j] -= debts[start]
        return best

    return search(0)


@st.composite
def zero_sum_balances(draw):
    n = draw(st.integers(min_value=2, max_value=8))
    values = draw(st.lists(st.integers(min_value=-(10**6), max_value=10**6), min_size=n - 1, max_size=n - 1))
    values.append(-sum(values))
    return {f"m{i}": v for i, v in enumerate(values)}


@given(zero_sum_balances())
def test_settle_up_clears_balances_minimally(balances):
    transfers = minimum_transfers(balances)
    after = dict(balances)
    for t in transfers:
        assert t.amount_cents > 0
        after[t.from_member_id] += t.amount_cents
        after[t.to_member_id] -= t.amount_cents
    assert all(v == 0 for v in after.values())
    assert len(transfers) == _brute_force_min_transfers(list(balances.values()))


@given(st.lists(st.integers(min_value=-50, max_value=50), min_size=1, max_size=7))
def test_settle_up_minimal_with_many_zero_sum_subgroups(values):
    # Small values make zero-sum subgroups common, exercising the partition search.
    values = values + [-sum(values)]
    balances = {f"m{i}": v for i, v in enumerate(values)}
    assert len(minimum_transfers(balances)) == _brute_force_min_transfers(values)
