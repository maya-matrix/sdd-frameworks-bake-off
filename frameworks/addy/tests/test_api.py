from typing import Any

import pytest
from fastapi.testclient import TestClient


def assert_error(response: Any, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    assert body["error"]["message"]


# --- groups -------------------------------------------------------------------------------


def test_create_group_defaults_to_euro_with_no_members(client: TestClient) -> None:
    response = client.post("/groups", json={"name": "Trip"})

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "name", "currency", "members"}
    assert body["name"] == "Trip"
    assert body["currency"] == "EUR"
    assert body["members"] == []


def test_create_group_accepts_explicit_currency(client: TestClient) -> None:
    response = client.post("/groups", json={"name": "Trip", "currency": "USD"})

    assert response.status_code == 201
    assert response.json()["currency"] == "USD"


def test_create_group_trims_name(client: TestClient) -> None:
    response = client.post("/groups", json={"name": "  Trip  "})

    assert response.json()["name"] == "Trip"


@pytest.mark.parametrize("currency", ["usd", "EURO", "EU", "123", 978])
def test_create_group_rejects_invalid_currency(client: TestClient, currency: object) -> None:
    response = client.post("/groups", json={"name": "Trip", "currency": currency})

    assert_error(response, 400, "VALIDATION_ERROR")


@pytest.mark.parametrize(
    "body", [{}, {"name": ""}, {"name": "   "}, {"name": "x" * 101}, {"name": 5}]
)
def test_create_group_rejects_invalid_name(client: TestClient, body: dict[str, object]) -> None:
    assert_error(client.post("/groups", json=body), 400, "VALIDATION_ERROR")


def test_create_group_accepts_name_of_maximum_length(client: TestClient) -> None:
    assert client.post("/groups", json={"name": "x" * 100}).status_code == 201


def test_malformed_json_is_a_validation_error(client: TestClient) -> None:
    response = client.post(
        "/groups", content=b'{"name": ', headers={"content-type": "application/json"}
    )

    assert_error(response, 400, "VALIDATION_ERROR")


def test_get_group_returns_created_group(client: TestClient) -> None:
    created = client.post("/groups", json={"name": "Trip"}).json()

    response = client.get(f"/groups/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_group_is_not_found(client: TestClient) -> None:
    assert_error(client.get("/groups/does-not-exist"), 404, "GROUP_NOT_FOUND")


def test_unknown_route_uses_error_shape(client: TestClient) -> None:
    assert_error(client.get("/nope"), 404, "NOT_FOUND")


# --- members ------------------------------------------------------------------------------


def create_group(client: TestClient, name: str = "Trip") -> str:
    group_id: str = client.post("/groups", json={"name": name}).json()["id"]
    return group_id


def test_add_member_returns_member(client: TestClient) -> None:
    group_id = create_group(client)

    response = client.post(f"/groups/{group_id}/members", json={"name": "  Ana "})

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "name"}
    assert body["name"] == "Ana"


def test_group_lists_members_in_join_order(client: TestClient) -> None:
    group_id = create_group(client)
    added = [
        client.post(f"/groups/{group_id}/members", json={"name": name}).json()
        for name in ["Zed", "Ana", "Bo"]
    ]

    group = client.get(f"/groups/{group_id}").json()

    assert group["members"] == added


def test_duplicate_member_name_conflicts_ignoring_case(client: TestClient) -> None:
    group_id = create_group(client)
    client.post(f"/groups/{group_id}/members", json={"name": "Ana"})

    response = client.post(f"/groups/{group_id}/members", json={"name": "ana"})

    assert_error(response, 409, "DUPLICATE_MEMBER")


def test_same_member_name_allowed_in_another_group(client: TestClient) -> None:
    first, second = create_group(client, "Trip"), create_group(client, "Flat")
    client.post(f"/groups/{first}/members", json={"name": "Ana"})

    response = client.post(f"/groups/{second}/members", json={"name": "Ana"})

    assert response.status_code == 201


@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": " "}, {"name": "x" * 101}])
def test_add_member_rejects_invalid_name(client: TestClient, body: dict[str, object]) -> None:
    group_id = create_group(client)

    assert_error(client.post(f"/groups/{group_id}/members", json=body), 400, "VALIDATION_ERROR")


def test_add_member_to_unknown_group_is_not_found(client: TestClient) -> None:
    response = client.post("/groups/missing/members", json={"name": "Ana"})

    assert_error(response, 404, "GROUP_NOT_FOUND")
