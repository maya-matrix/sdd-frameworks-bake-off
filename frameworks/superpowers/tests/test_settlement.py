import random
from itertools import combinations

import pytest

from app.settlement import EXACT_LIMIT, Transfer, minimize_transfers


def apply(balances, transfers):
    result = dict(balances)
    for transfer in transfers:
        assert transfer.amount_cents > 0
        result[transfer.from_member_id] += transfer.amount_cents
        result[transfer.to_member_id] -= transfer.amount_cents
    return result


def max_zero_sum_groups(values):
    if not values:
        return 0
    first, rest = values[0], values[1:]
    best = -len(values)
    for size in range(len(rest) + 1):
        for chosen in combinations(range(len(rest)), size):
            if first + sum(rest[i] for i in chosen) == 0:
                remaining = [rest[i] for i in range(len(rest)) if i not in chosen]
                best = max(best, 1 + max_zero_sum_groups(remaining))
    return best


def brute_force_minimum(values):
    nonzero = [v for v in values if v != 0]
    return len(nonzero) - max_zero_sum_groups(nonzero)


def test_no_balances():
    assert minimize_transfers({}) == ([], True)


def test_all_zero_balances():
    assert minimize_transfers({1: 0, 2: 0}) == ([], True)


def test_single_debt():
    assert minimize_transfers({1: 500, 2: -500}) == ([Transfer(2, 1, 500)], True)


def test_one_creditor_two_debtors():
    transfers, optimal = minimize_transfers({1: 666, 2: -333, 3: -333})
    assert optimal
    assert transfers == [Transfer(2, 1, 333), Transfer(3, 1, 333)]


def test_beats_greedy_where_greedy_needs_four_transfers():
    # Greedy (largest debtor pays largest creditor) uses 4 transfers here;
    # {+4, -2, -2} and {+3, -3} settle in 3.
    balances = {1: 400, 2: 300, 3: -300, 4: -200, 5: -200}
    transfers, optimal = minimize_transfers(balances)
    assert optimal
    assert transfers == [Transfer(3, 2, 300), Transfer(4, 1, 200), Transfer(5, 1, 200)]


def test_rejects_balances_that_do_not_sum_to_zero():
    with pytest.raises(ValueError):
        minimize_transfers({1: 100, 2: -99})


def test_matches_brute_force_minimum_on_random_cases():
    rng = random.Random(1234)
    for _ in range(300):
        size = rng.randint(2, 7)
        values = [rng.choice([-1, 1]) * rng.randint(1, 6) * 100 for _ in range(size - 1)]
        values.append(-sum(values))
        balances = {index + 1: value for index, value in enumerate(values)}
        transfers, optimal = minimize_transfers(balances)
        assert optimal
        assert all(value == 0 for value in apply(balances, transfers).values())
        assert len(transfers) == brute_force_minimum(values)


def test_transfers_are_sorted_and_deterministic():
    balances = {9: -700, 3: 200, 5: 500}
    first, _ = minimize_transfers(balances)
    second, _ = minimize_transfers(dict(reversed(list(balances.items()))))
    assert first == second
    assert first == sorted(first, key=lambda t: (t.from_member_id, t.to_member_id))


def test_exactly_twenty_nonzero_balances_is_solved_exactly():
    rng = random.Random(7)
    amounts = [100 * k for k in range(1, 11)]
    debts = amounts[:]
    rng.shuffle(debts)
    balances = {i + 1: amount for i, amount in enumerate(amounts)}
    balances.update({i + 11: -debt for i, debt in enumerate(debts)})
    assert sum(1 for v in balances.values() if v) == EXACT_LIMIT == 20
    transfers, optimal = minimize_transfers(balances)
    assert optimal
    assert len(transfers) == 10
    assert all(value == 0 for value in apply(balances, transfers).values())


def test_more_than_twenty_nonzero_balances_falls_back_to_greedy():
    balances = {i: 200 for i in range(1, 8)}
    balances.update({i: -100 for i in range(8, 22)})
    transfers, optimal = minimize_transfers(balances)
    assert not optimal
    assert all(value == 0 for value in apply(balances, transfers).values())
