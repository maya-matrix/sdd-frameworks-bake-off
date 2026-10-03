import pytest


def expense_payload(payer_id, split_between, amount="10.00", description="Taxi"):
    return {
        "payer_id": payer_id,
        "amount": amount,
        "description": description,
        "split_between": split_between,
    }


def test_record_expense_split_three_ways(client, make_group):
    group_id, (alice, bob, carol) = make_group("Alice", "Bob", "Carol")
    response = client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [carol, alice, bob]))
    assert response.status_code == 201
    body = response.json()
    assert body["payer_id"] == alice
    assert body["amount"] == "10.00"
    assert body["description"] == "Taxi"
    assert body["created_at"].endswith("Z")
    assert body["shares"] == [
        {"member_id": alice, "amount": "3.34"},
        {"member_id": bob, "amount": "3.33"},
        {"member_id": carol, "amount": "3.33"},
    ]


def test_payer_need_not_share_the_expense(client, make_group):
    group_id, (alice, bob) = make_group("Alice", "Bob")
    response = client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [bob]))
    assert response.status_code == 201
    assert response.json()["shares"] == [{"member_id": bob, "amount": "10.00"}]


def test_list_expenses_in_order(client, make_group):
    group_id, (alice, bob) = make_group("Alice", "Bob")
    first = client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [alice, bob])).json()
    second = client.post(
        f"/groups/{group_id}/expenses", json=expense_payload(bob, [alice], amount="0.01", description="Gum")
    ).json()
    assert client.get(f"/groups/{group_id}/expenses").json() == [first, second]


@pytest.mark.parametrize(
    "amount",
    [10, 10.5, "1.234", "0", "-5.00", "1e3", "", " 1", "1000000000.01", "9" * 5000, None],
)
def test_invalid_amount_is_422(client, make_group, amount):
    group_id, (alice, bob) = make_group("Alice", "Bob")
    response = client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [alice, bob], amount=amount))
    assert response.status_code == 422


@pytest.mark.parametrize("description", ["", "   ", "x" * 201])
def test_invalid_description_is_422(client, make_group, description):
    group_id, (alice,) = make_group("Alice")
    payload = expense_payload(alice, [alice], description=description)
    assert client.post(f"/groups/{group_id}/expenses", json=payload).status_code == 422


def test_empty_split_is_422(client, make_group):
    group_id, (alice,) = make_group("Alice")
    assert client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [])).status_code == 422


def test_duplicate_split_members_is_422(client, make_group):
    group_id, (alice, bob) = make_group("Alice", "Bob")
    payload = expense_payload(alice, [bob, bob])
    assert client.post(f"/groups/{group_id}/expenses", json=payload).status_code == 422


def test_non_integer_ids_are_422(client, make_group):
    group_id, (alice, bob) = make_group("Alice", "Bob")
    for payload in (
        expense_payload(True, [alice, bob]),
        expense_payload(str(alice), [alice, bob]),
        expense_payload(alice, [str(bob)]),
        expense_payload(alice, [True]),
        expense_payload(float(alice), [alice]),
    ):
        assert client.post(f"/groups/{group_id}/expenses", json=payload).status_code == 422


def test_members_of_another_group_are_rejected(client, make_group):
    group_id, (alice,) = make_group("Alice")
    _, (outsider,) = make_group("Mallory")
    for payload in (expense_payload(outsider, [alice]), expense_payload(alice, [alice, outsider])):
        response = client.post(f"/groups/{group_id}/expenses", json=payload)
        assert response.status_code == 422
        assert str(outsider) in response.json()["detail"]


def test_unknown_member_id_is_rejected(client, make_group):
    group_id, (alice,) = make_group("Alice")
    assert client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [999])).status_code == 422
    assert client.post(f"/groups/{group_id}/expenses", json=expense_payload(999, [alice])).status_code == 422


def test_rejected_expense_is_not_stored(client, make_group):
    group_id, (alice,) = make_group("Alice")
    client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [999]))
    assert client.get(f"/groups/{group_id}/expenses").json() == []


def test_unknown_group_is_404(client):
    assert client.post("/groups/999/expenses", json=expense_payload(1, [1])).status_code == 404
    assert client.get("/groups/999/expenses").status_code == 404
