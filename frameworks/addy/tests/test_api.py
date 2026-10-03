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


# --- expenses -----------------------------------------------------------------------------


def create_group_with_members(client: TestClient, *names: str) -> tuple[str, list[str]]:
    group_id = create_group(client)
    member_ids = [
        client.post(f"/groups/{group_id}/members", json={"name": name}).json()["id"]
        for name in names
    ]
    return group_id, member_ids


def test_record_expense_splits_equally_with_remainder_to_first_listed(
    client: TestClient,
) -> None:
    group_id, (a, b, c) = create_group_with_members(client, "Ana", "Bo", "Cy")

    response = client.post(
        f"/groups/{group_id}/expenses",
        json={"payerId": a, "amount": "10.00", "description": "Taxi", "splitBetween": [b, a, c]},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {
        "id",
        "payerId",
        "amount",
        "description",
        "splitType",
        "shares",
        "createdAt",
    }
    assert body["payerId"] == a
    assert body["amount"] == "10.00"
    assert body["description"] == "Taxi"
    assert body["splitType"] == "equal"
    assert body["shares"] == [
        {"memberId": b, "amount": "3.34"},
        {"memberId": a, "amount": "3.33"},
        {"memberId": c, "amount": "3.33"},
    ]
    assert body["createdAt"].endswith("Z")


def test_amount_is_normalized_to_two_decimals(client: TestClient) -> None:
    group_id, (a,) = create_group_with_members(client, "Ana")

    body = client.post(
        f"/groups/{group_id}/expenses",
        json={"payerId": a, "amount": "7.5", "description": "Tea", "splitBetween": [a]},
    ).json()

    assert body["amount"] == "7.50"


def test_payer_does_not_have_to_share_the_expense(client: TestClient) -> None:
    group_id, (a, b) = create_group_with_members(client, "Ana", "Bo")

    body = client.post(
        f"/groups/{group_id}/expenses",
        json={"payerId": a, "amount": "5.00", "description": "Gift", "splitBetween": [b]},
    ).json()

    assert body["shares"] == [{"memberId": b, "amount": "5.00"}]


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": 10.5},
        {"amount": 10},
        {"amount": "1.234"},
        {"amount": "0"},
        {"amount": "-5.00"},
        {"amount": "1000000000.01"},
        {"amount": None},
        {"description": ""},
        {"description": "   "},
        {"description": "x" * 201},
        {"splitBetween": []},
        {"splitBetween": "everyone"},
        {"payerId": None},
    ],
)
def test_record_expense_rejects_invalid_input(
    client: TestClient, overrides: dict[str, object]
) -> None:
    group_id, (a, b) = create_group_with_members(client, "Ana", "Bo")
    body = {"payerId": a, "amount": "10.00", "description": "Taxi", "splitBetween": [a, b]}

    response = client.post(f"/groups/{group_id}/expenses", json=body | overrides)

    assert_error(response, 400, "VALIDATION_ERROR")


def test_record_expense_rejects_duplicate_split_members(client: TestClient) -> None:
    group_id, (a, b) = create_group_with_members(client, "Ana", "Bo")

    response = client.post(
        f"/groups/{group_id}/expenses",
        json={"payerId": a, "amount": "10.00", "description": "Taxi", "splitBetween": [a, b, a]},
    )

    assert_error(response, 400, "VALIDATION_ERROR")


def test_record_expense_rejects_unknown_payer(client: TestClient) -> None:
    group_id, (a,) = create_group_with_members(client, "Ana")

    response = client.post(
        f"/groups/{group_id}/expenses",
        json={"payerId": "ghost", "amount": "1.00", "description": "Tea", "splitBetween": [a]},
    )

    assert_error(response, 400, "UNKNOWN_MEMBER")


def test_record_expense_rejects_member_of_another_group(client: TestClient) -> None:
    group_id, (a,) = create_group_with_members(client, "Ana")
    _, (outsider,) = create_group_with_members(client, "Oz")

    response = client.post(
        f"/groups/{group_id}/expenses",
        json={"payerId": a, "amount": "1.00", "description": "Tea", "splitBetween": [a, outsider]},
    )

    assert_error(response, 400, "UNKNOWN_MEMBER")


def test_record_expense_in_unknown_group_is_not_found(client: TestClient) -> None:
    response = client.post(
        "/groups/missing/expenses",
        json={"payerId": "a", "amount": "1.00", "description": "Tea", "splitBetween": ["a"]},
    )

    assert_error(response, 404, "GROUP_NOT_FOUND")


def test_list_expenses_returns_them_oldest_first(client: TestClient) -> None:
    group_id, (a, b) = create_group_with_members(client, "Ana", "Bo")
    recorded = [
        client.post(
            f"/groups/{group_id}/expenses",
            json={"payerId": a, "amount": amount, "description": d, "splitBetween": [a, b]},
        ).json()
        for amount, d in [("3.00", "first"), ("0.01", "second"), ("99.99", "third")]
    ]

    response = client.get(f"/groups/{group_id}/expenses")

    assert response.status_code == 200
    assert response.json() == {"expenses": recorded}


def test_list_expenses_of_new_group_is_empty(client: TestClient) -> None:
    group_id = create_group(client)

    assert client.get(f"/groups/{group_id}/expenses").json() == {"expenses": []}


def test_list_expenses_of_unknown_group_is_not_found(client: TestClient) -> None:
    assert_error(client.get("/groups/missing/expenses"), 404, "GROUP_NOT_FOUND")
