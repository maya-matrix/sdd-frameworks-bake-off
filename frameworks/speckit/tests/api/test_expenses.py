import uuid

import pytest


def _post(client, group_id, **payload):
    return client.post(f"/groups/{group_id}/expenses", json=payload)


def _expense(ids, payer="Ana", amount="30.00", description="Dinner", participants=("Ana", "Ben", "Cleo")):
    return {
        "payer_id": ids[payer],
        "amount": amount,
        "description": description,
        "participant_ids": [ids[p] for p in participants],
    }


def _shares(body):
    return [s["amount"] for s in body["shares"]]


def _expenses(client, group_id):
    return client.get(f"/groups/{group_id}/expenses").json()["expenses"]


def test_record_even_expense(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    resp = _post(client, group_id, **_expense(ids))
    assert resp.status_code == 201
    body = resp.json()
    uuid.UUID(body["id"])
    assert body["payer_id"] == ids["Ana"]
    assert body["amount"] == "30.00"
    assert body["description"] == "Dinner"
    assert body["shares"] == [{"member_id": ids[n], "amount": "10.00"} for n in ("Ana", "Ben", "Cleo")]
    assert body["created_at"]


def test_uneven_split_gives_leftover_cent_to_first_listed(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    body = _post(client, group_id, **_expense(ids, amount="10.00", description="Taxi")).json()
    assert _shares(body) == ["3.34", "3.33", "3.33"]
    assert body["shares"][0]["member_id"] == ids["Ana"]


def test_participant_order_determines_leftover(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    body = _post(client, group_id, **_expense(ids, amount="10.00", participants=("Cleo", "Ana", "Ben"))).json()
    assert body["shares"][0] == {"member_id": ids["Cleo"], "amount": "3.34"}
    assert _shares(body) == ["3.34", "3.33", "3.33"]


def test_one_cent_split_three_ways(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    body = _post(client, group_id, **_expense(ids, amount="0.01")).json()
    assert _shares(body) == ["0.01", "0.00", "0.00"]


def test_payer_need_not_participate(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    resp = _post(client, group_id, **_expense(ids, payer="Ben", amount="20.00", participants=("Ana", "Cleo")))
    assert resp.status_code == 201
    assert _shares(resp.json()) == ["10.00", "10.00"]


def test_payer_as_only_participant(client, make_group):
    group_id, ids = make_group("Ana", "Ben")
    resp = _post(client, group_id, **_expense(ids, participants=("Ana",)))
    assert resp.status_code == 201
    assert _shares(resp.json()) == ["30.00"]


def test_max_amount_accepted(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    body = _post(client, group_id, **_expense(ids, amount="1000000000.00")).json()
    assert _shares(body) == ["333333333.34", "333333333.33", "333333333.33"]


def test_description_is_trimmed(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    body = _post(client, group_id, **_expense(ids, description="  Lunch ")).json()
    assert body["description"] == "Lunch"


def test_list_expenses_in_recording_order(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    first = _post(client, group_id, **_expense(ids, description="First")).json()
    second = _post(client, group_id, **_expense(ids, description="Second", amount="10.00")).json()
    assert _expenses(client, group_id) == [first, second]


def test_list_expenses_empty(client, make_group):
    group_id, _ = make_group("Ana")
    assert _expenses(client, group_id) == []


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"amount": "0.00"}, "amount"),
        ({"amount": "-5.00"}, "amount"),
        ({"amount": "10.005"}, "amount"),
        ({"amount": "10.5"}, "amount"),
        ({"amount": "10"}, "amount"),
        ({"amount": 10.0}, "amount"),
        ({"amount": 10}, "amount"),
        ({"amount": "1000000000.01"}, "amount"),
        ({"description": ""}, "description"),
        ({"description": "   "}, "description"),
        ({"description": "x" * 201}, "description"),
        ({"participant_ids": []}, "participant_ids"),
        ({"extra": True}, "extra"),
    ],
)
def test_invalid_expense_rejected(client, make_group, override, field):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    payload = {**_expense(ids), **override}
    resp = _post(client, group_id, **payload)
    assert resp.status_code == 422, resp.text
    error = resp.json()["error"]
    assert error["code"] == "validation_error"
    assert error["field"] == field
    assert _expenses(client, group_id) == []


def test_missing_field_rejected(client, make_group):
    group_id, ids = make_group("Ana", "Ben")
    payload = _expense(ids, participants=("Ana", "Ben"))
    del payload["payer_id"]
    resp = _post(client, group_id, **payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["field"] == "payer_id"


def test_duplicate_participants_rejected(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    resp = _post(client, group_id, **_expense(ids, participants=("Ana", "Ben", "Ana")))
    assert resp.status_code == 422
    assert resp.json()["error"]["field"] == "participant_ids"
    assert _expenses(client, group_id) == []


def test_unknown_payer(client, make_group):
    group_id, ids = make_group("Ana", "Ben")
    payload = {**_expense(ids, participants=("Ana", "Ben")), "payer_id": str(uuid.uuid4())}
    resp = _post(client, group_id, **payload)
    assert resp.status_code == 404
    error = resp.json()["error"]
    assert error["code"] == "not_found"
    assert error["field"] == "payer_id"
    assert payload["payer_id"] in error["message"]
    assert _expenses(client, group_id) == []


def test_participant_from_another_group(client, make_group):
    group_id, ids = make_group("Ana", "Ben")
    _, other = make_group("Zed")
    payload = _expense(ids, participants=("Ana", "Ben"))
    payload["participant_ids"].append(other["Zed"])
    resp = _post(client, group_id, **payload)
    assert resp.status_code == 404
    error = resp.json()["error"]
    assert error["field"] == "participant_ids"
    assert other["Zed"] in error["message"]
    assert _expenses(client, group_id) == []


def test_expense_in_unknown_group(client, make_group):
    _, ids = make_group("Ana")
    resp = _post(client, str(uuid.uuid4()), **_expense(ids, participants=("Ana",)))
    assert resp.status_code == 404
    assert client.get(f"/groups/{uuid.uuid4()}/expenses").status_code == 404


def test_description_of_200_chars_accepted(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    resp = _post(client, group_id, **_expense(ids, description="x" * 200))
    assert resp.status_code == 201
    assert resp.json()["description"] == "x" * 200


@pytest.mark.parametrize("bad", [[1], [None], [["nested"]]])
def test_non_string_participant_ids_rejected(client, make_group, bad):
    group_id, ids = make_group("Ana", "Ben")
    resp = _post(client, group_id, **{**_expense(ids, participants=("Ana",)), "participant_ids": bad})
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "validation_error"
    assert error["field"] == "participant_ids"
    assert _expenses(client, group_id) == []


def test_malformed_expense_body_rejected(client, make_group):
    group_id, _ = make_group("Ana")
    resp = client.post(f"/groups/{group_id}/expenses", content=b"{bad", headers={"content-type": "application/json"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
    assert _expenses(client, group_id) == []


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("10.005", "amount: invalid amount '10.005': expected exactly two decimals, e.g. \"10.00\""),
        ("0.00", "amount: amount must be at least 0.01"),
        (10.0, 'amount: must be a string with exactly two decimals, e.g. "10.00" (numbers are not accepted)'),
    ],
)
def test_validation_messages_are_clean(client, make_group, amount, expected):
    group_id, ids = make_group("Ana")
    resp = _post(client, group_id, **{**_expense(ids, participants=("Ana",)), "amount": amount})
    assert resp.status_code == 422
    assert resp.json()["error"]["message"] == expected
