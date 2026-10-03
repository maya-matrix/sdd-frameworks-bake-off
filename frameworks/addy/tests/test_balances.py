from hypothesis import given
from hypothesis import strategies as st

from expense_splitter.balances import ExpenseShares, compute_balances
from expense_splitter.split import split_equally


def test_payer_is_owed_what_others_owe() -> None:
    expense = ExpenseShares(payer_id="a", shares=split_equally(1000, ["a", "b", "c"]))

    balances = compute_balances(["a", "b", "c"], [expense])

    assert balances == {"a": 666, "b": -333, "c": -333}


def test_payer_outside_the_split_is_credited_full_amount() -> None:
    expense = ExpenseShares(payer_id="a", shares=split_equally(1000, ["b", "c"]))

    balances = compute_balances(["a", "b", "c"], [expense])

    assert balances == {"a": 1000, "b": -500, "c": -500}


def test_members_without_expenses_have_zero_balance() -> None:
    expense = ExpenseShares(payer_id="a", shares=[("b", 500)])

    balances = compute_balances(["a", "b", "c"], [expense])

    assert balances == {"a": 500, "b": -500, "c": 0}


def test_no_expenses_means_everyone_is_zero() -> None:
    assert compute_balances(["a", "b"], []) == {"a": 0, "b": 0}


def test_balances_follow_member_order() -> None:
    balances = compute_balances(["c", "a", "b"], [])

    assert list(balances) == ["c", "a", "b"]


def test_multiple_expenses_accumulate() -> None:
    expenses = [
        ExpenseShares(payer_id="a", shares=split_equally(3000, ["a", "b", "c"])),
        ExpenseShares(payer_id="b", shares=split_equally(1000, ["a", "b"])),
        ExpenseShares(payer_id="c", shares=split_equally(1, ["a", "b", "c"])),
    ]

    balances = compute_balances(["a", "b", "c"], expenses)

    # a: paid 3000, owes 1000 + 500 + 1 -> 1499
    # b: paid 1000, owes 1000 + 500     -> -500
    # c: paid 1,    owes 1000           -> -999
    assert balances == {"a": 1499, "b": -500, "c": -999}


members = st.lists(st.sampled_from("abcdefgh"), min_size=1, max_size=8, unique=True)


@st.composite
def group_with_expenses(draw: st.DrawFn) -> tuple[list[str], list[ExpenseShares]]:
    member_ids = draw(members)
    expenses = []
    for _ in range(draw(st.integers(min_value=0, max_value=15))):
        payer = draw(st.sampled_from(member_ids))
        split_between = draw(st.lists(st.sampled_from(member_ids), min_size=1, unique=True))
        total = draw(st.integers(min_value=1, max_value=10_000_000))
        expenses.append(ExpenseShares(payer_id=payer, shares=split_equally(total, split_between)))
    return member_ids, expenses


@given(group_with_expenses())
def test_balances_always_sum_to_zero(group: tuple[list[str], list[ExpenseShares]]) -> None:
    member_ids, expenses = group

    balances = compute_balances(member_ids, expenses)

    assert sum(balances.values()) == 0
    assert list(balances) == member_ids
