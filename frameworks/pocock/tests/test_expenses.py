from typing import Any

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.conftest import create_group, member_ids


def record_expense(
    client: TestClient,
    group_id: str,
    payer_id: str,
    amount: Any,
    participant_ids: list[str],
    description: str = "Dinner",
) -> Any:
    return client.post(
        f"/groups/{group_id}/expenses",
        json={
            "payer_id": payer_id,
            "amount": amount,
            "description": description,
            "participant_ids": participant_ids,
        },
    )


def shares_by_name(expense: dict[str, Any], ids: dict[str, str]) -> dict[str, int]:
    names = {member_id: name for name, member_id in ids.items()}
    return {names[s["member_id"]]: s["amount"] for s in expense["shares"]}


def test_record_expense_split_equally(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob"])
    ids = member_ids(group)

    response = record_expense(client, group["id"], ids["Alice"], 1000, [ids["Alice"], ids["Bob"]])

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["created_at"]
    assert body["payer_id"] == ids["Alice"]
    assert body["amount"] == 1000
    assert body["description"] == "Dinner"
    assert shares_by_name(body, ids) == {"Alice": 500, "Bob": 500}


def test_remainder_goes_to_earliest_joined_participants_whatever_the_request_order(
    client: TestClient,
) -> None:
    group = create_group(client, ["Alice", "Bob", "Cara"])
    ids = member_ids(group)

    response = record_expense(
        client, group["id"], ids["Bob"], 1000, [ids["Cara"], ids["Bob"], ids["Alice"]]
    )

    assert shares_by_name(response.json(), ids) == {"Alice": 334, "Bob": 333, "Cara": 333}


def test_remainder_of_two_goes_to_the_first_two_joined(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob", "Cara", "Dan"])
    ids = member_ids(group)

    response = record_expense(
        client, group["id"], ids["Alice"], 1002, [ids["Dan"], ids["Cara"], ids["Bob"]]
    )

    assert shares_by_name(response.json(), ids) == {"Bob": 334, "Cara": 334, "Dan": 334}

    response = record_expense(client, group["id"], ids["Alice"], 1001, list(ids.values()))

    assert shares_by_name(response.json(), ids) == {
        "Alice": 251, "Bob": 250, "Cara": 250, "Dan": 250,
    }  # fmt: skip


def test_payer_need_not_be_a_participant(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob", "Cara"])
    ids = member_ids(group)

    response = record_expense(client, group["id"], ids["Alice"], 3000, [ids["Bob"], ids["Cara"]])

    assert response.status_code == 201
    assert shares_by_name(response.json(), ids) == {"Bob": 1500, "Cara": 1500}


def test_amount_smaller_than_participant_count_gives_some_zero_shares(
    client: TestClient,
) -> None:
    group = create_group(client, ["Alice", "Bob", "Cara"])
    ids = member_ids(group)

    response = record_expense(client, group["id"], ids["Alice"], 1, list(ids.values()))

    assert shares_by_name(response.json(), ids) == {"Alice": 1, "Bob": 0, "Cara": 0}


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
@given(amount=st.integers(1, 10**12), participant_count=st.integers(1, 7))
def test_shares_always_sum_exactly_to_the_amount(
    client: TestClient, amount: int, participant_count: int
) -> None:
    group = create_group(client, [f"M{i}" for i in range(7)])
    participants = [m["id"] for m in group["members"][:participant_count]]

    response = record_expense(client, group["id"], participants[0], amount, participants)

    shares = [s["amount"] for s in response.json()["shares"]]
    assert sum(shares) == amount
    assert max(shares) - min(shares) <= 1


def test_list_expenses_returns_them_with_the_same_shares(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob", "Cara"])
    ids = member_ids(group)
    first = record_expense(client, group["id"], ids["Alice"], 1000, list(ids.values())).json()
    second = record_expense(
        client, group["id"], ids["Bob"], 250, [ids["Cara"]], description="Taxi"
    ).json()

    response = client.get(f"/groups/{group['id']}/expenses")

    assert response.status_code == 200
    assert response.json() == [first, second]


def test_expenses_are_listed_per_group(client: TestClient) -> None:
    group = create_group(client, ["Alice"])
    other = create_group(client, ["Zed"])
    ids = member_ids(group)
    record_expense(client, group["id"], ids["Alice"], 100, [ids["Alice"]])

    assert client.get(f"/groups/{other['id']}/expenses").json() == []


def test_expenses_of_unknown_group_are_404(client: TestClient) -> None:
    assert client.get("/groups/nope/expenses").status_code == 404
    assert record_expense(client, "nope", "x", 100, ["x"]).status_code == 404


@pytest.mark.parametrize("amount", [0, -100, 10.5, "10.00", None])
def test_amount_must_be_a_positive_integer(client: TestClient, amount: Any) -> None:
    group = create_group(client, ["Alice"])
    ids = member_ids(group)

    response = record_expense(client, group["id"], ids["Alice"], amount, [ids["Alice"]])

    assert response.status_code == 422


@pytest.mark.parametrize("description", ["", "   ", "x" * 201])
def test_description_must_be_1_to_200_characters(client: TestClient, description: str) -> None:
    group = create_group(client, ["Alice"])
    ids = member_ids(group)

    response = record_expense(
        client, group["id"], ids["Alice"], 100, [ids["Alice"]], description=description
    )

    assert response.status_code == 422


def test_there_must_be_at_least_one_participant(client: TestClient) -> None:
    group = create_group(client, ["Alice"])
    ids = member_ids(group)

    response = record_expense(client, group["id"], ids["Alice"], 100, [])

    assert response.status_code == 422


def test_participants_must_not_repeat(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob"])
    ids = member_ids(group)

    response = record_expense(client, group["id"], ids["Alice"], 100, [ids["Bob"], ids["Bob"]])

    assert response.status_code == 422


def test_payer_and_participants_must_be_members_of_this_group(client: TestClient) -> None:
    group = create_group(client, ["Alice"])
    other = create_group(client, ["Zed"])
    ids = member_ids(group)
    zed = member_ids(other)["Zed"]

    assert record_expense(client, group["id"], zed, 100, [ids["Alice"]]).status_code == 422
    assert record_expense(client, group["id"], ids["Alice"], 100, [zed]).status_code == 422
    assert record_expense(client, group["id"], ids["Alice"], 100, ["nope"]).status_code == 422
    assert client.get(f"/groups/{group['id']}/expenses").json() == []
