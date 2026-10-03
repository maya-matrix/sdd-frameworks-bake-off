from pathlib import Path

from fastapi.testclient import TestClient

from expense_splitter.main import create_app


def test_data_survives_an_app_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "expenses.db"
    with TestClient(create_app(db_path)) as before:
        group_id = before.post("/groups", json={"name": "Trip"}).json()["id"]
        a = before.post(f"/groups/{group_id}/members", json={"name": "Ana"}).json()["id"]
        b = before.post(f"/groups/{group_id}/members", json={"name": "Bo"}).json()["id"]
        before.post(
            f"/groups/{group_id}/expenses",
            json={"payerId": a, "amount": "9.99", "description": "Lunch", "splitBetween": [a, b]},
        )
        snapshot = {
            path: before.get(f"/groups/{group_id}{path}").json()
            for path in ["", "/expenses", "/balances", "/settle-up"]
        }

    with TestClient(create_app(db_path)) as after:
        for path, expected in snapshot.items():
            assert after.get(f"/groups/{group_id}{path}").json() == expected

    assert snapshot["/balances"]["balances"][1]["balance"] == "-4.99"
