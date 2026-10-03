from splitit.balances import compute_balances
from splitit.models import Expense, Group, Member, Share, utc_now
from splitit.splitting import split_equally


def _group(*names):
    group = Group(id="g", name="G", created_at=utc_now())
    group.members = [Member(id=n, group_id="g", name=n) for n in names]
    return group


def _add(group, payer, amount, participants):
    shares = tuple(Share(p, a) for p, a in zip(participants, split_equally(amount, len(participants))))
    group.expenses.append(Expense("e", "g", "x", amount, payer, shares, utc_now()))


def test_even_split():
    g = _group("Ana", "Ben", "Cleo")
    _add(g, "Ana", 3000, ["Ana", "Ben", "Cleo"])
    assert compute_balances(g) == {"Ana": 2000, "Ben": -1000, "Cleo": -1000}


def test_uneven_split_conserves_cents():
    g = _group("Ana", "Ben", "Cleo")
    _add(g, "Ana", 1000, ["Ana", "Ben", "Cleo"])
    balances = compute_balances(g)
    assert balances == {"Ana": 666, "Ben": -333, "Cleo": -333}
    assert sum(balances.values()) == 0


def test_payer_only_expense_changes_nothing():
    g = _group("Ana", "Ben")
    _add(g, "Ana", 500, ["Ana"])
    assert compute_balances(g) == {"Ana": 0, "Ben": 0}


def test_no_expenses():
    assert compute_balances(_group("Ana", "Ben")) == {"Ana": 0, "Ben": 0}


def test_multiple_expenses_accumulate():
    g = _group("Ana", "Ben", "Cleo")
    _add(g, "Ana", 3000, ["Ana", "Ben", "Cleo"])
    _add(g, "Ben", 2000, ["Ana", "Cleo"])
    assert compute_balances(g) == {"Ana": 1000, "Ben": 1000, "Cleo": -2000}


def test_keys_in_member_order():
    g = _group("Cleo", "Ana", "Ben")
    _add(g, "Ben", 900, ["Ana"])
    assert list(compute_balances(g)) == ["Cleo", "Ana", "Ben"]
