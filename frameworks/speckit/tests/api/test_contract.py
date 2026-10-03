"""The app serves exactly the endpoints in contracts/openapi.yaml, with money in the contract format."""

import re
from pathlib import Path

import yaml

from splitit.main import create_app

CONTRACT = Path(__file__).resolve().parents[2] / "specs/001-expense-splitting-api/contracts/openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}


def _operations(paths: dict) -> set[tuple[str, str]]:
    return {(path, method) for path, item in paths.items() for method in item if method in METHODS}


def test_app_serves_every_contract_operation():
    contract = yaml.safe_load(CONTRACT.read_text())
    served = _operations(create_app().openapi()["paths"])
    assert _operations(contract["paths"]) == served


def test_money_fields_match_contract_pattern(client, make_group):
    contract = yaml.safe_load(CONTRACT.read_text())
    money = re.compile(contract["components"]["schemas"]["Money"]["pattern"])
    group_id, ids = make_group("Ana", "Ben", "Cleo")
    expense = client.post(
        f"/groups/{group_id}/expenses",
        json={"payer_id": ids["Ana"], "amount": "10.00", "description": "Taxi", "participant_ids": list(ids.values())},
    ).json()
    amounts = [expense["amount"], *(s["amount"] for s in expense["shares"])]
    amounts += [b["balance"] for b in client.get(f"/groups/{group_id}/balances").json()["balances"]]
    amounts += [t["amount"] for t in client.get(f"/groups/{group_id}/settle-up").json()["transfers"]]
    assert "-3.33" in amounts
    for amount in amounts:
        assert isinstance(amount, str) and money.fullmatch(amount), amount
