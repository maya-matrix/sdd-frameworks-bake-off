import uuid

from splitit.money import parse_money


def _signed(text):
    return -parse_money(text[1:]) if text.startswith("-") else parse_money(text)


def _record(client, group_id, ids, payer, amount, participants):
    resp = client.post(
        f"/groups/{group_id}/expenses",
        json={"payer_id": ids[payer], "amount": amount, "description": "x", "participant_ids": [ids[p] for p in participants]},
    )
    assert resp.status_code == 201, resp.text


def _settle(client, group_id):
    resp = client.get(f"/groups/{group_id}/settle-up")
    assert resp.status_code == 200
    return resp.json()["transfers"]


def _balances(client, group_id):
    return {b["member_id"]: _signed(b["balance"]) for b in client.get(f"/groups/{group_id}/balances").json()["balances"]}


def test_spec_scenario_one(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    _record(client, group_id, ids, "Ana", "30.00", ["Ana", "Ben", "Cleo"])
    assert _settle(client, group_id) == [
        {"from_member_id": ids["Ben"], "to_member_id": ids["Ana"], "amount": "10.00"},
        {"from_member_id": ids["Cleo"], "to_member_id": ids["Ana"], "amount": "10.00"},
    ]


def test_spec_scenario_two_independent_pairs(client, make_group):
    group_id, ids = make_group("A", "B", "C", "D")
    _record(client, group_id, ids, "A", "5.00", ["B"])
    _record(client, group_id, ids, "C", "7.00", ["D"])
    assert _settle(client, group_id) == [
        {"from_member_id": ids["B"], "to_member_id": ids["A"], "amount": "5.00"},
        {"from_member_id": ids["D"], "to_member_id": ids["C"], "amount": "7.00"},
    ]


def test_spec_scenario_all_settled(client, make_group):
    group_id, ids = make_group("Ana", "Ben")
    assert _settle(client, group_id) == []
    _record(client, group_id, ids, "Ana", "10.00", ["Ana"])
    assert _settle(client, group_id) == []


def test_transfers_clear_uneven_balances(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo", "Dee")
    _record(client, group_id, ids, "Ana", "10.00", ["Ana", "Ben", "Cleo"])
    _record(client, group_id, ids, "Ben", "7.01", ["Cleo", "Dee", "Ana"])
    _record(client, group_id, ids, "Dee", "0.01", ["Ana", "Ben", "Cleo", "Dee"])
    balances = _balances(client, group_id)
    for t in _settle(client, group_id):
        amount = parse_money(t["amount"])
        assert amount > 0
        balances[t["from_member_id"]] += amount
        balances[t["to_member_id"]] -= amount
    assert all(v == 0 for v in balances.values())


def test_settle_up_is_read_only(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    _record(client, group_id, ids, "Ana", "10.00", ["Ana", "Ben", "Cleo"])
    before = client.get(f"/groups/{group_id}/balances").json()
    first = _settle(client, group_id)
    second = _settle(client, group_id)
    assert first == second
    assert client.get(f"/groups/{group_id}/balances").json() == before
    assert len(client.get(f"/groups/{group_id}/expenses").json()["expenses"]) == 1


def test_settle_up_unknown_group(client):
    resp = client.get(f"/groups/{uuid.uuid4()}/settle-up")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
