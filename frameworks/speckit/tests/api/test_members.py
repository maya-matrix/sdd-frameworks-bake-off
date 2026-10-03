import uuid

import pytest


def _members(client, group_id):
    return client.get(f"/groups/{group_id}").json()["members"]


def test_add_members(client, make_group):
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    assert len(set(ids.values())) == 3
    for member_id in ids.values():
        uuid.UUID(member_id)
    members = _members(client, group_id)
    assert members == [{"id": ids[n], "name": n} for n in ("Ana", "Ben", "Cleo")]


def test_add_member_response(client, make_group):
    group_id, _ = make_group()
    resp = client.post(f"/groups/{group_id}/members", json={"name": "  Ana "})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Ana"


@pytest.mark.parametrize("dup", ["Ana", "ana", " ANA "])
def test_duplicate_member_name_rejected(client, make_group, dup):
    group_id, _ = make_group("Ana")
    resp = client.post(f"/groups/{group_id}/members", json={"name": dup})
    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "duplicate_member_name"
    assert error["field"] == "name"
    assert len(_members(client, group_id)) == 1


def test_same_name_allowed_in_different_groups(client, make_group):
    make_group("Ana")
    make_group("Ana")


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_invalid_member_name(client, make_group, name):
    group_id, _ = make_group()
    resp = client.post(f"/groups/{group_id}/members", json={"name": name})
    assert resp.status_code == 422
    assert resp.json()["error"]["field"] == "name"
    assert _members(client, group_id) == []


def test_add_member_to_unknown_group(client):
    resp = client.post(f"/groups/{uuid.uuid4()}/members", json={"name": "Ana"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_member_limit_is_20(client, make_group):
    group_id, _ = make_group(*[f"M{i}" for i in range(20)])
    resp = client.post(f"/groups/{group_id}/members", json={"name": "M20"})
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "validation_error"
    assert "20" in error["message"]
    assert len(_members(client, group_id)) == 20


def test_extra_member_field_rejected(client, make_group):
    group_id, _ = make_group()
    resp = client.post(f"/groups/{group_id}/members", json={"name": "Ana", "role": "admin"})
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "validation_error"
    assert error["field"] == "role"
    assert _members(client, group_id) == []
