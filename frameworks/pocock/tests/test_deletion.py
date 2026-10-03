from fastapi.testclient import TestClient

from tests.conftest import create_group, member_ids
from tests.test_balances import balances_by_name
from tests.test_expenses import record_expense
from tests.test_payments import record_payment


def test_deleting_an_expense_reverses_its_effect(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob"])
    ids = member_ids(group)
    keep = record_expense(client, group["id"], ids["Bob"], 300, list(ids.values())).json()
    mistake = record_expense(client, group["id"], ids["Alice"], 1000, list(ids.values())).json()

    response = client.delete(f"/groups/{group['id']}/expenses/{mistake['id']}")

    assert response.status_code == 204
    assert client.get(f"/groups/{group['id']}/expenses").json() == [keep]
    assert balances_by_name(client, group["id"]) == {"Alice": -150, "Bob": 150}


def test_deleting_a_payment_reverses_its_effect(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob"])
    ids = member_ids(group)
    record_expense(client, group["id"], ids["Alice"], 1000, list(ids.values()))
    payment = record_payment(client, group["id"], ids["Bob"], ids["Alice"], 500).json()

    response = client.delete(f"/groups/{group['id']}/payments/{payment['id']}")

    assert response.status_code == 204
    assert client.get(f"/groups/{group['id']}/payments").json() == []
    assert balances_by_name(client, group["id"]) == {"Alice": 500, "Bob": -500}


def test_deleting_twice_is_404_the_second_time(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob"])
    ids = member_ids(group)
    expense = record_expense(client, group["id"], ids["Alice"], 100, [ids["Bob"]]).json()
    payment = record_payment(client, group["id"], ids["Bob"], ids["Alice"], 100).json()

    for path in (f"expenses/{expense['id']}", f"payments/{payment['id']}"):
        assert client.delete(f"/groups/{group['id']}/{path}").status_code == 204
        assert client.delete(f"/groups/{group['id']}/{path}").status_code == 404


def test_cannot_delete_another_groups_records(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob"])
    other = create_group(client, ["Zed"])
    ids = member_ids(group)
    expense = record_expense(client, group["id"], ids["Alice"], 100, [ids["Bob"]]).json()
    payment = record_payment(client, group["id"], ids["Bob"], ids["Alice"], 100).json()

    assert client.delete(f"/groups/{other['id']}/expenses/{expense['id']}").status_code == 404
    assert client.delete(f"/groups/{other['id']}/payments/{payment['id']}").status_code == 404
    assert len(client.get(f"/groups/{group['id']}/expenses").json()) == 1
    assert len(client.get(f"/groups/{group['id']}/payments").json()) == 1


def test_deleting_from_unknown_group_or_unknown_record_is_404(client: TestClient) -> None:
    group = create_group(client, ["Alice"])

    assert client.delete("/groups/nope/expenses/x").status_code == 404
    assert client.delete("/groups/nope/payments/x").status_code == 404
    assert client.delete(f"/groups/{group['id']}/expenses/x").status_code == 404
    assert client.delete(f"/groups/{group['id']}/payments/x").status_code == 404
