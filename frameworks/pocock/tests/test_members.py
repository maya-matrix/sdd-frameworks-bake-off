import pytest
from fastapi.testclient import TestClient

from tests.conftest import create_group


def test_add_member_to_existing_group(client: TestClient) -> None:
    group = create_group(client, ["Alice"])

    response = client.post(f"/groups/{group['id']}/members", json={"name": "Bob"})

    assert response.status_code == 201
    assert response.json()["name"] == "Bob"
    members = client.get(f"/groups/{group['id']}").json()["members"]
    assert [m["name"] for m in members] == ["Alice", "Bob"]
    assert members[1]["id"] == response.json()["id"]


def test_add_member_to_unknown_group_is_404(client: TestClient) -> None:
    response = client.post("/groups/nope/members", json={"name": "Bob"})

    assert response.status_code == 404


@pytest.mark.parametrize("name", ["", "   ", "x" * 51])
def test_member_name_must_be_1_to_50_characters(client: TestClient, name: str) -> None:
    group = create_group(client, [])

    response = client.post(f"/groups/{group['id']}/members", json={"name": name})

    assert response.status_code == 422


def test_member_name_of_50_characters_is_accepted(client: TestClient) -> None:
    group = create_group(client, [])

    response = client.post(f"/groups/{group['id']}/members", json={"name": "x" * 50})

    assert response.status_code == 201


def test_member_names_are_unique_ignoring_case(client: TestClient) -> None:
    group = create_group(client, ["Alice"])

    response = client.post(f"/groups/{group['id']}/members", json={"name": "aLiCe"})

    assert response.status_code == 409


def test_same_name_may_exist_in_different_groups(client: TestClient) -> None:
    create_group(client, ["Alice"])
    other = create_group(client, [])

    response = client.post(f"/groups/{other['id']}/members", json={"name": "Alice"})

    assert response.status_code == 201


def test_initial_members_must_have_unique_names(client: TestClient) -> None:
    response = client.post(
        "/groups", json={"name": "Trip", "currency": "EUR", "members": ["Bob", "BOB"]}
    )

    assert response.status_code == 409


def test_initial_member_names_are_validated(client: TestClient) -> None:
    response = client.post(
        "/groups", json={"name": "Trip", "currency": "EUR", "members": ["Bob", ""]}
    )

    assert response.status_code == 422
