from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import create_group, member_ids
from tests.test_balances import balances_by_name
from tests.test_expenses import record_expense


def record_payment(
    client: TestClient, group_id: str, from_id: str, to_id: str, amount: Any
) -> Any:
    return client.post(
        f"/groups/{group_id}/payments",
        json={"from_id": from_id, "to_id": to_id, "amount": amount},
    )


def test_payment_reduces_what_the_sender_owes(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob", "Cara"])
    ids = member_ids(group)
    record_expense(client, group["id"], ids["Alice"], 1000, list(ids.values()))

    response = record_payment(client, group["id"], ids["Bob"], ids["Alice"], 333)

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["created_at"]
    assert (body["from_id"], body["to_id"], body["amount"]) == (ids["Bob"], ids["Alice"], 333)
    assert balances_by_name(client, group["id"]) == {"Alice": 333, "Bob": 0, "Cara": -333}


def test_overpaying_flips_the_balances(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob"])
    ids = member_ids(group)
    record_expense(client, group["id"], ids["Alice"], 1000, list(ids.values()))

    record_payment(client, group["id"], ids["Bob"], ids["Alice"], 800)

    assert balances_by_name(client, group["id"]) == {"Alice": -300, "Bob": 300}


def test_list_payments(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob"])
    ids = member_ids(group)
    first = record_payment(client, group["id"], ids["Bob"], ids["Alice"], 100).json()
    second = record_payment(client, group["id"], ids["Alice"], ids["Bob"], 50).json()

    response = client.get(f"/groups/{group['id']}/payments")

    assert response.status_code == 200
    assert response.json() == [first, second]


def test_payments_of_unknown_group_are_404(client: TestClient) -> None:
    assert client.get("/groups/nope/payments").status_code == 404
    assert record_payment(client, "nope", "a", "b", 100).status_code == 404


def test_cannot_pay_yourself(client: TestClient) -> None:
    group = create_group(client, ["Alice"])
    ids = member_ids(group)

    response = record_payment(client, group["id"], ids["Alice"], ids["Alice"], 100)

    assert response.status_code == 422


@pytest.mark.parametrize("amount", [0, -5, 1.5, "1.00", None])
def test_payment_amount_must_be_a_positive_integer(client: TestClient, amount: Any) -> None:
    group = create_group(client, ["Alice", "Bob"])
    ids = member_ids(group)

    response = record_payment(client, group["id"], ids["Bob"], ids["Alice"], amount)

    assert response.status_code == 422


def test_sender_and_recipient_must_be_members_of_this_group(client: TestClient) -> None:
    group = create_group(client, ["Alice"])
    zed = member_ids(create_group(client, ["Zed"]))["Zed"]
    alice = member_ids(group)["Alice"]

    assert record_payment(client, group["id"], zed, alice, 100).status_code == 422
    assert record_payment(client, group["id"], alice, zed, 100).status_code == 422
    assert client.get(f"/groups/{group['id']}/payments").json() == []


def test_balances_sum_to_zero_with_expenses_and_payments(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob", "Cara"])
    ids = member_ids(group)
    record_expense(client, group["id"], ids["Alice"], 1001, list(ids.values()))
    record_expense(client, group["id"], ids["Cara"], 77, [ids["Bob"]])
    record_payment(client, group["id"], ids["Bob"], ids["Cara"], 1234)

    assert sum(balances_by_name(client, group["id"]).values()) == 0
