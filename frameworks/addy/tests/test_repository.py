import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from expense_splitter import repository
from expense_splitter.db import connect, init_schema


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(tmp_path / "test.db")
    init_schema(connection)
    yield connection
    connection.close()


def test_created_group_can_be_read_back(conn: sqlite3.Connection) -> None:
    group = repository.create_group(conn, name="Trip", currency="EUR")

    assert repository.get_group(conn, group.id) == group
    assert group.name == "Trip"
    assert group.currency == "EUR"


def test_unknown_group_is_none(conn: sqlite3.Connection) -> None:
    assert repository.get_group(conn, "missing") is None


def test_members_are_listed_in_join_order(conn: sqlite3.Connection) -> None:
    group = repository.create_group(conn, name="Trip", currency="EUR")
    names = ["Zed", "Ana", "Bo"]
    for name in names:
        repository.add_member(conn, group.id, name)

    members = repository.list_members(conn, group.id)

    assert [m.name for m in members] == names


def test_member_names_are_unique_per_group_ignoring_case(conn: sqlite3.Connection) -> None:
    group = repository.create_group(conn, name="Trip", currency="EUR")
    repository.add_member(conn, group.id, "Ana")

    with pytest.raises(repository.DuplicateMemberError):
        repository.add_member(conn, group.id, "ana")


def test_same_member_name_is_allowed_in_different_groups(conn: sqlite3.Connection) -> None:
    first = repository.create_group(conn, name="Trip", currency="EUR")
    second = repository.create_group(conn, name="Flat", currency="EUR")
    repository.add_member(conn, first.id, "Ana")

    member = repository.add_member(conn, second.id, "Ana")

    assert repository.list_members(conn, second.id) == [member]


def test_member_of_unknown_group_violates_foreign_key(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        repository.add_member(conn, "missing", "Ana")


def test_expense_and_shares_round_trip_in_cents(conn: sqlite3.Connection) -> None:
    group = repository.create_group(conn, name="Trip", currency="EUR")
    a, b, c = (repository.add_member(conn, group.id, n) for n in ["Ana", "Bo", "Cy"])

    expense = repository.add_expense(
        conn,
        group_id=group.id,
        payer_id=a.id,
        amount_cents=1000,
        description="Taxi",
        split_type="equal",
        shares=[(c.id, 334), (a.id, 333), (b.id, 333)],
    )

    assert repository.list_expenses(conn, group.id) == [expense]
    assert expense.amount_cents == 1000
    assert expense.shares == [(c.id, 334), (a.id, 333), (b.id, 333)]
    assert expense.created_at.endswith("Z")


def test_expenses_are_listed_oldest_first(conn: sqlite3.Connection) -> None:
    group = repository.create_group(conn, name="Trip", currency="EUR")
    a = repository.add_member(conn, group.id, "Ana")
    for description in ["first", "second", "third"]:
        repository.add_expense(conn, group.id, a.id, 100, description, "equal", [(a.id, 100)])

    expenses = repository.list_expenses(conn, group.id)

    assert [e.description for e in expenses] == ["first", "second", "third"]


def test_expenses_are_scoped_to_their_group(conn: sqlite3.Connection) -> None:
    trip = repository.create_group(conn, name="Trip", currency="EUR")
    flat = repository.create_group(conn, name="Flat", currency="EUR")
    a = repository.add_member(conn, trip.id, "Ana")
    repository.add_expense(conn, trip.id, a.id, 100, "Taxi", "equal", [(a.id, 100)])

    assert repository.list_expenses(conn, flat.id) == []


def test_failed_share_insert_rolls_back_the_expense(conn: sqlite3.Connection) -> None:
    group = repository.create_group(conn, name="Trip", currency="EUR")
    a = repository.add_member(conn, group.id, "Ana")

    with pytest.raises(sqlite3.IntegrityError):
        repository.add_expense(
            conn, group.id, a.id, 200, "Taxi", "equal", [(a.id, 100), ("ghost", 100)]
        )

    assert repository.list_expenses(conn, group.id) == []


def test_data_persists_across_connections(tmp_path: Path) -> None:
    path = tmp_path / "persist.db"
    first = connect(path)
    init_schema(first)
    group = repository.create_group(first, name="Trip", currency="EUR")
    first.close()

    second = connect(path)
    init_schema(second)

    assert repository.get_group(second, group.id) == group
    second.close()


def test_group_accepts_members_up_to_the_cap(conn: sqlite3.Connection) -> None:
    group = repository.create_group(conn, name="Trip", currency="EUR")

    for i in range(repository.MAX_MEMBERS):
        repository.add_member(conn, group.id, f"member {i}")

    assert len(repository.list_members(conn, group.id)) == repository.MAX_MEMBERS


def test_group_rejects_members_beyond_the_cap(conn: sqlite3.Connection) -> None:
    group = repository.create_group(conn, name="Trip", currency="EUR")
    for i in range(repository.MAX_MEMBERS):
        repository.add_member(conn, group.id, f"member {i}")

    with pytest.raises(repository.GroupFullError):
        repository.add_member(conn, group.id, "one too many")

    assert len(repository.list_members(conn, group.id)) == repository.MAX_MEMBERS
