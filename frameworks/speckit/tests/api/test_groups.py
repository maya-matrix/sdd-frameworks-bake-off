import uuid

import pytest


def test_create_group(client):
    resp = client.post("/groups", json={"name": "Lisbon trip"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Lisbon trip"
    assert body["members"] == []
    uuid.UUID(body["id"])


def test_get_group(client):
    created = client.post("/groups", json={"name": "Lisbon trip"}).json()
    resp = client.get(f"/groups/{created['id']}")
    assert resp.status_code == 200
    assert resp.json() == created


def test_group_ids_are_unique(client):
    a = client.post("/groups", json={"name": "A"}).json()["id"]
    b = client.post("/groups", json={"name": "A"}).json()["id"]
    assert a != b


def test_group_name_is_trimmed(client):
    resp = client.post("/groups", json={"name": "  Trip  "})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Trip"


def test_group_name_of_100_chars_accepted(client):
    assert client.post("/groups", json={"name": "x" * 100}).status_code == 201


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"name": ""}, "name"),
        ({"name": "   "}, "name"),
        ({"name": "x" * 101}, "name"),
        ({}, "name"),
        ({"name": 5}, "name"),
        ({"name": "Trip", "extra": 1}, "extra"),
    ],
)
def test_create_group_validation(client, payload, field):
    resp = client.post("/groups", json=payload)
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "validation_error"
    assert error["field"] == field
    assert error["message"]


def test_get_unknown_group(client):
    resp = client.get(f"/groups/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"content": b"{bad", "headers": {"content-type": "application/json"}},
        {"content": b"", "headers": {"content-type": "application/json"}},
        {"json": ["Trip"]},
    ],
    ids=["malformed-json", "empty-body", "array-body"],
)
def test_unparseable_group_body_rejected(client, kwargs):
    resp = client.post("/groups", **kwargs)
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"]
    assert "Value error" not in error["message"]


def test_create_group_with_initial_members(client):
    resp = client.post("/groups", json={"name": "Trip", "members": [" Ana ", "Ben", "Cleo"]})
    assert resp.status_code == 201
    body = resp.json()
    assert [m["name"] for m in body["members"]] == ["Ana", "Ben", "Cleo"]
    assert len({m["id"] for m in body["members"]}) == 3
    assert client.get(f"/groups/{body['id']}").json() == body


def test_initial_members_can_be_extended(client):
    group = client.post("/groups", json={"name": "Trip", "members": ["Ana"]}).json()
    assert client.post(f"/groups/{group['id']}/members", json={"name": "ana"}).status_code == 409
    assert client.post(f"/groups/{group['id']}/members", json={"name": "Ben"}).status_code == 201


@pytest.mark.parametrize(
    ("members", "status", "code"),
    [
        (["Ana", "ana"], 409, "duplicate_member_name"),
        (["Ana", " ANA "], 409, "duplicate_member_name"),
        (["Ana", ""], 422, "validation_error"),
        (["x" * 101], 422, "validation_error"),
        ([1], 422, "validation_error"),
        ([f"M{i}" for i in range(21)], 422, "validation_error"),
        ("Ana", 422, "validation_error"),
    ],
)
def test_invalid_initial_members_reject_whole_request(client, members, status, code):
    resp = client.post("/groups", json={"name": "Trip", "members": members})
    assert resp.status_code == status, resp.text
    error = resp.json()["error"]
    assert error["code"] == code
    assert error["field"] == "members"
    assert "id" not in resp.json()
    assert client.app.state.repository._groups == {}, "rejected request must store nothing"


def test_twenty_initial_members_accepted(client):
    resp = client.post("/groups", json={"name": "Trip", "members": [f"M{i}" for i in range(20)]})
    assert resp.status_code == 201
    assert len(resp.json()["members"]) == 20


def test_sc004_four_requests_end_to_end(client):
    """SC-004: create group with members, record an expense, see balances — 4 requests or fewer."""
    requests = 0

    group = client.post("/groups", json={"name": "Lisbon trip", "members": ["Ana", "Ben", "Cleo"]}).json()
    requests += 1
    ids = {m["name"]: m["id"] for m in group["members"]}

    resp = client.post(
        f"/groups/{group['id']}/expenses",
        json={"payer_id": ids["Ana"], "amount": "10.00", "description": "Taxi", "participant_ids": list(ids.values())},
    )
    requests += 1
    assert resp.status_code == 201

    balances = client.get(f"/groups/{group['id']}/balances").json()["balances"]
    requests += 1

    assert [b["balance"] for b in balances] == ["6.66", "-3.33", "-3.33"]
    assert requests <= 4
