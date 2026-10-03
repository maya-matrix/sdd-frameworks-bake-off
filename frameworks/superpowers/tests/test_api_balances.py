import random

from sqlalchemy import event

from app import repository
from tests.conftest import to_cents


def record(client, group_id, payer_id, amount, split_between, description="Expense"):
    response = client.post(
        f"/groups/{group_id}/expenses",
        json={"payer_id": payer_id, "amount": amount, "description": description, "split_between": split_between},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_balances_start_at_zero_for_every_member(client, make_group):
    group_id, (alice, bob) = make_group("Alice", "Bob", currency="GBP")
    assert client.get(f"/groups/{group_id}/balances").json() == {
        "currency": "GBP",
        "balances": [
            {"member_id": alice, "name": "Alice", "balance": "0.00"},
            {"member_id": bob, "name": "Bob", "balance": "0.00"},
        ],
    }


def test_ten_euros_three_ways_balances_to_exactly_zero(client, make_group):
    group_id, (alice, bob, carol) = make_group("Alice", "Bob", "Carol")
    record(client, group_id, alice, "10.00", [alice, bob, carol])
    balances = client.get(f"/groups/{group_id}/balances").json()["balances"]
    assert [b["balance"] for b in balances] == ["6.66", "-3.33", "-3.33"]
    assert sum(to_cents(b["balance"]) for b in balances) == 0


def test_settle_up_for_ten_euros_three_ways(client, make_group):
    group_id, (alice, bob, carol) = make_group("Alice", "Bob", "Carol")
    record(client, group_id, alice, "10.00", [alice, bob, carol])
    assert client.get(f"/groups/{group_id}/settle-up").json() == {
        "currency": "EUR",
        "optimal": True,
        "transfers": [
            {"from_member_id": bob, "to_member_id": alice, "amount": "3.33"},
            {"from_member_id": carol, "to_member_id": alice, "amount": "3.33"},
        ],
    }


def test_settle_up_with_no_debts(client, make_group):
    group_id, _ = make_group("Alice", "Bob")
    assert client.get(f"/groups/{group_id}/settle-up").json() == {
        "currency": "EUR",
        "optimal": True,
        "transfers": [],
    }


def test_settle_up_uses_fewer_transfers_than_greedy(client, make_group):
    group_id, (a, b, c, d, e) = make_group("A", "B", "C", "D", "E")
    record(client, group_id, a, "4.00", [d, e])  # A +4, D -2, E -2
    record(client, group_id, b, "3.00", [c])  # B +3, C -3
    assert client.get(f"/groups/{group_id}/settle-up").json()["transfers"] == [
        {"from_member_id": c, "to_member_id": b, "amount": "3.00"},
        {"from_member_id": d, "to_member_id": a, "amount": "2.00"},
        {"from_member_id": e, "to_member_id": a, "amount": "2.00"},
    ]


def test_many_uneven_expenses_stay_exact_and_settle_completely(client, make_group):
    rng = random.Random(42)
    group_id, members = make_group("A", "B", "C", "D", "E", "F")
    for _ in range(60):
        payer = rng.choice(members)
        split = rng.sample(members, rng.randint(1, len(members)))
        amount = f"{rng.randint(0, 500)}.{rng.randint(0, 99):02d}"
        if to_cents(amount) == 0:
            continue
        record(client, group_id, payer, amount, split)

    balances = {
        b["member_id"]: to_cents(b["balance"]) for b in client.get(f"/groups/{group_id}/balances").json()["balances"]
    }
    assert sum(balances.values()) == 0

    settle = client.get(f"/groups/{group_id}/settle-up").json()
    assert settle["optimal"] is True
    for transfer in settle["transfers"]:
        balances[transfer["from_member_id"]] += to_cents(transfer["amount"])
        balances[transfer["to_member_id"]] -= to_cents(transfer["amount"])
    assert all(cents == 0 for cents in balances.values())
    assert len(settle["transfers"]) <= len(members) - 1


def test_unknown_group_is_404(client):
    assert client.get("/groups/999/balances").status_code == 404
    assert client.get("/groups/999/settle-up").status_code == 404


def test_balances_stay_consistent_when_expenses_are_committed_mid_read(client, make_group):
    group_id, (alice, bob) = make_group("Alice", "Bob")
    record(client, group_id, alice, "10.00", [alice, bob])
    session_factory = client.app.state.session_factory
    engine = session_factory.kw["bind"]
    concurrent_commits = 0
    inside_hook = False

    def commit_expense_before_each_sum(_conn, _cursor, statement, *_args):
        nonlocal concurrent_commits, inside_hook
        if inside_hook or "sum(" not in statement.lower():
            return
        inside_hook = True
        try:
            with session_factory() as other:
                repository.record_expense(
                    other, group_id, payer_id=bob, amount_cents=1000, description="Race", split_between=[alice, bob]
                )
            concurrent_commits += 1
        finally:
            inside_hook = False

    event.listen(engine, "before_cursor_execute", commit_expense_before_each_sum)
    try:
        balances = client.get(f"/groups/{group_id}/balances").json()["balances"]
        settle = client.get(f"/groups/{group_id}/settle-up")
    finally:
        event.remove(engine, "before_cursor_execute", commit_expense_before_each_sum)

    assert concurrent_commits >= 2
    assert sum(to_cents(b["balance"]) for b in balances) == 0
    assert settle.status_code == 200
