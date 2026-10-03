from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import create_group, member_ids
from tests.test_balances import balances_by_name
from tests.test_expenses import record_expense
from tests.test_payments import record_payment


def settle_up(client: TestClient, group_id: str) -> dict[str, Any]:
    response = client.get(f"/groups/{group_id}/settle-up")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_settled_group_needs_no_transfers(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob"])

    assert settle_up(client, group["id"]) == {"transfers": [], "optimal": True}


def test_suggests_who_pays_whom(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob", "Cara"])
    ids = member_ids(group)
    record_expense(client, group["id"], ids["Alice"], 900, list(ids.values()))

    result = settle_up(client, group["id"])

    assert result["optimal"] is True
    assert sorted(result["transfers"], key=lambda t: t["from_id"] == ids["Cara"]) == [
        {"from_id": ids["Bob"], "to_id": ids["Alice"], "amount": 300},
        {"from_id": ids["Cara"], "to_id": ids["Alice"], "amount": 300},
    ]


def test_recording_the_suggested_transfers_settles_everyone(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob", "Cara", "Dan"])
    ids = member_ids(group)
    record_expense(client, group["id"], ids["Alice"], 1001, list(ids.values()))
    record_expense(client, group["id"], ids["Bob"], 777, [ids["Cara"], ids["Dan"]])
    record_expense(client, group["id"], ids["Dan"], 50, [ids["Alice"]])
    record_payment(client, group["id"], ids["Cara"], ids["Alice"], 100)

    for t in settle_up(client, group["id"])["transfers"]:
        assert record_payment(client, group["id"], t["from_id"], t["to_id"], t["amount"]).status_code == 201

    assert set(balances_by_name(client, group["id"]).values()) == {0}
    assert settle_up(client, group["id"]) == {"transfers": [], "optimal": True}


def test_uses_fewer_transfers_than_greedy_would(client: TestClient) -> None:
    # Balances a:-9 b:-8 c:+9 d:-6 e:-4 f:+18. Greedy needs 5 transfers; 4 is the minimum.
    group = create_group(client, ["a", "b", "c", "d", "e", "f"])
    ids = member_ids(group)
    record_expense(client, group["id"], ids["c"], 9, [ids["a"]])
    record_expense(client, group["id"], ids["f"], 18, [ids["b"], ids["d"], ids["e"]])
    record_payment(client, group["id"], ids["e"], ids["b"], 2)  # e:-6 -> -4, b:-6 -> -8
    assert balances_by_name(client, group["id"]) == {
        "a": -9, "b": -8, "c": 9, "d": -6, "e": -4, "f": 18,
    }  # fmt: skip

    result = settle_up(client, group["id"])

    assert len(result["transfers"]) == 4
    assert result["optimal"] is True


def test_large_groups_fall_back_to_greedy(client: TestClient) -> None:
    names = [f"M{i:02}" for i in range(20)]
    group = create_group(client, names)
    ids = member_ids(group)
    for i, name in enumerate(names[1:], start=1):
        record_expense(client, group["id"], ids[name], 100 + i, [ids["M00"]])

    result = settle_up(client, group["id"])

    assert result["optimal"] is False
    for t in result["transfers"]:
        record_payment(client, group["id"], t["from_id"], t["to_id"], t["amount"])
    assert set(balances_by_name(client, group["id"]).values()) == {0}


def test_same_state_gives_same_settle_up(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob", "Cara", "Dan"])
    ids = member_ids(group)
    record_expense(client, group["id"], ids["Alice"], 400, list(ids.values()))
    record_expense(client, group["id"], ids["Bob"], 400, list(ids.values()))

    assert settle_up(client, group["id"]) == settle_up(client, group["id"])


def test_settle_up_of_unknown_group_is_404(client: TestClient) -> None:
    assert client.get("/groups/nope/settle-up").status_code == 404
