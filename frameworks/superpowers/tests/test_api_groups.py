import pytest


def test_create_group(client):
    response = client.post("/groups", json={"name": "  Trip  ", "currency": "USD"})
    assert response.status_code == 201
    body = response.json()
    assert body == {"id": body["id"], "name": "Trip", "currency": "USD", "members": []}


def test_currency_defaults_to_eur(client):
    assert client.post("/groups", json={"name": "Trip"}).json()["currency"] == "EUR"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 101},
        {"name": "Trip", "currency": "eur"},
        {"name": "Trip", "currency": "EURO"},
        {"name": "Trip", "currency": " EUR"},
    ],
)
def test_create_group_validation(client, payload):
    assert client.post("/groups", json=payload).status_code == 422


def test_get_group_lists_members_in_id_order(client, make_group):
    group_id, (alice, bob) = make_group("Alice", "Bob")
    response = client.get(f"/groups/{group_id}")
    assert response.status_code == 200
    assert response.json()["members"] == [{"id": alice, "name": "Alice"}, {"id": bob, "name": "Bob"}]


def test_add_and_list_members(client, make_group):
    group_id, _ = make_group()
    response = client.post(f"/groups/{group_id}/members", json={"name": " Alice "})
    assert response.status_code == 201
    member = response.json()
    assert member == {"id": member["id"], "name": "Alice"}
    assert client.get(f"/groups/{group_id}/members").json() == [member]


def test_duplicate_member_name_conflicts(client, make_group):
    group_id, _ = make_group("Alice")
    response = client.post(f"/groups/{group_id}/members", json={"name": "Alice"})
    assert response.status_code == 409
    assert "Alice" in response.json()["detail"]


def test_name_differing_only_by_whitespace_is_a_duplicate(client, make_group):
    group_id, _ = make_group("Alice")
    assert client.post(f"/groups/{group_id}/members", json={"name": "Alice "}).status_code == 409


def test_same_member_name_allowed_in_different_groups(client, make_group):
    make_group("Alice")
    other_group, _ = make_group()
    assert client.post(f"/groups/{other_group}/members", json={"name": "Alice"}).status_code == 201


@pytest.mark.parametrize("payload", [{}, {"name": ""}, {"name": "x" * 101}])
def test_add_member_validation(client, make_group, payload):
    group_id, _ = make_group()
    assert client.post(f"/groups/{group_id}/members", json=payload).status_code == 422


def test_unknown_group_is_404(client):
    assert client.get("/groups/999").status_code == 404
    assert client.get("/groups/999/members").status_code == 404
    assert client.post("/groups/999/members", json={"name": "Alice"}).status_code == 404
    assert client.get("/groups/999").json() == {"detail": "group 999 not found"}


def test_non_integer_group_id_is_422(client):
    assert client.get("/groups/abc").status_code == 422


@pytest.mark.parametrize(
    "path",
    ["", "/members", "/expenses", "/balances", "/settle-up"],
)
def test_group_id_beyond_64_bits_is_404(client, path):
    assert client.get(f"/groups/{2**63}{path}").status_code == 404


def test_post_to_group_id_beyond_64_bits_is_404(client):
    huge = 2**63
    assert client.post(f"/groups/{huge}/members", json={"name": "Alice"}).status_code == 404
    payload = {"payer_id": 1, "amount": "1.00", "description": "x", "split_between": [1]}
    assert client.post(f"/groups/{huge}/expenses", json=payload).status_code == 404
