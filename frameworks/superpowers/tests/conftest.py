import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def to_cents(text: str) -> int:
    """Test-side parser for response money strings, including negatives."""
    negative = text.startswith("-")
    whole, fraction = text.removeprefix("-").split(".")
    cents = int(whole) * 100 + int(fraction)
    return -cents if negative else cents


@pytest.fixture
def client(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_group(client):
    def _make(*member_names, currency="EUR"):
        group = client.post("/groups", json={"name": "Trip", "currency": currency}).json()
        member_ids = [
            client.post(f"/groups/{group['id']}/members", json={"name": name}).json()["id"]
            for name in member_names
        ]
        return group["id"], member_ids

    return _make
