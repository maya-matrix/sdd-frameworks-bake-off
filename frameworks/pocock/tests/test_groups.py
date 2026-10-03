import pytest
from fastapi.testclient import TestClient


def test_create_group_with_initial_members(client: TestClient) -> None:
    response = client.post(
        "/groups", json={"name": "Ski trip", "currency": "EUR", "members": ["Alice", "Bob"]}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Ski trip"
    assert body["currency"] == "EUR"
    assert body["id"]
    assert body["created_at"]
    assert [m["name"] for m in body["members"]] == ["Alice", "Bob"]
    assert all(m["id"] for m in body["members"])


def test_get_group_returns_members_in_join_order(client: TestClient) -> None:
    created = client.post(
        "/groups", json={"name": "Flat", "currency": "GBP", "members": ["Cara", "Ann", "Ben"]}
    ).json()

    response = client.get(f"/groups/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created
    assert [m["name"] for m in response.json()["members"]] == ["Cara", "Ann", "Ben"]


def test_get_unknown_group_is_404(client: TestClient) -> None:
    assert client.get("/groups/does-not-exist").status_code == 404


@pytest.mark.parametrize("currency", ["usd", "JPY", "KWD", "XXX", "EURO", ""])
def test_currency_must_be_a_supported_two_decimal_iso_code(
    client: TestClient, currency: str
) -> None:
    response = client.post("/groups", json={"name": "Trip", "currency": currency})

    assert response.status_code == 422


@pytest.mark.parametrize("currency", ["EUR", "USD", "GBP", "CHF"])
def test_common_two_decimal_currencies_are_accepted(client: TestClient, currency: str) -> None:
    response = client.post("/groups", json={"name": "Trip", "currency": currency})

    assert response.status_code == 201


@pytest.mark.parametrize("name", ["", "  ", "x" * 101])
def test_group_name_must_be_1_to_100_characters(client: TestClient, name: str) -> None:
    response = client.post("/groups", json={"name": name, "currency": "EUR"})

    assert response.status_code == 422
