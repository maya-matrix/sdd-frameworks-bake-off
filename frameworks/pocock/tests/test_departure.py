from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import create_group, member_ids
from tests.test_balances import balances_by_name
from tests.test_expenses import record_expense
from tests.test_payments import record_payment
from tests.test_settle_up import settle_up


def leave(client: TestClient, group_id: str, member_id: str) -> Any:
    return client.delete(f"/groups/{group_id}/members/{member_id}")


def settled_trio(client: TestClient) -> tuple[str, dict[str, str], str, str]:
    """Alice paid 900 for all three; Cara has paid Alice back and is settled."""
    group = create_group(client, ["Alice", "Bob", "Cara"])
    ids = member_ids(group)
    expense = record_expense(client, group["id"], ids["Alice"], 900, list(ids.values())).json()
    payment = record_payment(client, group["id"], ids["Cara"], ids["Alice"], 300).json()
    return group["id"], ids, expense["id"], payment["id"]


def test_settled_member_can_leave(client: TestClient) -> None:
    group_id, ids, _, _ = settled_trio(client)

    response = leave(client, group_id, ids["Cara"])

    assert response.status_code == 204
    members = client.get(f"/groups/{group_id}").json()["members"]
    assert [m["name"] for m in members] == ["Alice", "Bob"]
    assert balances_by_name(client, group_id) == {"Alice": 300, "Bob": -300}


def test_member_with_nonzero_balance_cannot_leave(client: TestClient) -> None:
    group_id, ids, _, _ = settled_trio(client)

    assert leave(client, group_id, ids["Bob"]).status_code == 409
    assert leave(client, group_id, ids["Alice"]).status_code == 409
    assert "Bob" in balances_by_name(client, group_id)


def test_departed_member_stays_in_history(client: TestClient) -> None:
    group_id, ids, expense_id, payment_id = settled_trio(client)

    leave(client, group_id, ids["Cara"])

    (expense,) = client.get(f"/groups/{group_id}/expenses").json()
    assert ids["Cara"] in {s["member_id"] for s in expense["shares"]}
    (payment,) = client.get(f"/groups/{group_id}/payments").json()
    assert payment["from_id"] == ids["Cara"]


def test_departed_member_is_left_out_of_settle_up(client: TestClient) -> None:
    group_id, ids, _, _ = settled_trio(client)

    leave(client, group_id, ids["Cara"])

    assert settle_up(client, group_id)["transfers"] == [
        {"from_id": ids["Bob"], "to_id": ids["Alice"], "amount": 300}
    ]


def test_departed_member_cannot_take_part_in_new_records(client: TestClient) -> None:
    group_id, ids, _, _ = settled_trio(client)
    leave(client, group_id, ids["Cara"])

    assert record_expense(client, group_id, ids["Cara"], 100, [ids["Bob"]]).status_code == 422
    assert record_expense(client, group_id, ids["Bob"], 100, [ids["Cara"]]).status_code == 422
    assert record_payment(client, group_id, ids["Cara"], ids["Bob"], 100).status_code == 422
    assert record_payment(client, group_id, ids["Bob"], ids["Cara"], 100).status_code == 422


def test_departed_members_name_stays_reserved(client: TestClient) -> None:
    group_id, ids, _, _ = settled_trio(client)
    leave(client, group_id, ids["Cara"])

    response = client.post(f"/groups/{group_id}/members", json={"name": "CARA"})

    assert response.status_code == 409


def test_leaving_twice_or_leaving_the_wrong_group_is_404(client: TestClient) -> None:
    group_id, ids, _, _ = settled_trio(client)
    other = create_group(client, ["Zed"])

    assert leave(client, other["id"], ids["Cara"]).status_code == 404
    assert leave(client, group_id, "nope").status_code == 404
    assert leave(client, "nope", ids["Cara"]).status_code == 404
    assert leave(client, group_id, ids["Cara"]).status_code == 204
    assert leave(client, group_id, ids["Cara"]).status_code == 404


def test_deletes_that_would_unsettle_a_departed_member_are_refused(client: TestClient) -> None:
    group_id, ids, expense_id, payment_id = settled_trio(client)
    leave(client, group_id, ids["Cara"])

    assert client.delete(f"/groups/{group_id}/expenses/{expense_id}").status_code == 409
    assert client.delete(f"/groups/{group_id}/payments/{payment_id}").status_code == 409
    assert len(client.get(f"/groups/{group_id}/expenses").json()) == 1
    assert len(client.get(f"/groups/{group_id}/payments").json()) == 1


def test_deletes_not_involving_a_departed_member_still_succeed(client: TestClient) -> None:
    group_id, ids, _, _ = settled_trio(client)
    leave(client, group_id, ids["Cara"])
    expense = record_expense(client, group_id, ids["Bob"], 50, [ids["Alice"]]).json()
    payment = record_payment(client, group_id, ids["Bob"], ids["Alice"], 10).json()

    assert client.delete(f"/groups/{group_id}/expenses/{expense['id']}").status_code == 204
    assert client.delete(f"/groups/{group_id}/payments/{payment['id']}").status_code == 204


def test_delete_touching_a_departed_member_is_allowed_if_it_nets_to_zero(
    client: TestClient,
) -> None:
    # Cara paid 10 for herself only: the Expense involves her but leaves her at zero.
    group_id, ids, _, _ = settled_trio(client)
    own = record_expense(client, group_id, ids["Cara"], 10, [ids["Cara"]]).json()
    leave(client, group_id, ids["Cara"])

    assert client.delete(f"/groups/{group_id}/expenses/{own['id']}").status_code == 204
