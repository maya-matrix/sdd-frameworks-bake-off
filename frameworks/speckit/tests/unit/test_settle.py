import pytest

from splitit.models import Transfer
from splitit.settle import _zero_sum_groups, minimum_transfers


def _apply(balances, transfers):
    result = dict(balances)
    for t in transfers:
        assert t.amount_cents > 0
        assert t.from_member_id != t.to_member_id
        result[t.from_member_id] += t.amount_cents
        result[t.to_member_id] -= t.amount_cents
    return result


def _assert_clears(balances, transfers):
    assert all(v == 0 for v in _apply(balances, transfers).values())


def test_spec_scenario_one_creditor():
    balances = {"A": 2000, "B": -1000, "C": -1000}
    assert minimum_transfers(balances) == [Transfer("B", "A", 1000), Transfer("C", "A", 1000)]


def test_spec_scenario_independent_pairs():
    balances = {"A": 500, "B": -500, "C": 700, "D": -700}
    assert minimum_transfers(balances) == [Transfer("B", "A", 500), Transfer("D", "C", 700)]


def test_all_zero():
    assert minimum_transfers({"A": 0, "B": 0}) == []
    assert minimum_transfers({}) == []


def test_greedy_counterexample_uses_three_transfers():
    # Largest-debtor-pays-largest-creditor needs 4 here; the optimum is 3 (research §4).
    balances = {"a": -700, "b": -800, "c": 200, "d": 600, "e": 700}
    transfers = minimum_transfers(balances)
    assert len(transfers) == 3
    _assert_clears(balances, transfers)


def test_chain_needs_n_minus_one():
    balances = {"A": 300, "B": -100, "C": -100, "D": -100}
    transfers = minimum_transfers(balances)
    assert len(transfers) == 3
    _assert_clears(balances, transfers)


def test_output_follows_member_order():
    balances = {"Zed": -500, "Amy": 500, "Bob": -200, "Cat": 200}
    assert minimum_transfers(balances) == [Transfer("Zed", "Amy", 500), Transfer("Bob", "Cat", 200)]


def test_deterministic():
    balances = {f"m{i}": v for i, v in enumerate([1234, -999, 50, -285, 700, -700])}
    assert minimum_transfers(balances) == minimum_transfers(dict(balances))


def test_rejects_unbalanced_input():
    with pytest.raises(ValueError):
        minimum_transfers({"A": 100, "B": -99})


@pytest.mark.parametrize(
    "values",
    [
        [-700, -800, 200, 600, 700],
        [500, -500, 700, -700],
        [1234, -999, 50, -285, 700, -700],
        [3, 4, 5, -12],
    ],
)
def test_numpy_and_python_paths_agree(values):
    assert _zero_sum_groups(values, use_numpy=True) == _zero_sum_groups(values, use_numpy=False)


def test_huge_balances_use_exact_fallback():
    big = 2**70
    balances = {"A": big, "B": -big + 1, "C": -1}
    transfers = minimum_transfers(balances)
    assert len(transfers) == 2
    _assert_clears(balances, transfers)
