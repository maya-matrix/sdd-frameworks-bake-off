import uuid

from splitit.money import parse_money


def _signed(text):
    return -parse_money(text[1:]) if text.startswith("-") else parse_money(text)


def _record(client, group_id, ids, payer, amount, participants):
    resp = client.post(
        f"/groups/{group_id}/expenses",
        json={
            "payer_id": ids[payer],
            "amount": amount,
            "description": "x",
            "participant_ids": [ids[p] for p in participants],
        },
    )
    assert resp.status_code == 201, resp.text


def _balances(client, group_id):
    resp = client.get(f"/groups/{group_id}/balances")
    assert resp.status_code == 200
    return resp.json()["balances"]


def test_balances_spec_scenario(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    _record(client, group_id, ids, "Ana", "30.00", ["Ana", "Ben", "Cleo"])
    assert _balances(client, group_id) == [
        {"member_id": ids["Ana"], "name": "Ana", "balance": "20.00"},
        {"member_id": ids["Ben"], "name": "Ben", "balance": "-10.00"},
        {"member_id": ids["Cleo"], "name": "Cleo", "balance": "-10.00"},
    ]


def test_uneven_balances_sum_to_zero(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    _record(client, group_id, ids, "Ana", "10.00", ["Ana", "Ben", "Cleo"])
    balances = _balances(client, group_id)
    assert [b["balance"] for b in balances] == ["6.66", "-3.33", "-3.33"]
    assert sum(_signed(b["balance"]) for b in balances) == 0


def test_members_without_expenses_show_zero(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Dee")
    _record(client, group_id, ids, "Ana", "10.00", ["Ana", "Ben"])
    assert [b["balance"] for b in _balances(client, group_id)] == ["5.00", "-5.00", "0.00"]


def test_no_expenses_all_zero(client, make_group):
    group_id, _ = make_group("Ana", "Ben")
    assert [b["balance"] for b in _balances(client, group_id)] == ["0.00", "0.00"]


def test_balances_unknown_group(client):
    resp = client.get(f"/groups/{uuid.uuid4()}/balances")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
