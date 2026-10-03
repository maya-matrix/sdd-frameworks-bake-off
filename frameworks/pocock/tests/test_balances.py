from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.conftest import create_group, member_ids
from tests.test_expenses import record_expense


def balances_by_name(client: TestClient, group_id: str) -> dict[str, int]:
    response = client.get(f"/groups/{group_id}/balances")
    assert response.status_code == 200, response.text
    return {b["name"]: b["balance"] for b in response.json()}


def test_new_group_has_everyone_at_zero(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob"])

    response = client.get(f"/groups/{group['id']}/balances")

    ids = member_ids(group)
    assert response.json() == [
        {"member_id": ids["Alice"], "name": "Alice", "balance": 0},
        {"member_id": ids["Bob"], "name": "Bob", "balance": 0},
    ]


def test_payer_is_owed_what_the_other_participants_owe(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob", "Cara"])
    ids = member_ids(group)
    record_expense(client, group["id"], ids["Alice"], 1000, list(ids.values()))

    assert balances_by_name(client, group["id"]) == {"Alice": 666, "Bob": -333, "Cara": -333}


def test_payer_outside_the_split_is_owed_the_full_amount(client: TestClient) -> None:
    group = create_group(client, ["Alice", "Bob", "Cara"])
    ids = member_ids(group)
    record_expense(client, group["id"], ids["Alice"], 3001, [ids["Bob"], ids["Cara"]])

    assert balances_by_name(client, group["id"]) == {"Alice": 3001, "Bob": -1501, "Cara": -1500}


def test_balances_accumulate_across_expenses_and_members_at_zero_are_listed(
    client: TestClient,
) -> None:
    group = create_group(client, ["Alice", "Bob", "Cara", "Dan"])
    ids = member_ids(group)
    record_expense(client, group["id"], ids["Alice"], 900, [ids["Alice"], ids["Bob"], ids["Cara"]])
    record_expense(client, group["id"], ids["Bob"], 600, [ids["Alice"], ids["Bob"]])

    assert balances_by_name(client, group["id"]) == {
        "Alice": 300, "Bob": 0, "Cara": -300, "Dan": 0,
    }  # fmt: skip


def test_balances_of_unknown_group_are_404(client: TestClient) -> None:
    assert client.get("/groups/nope/balances").status_code == 404


expense_spec = st.tuples(
    st.integers(0, 4),  # payer index
    st.integers(1, 10**9),  # amount
    st.sets(st.integers(0, 4), min_size=1),  # participant indexes
)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=30)
@given(st.lists(expense_spec, max_size=8))
def test_balances_always_sum_to_exactly_zero(
    client: TestClient, expenses: list[tuple[int, int, set[int]]]
) -> None:
    group = create_group(client, ["A", "B", "C", "D", "E"])
    members = [m["id"] for m in group["members"]]
    for payer, amount, participants in expenses:
        record_expense(
            client, group["id"], members[payer], amount, [members[i] for i in participants]
        )

    assert sum(balances_by_name(client, group["id"]).values()) == 0
