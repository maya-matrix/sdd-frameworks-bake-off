from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from expense_splitter.app import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(tmp_path / "test.db")) as test_client:
        yield test_client


def create_group(
    client: TestClient, members: list[str], name: str = "Trip", currency: str = "EUR"
) -> dict[str, Any]:
    response = client.post(
        "/groups", json={"name": name, "currency": currency, "members": members}
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def member_ids(group: dict[str, Any]) -> dict[str, str]:
    return {m["name"]: m["id"] for m in group["members"]}
