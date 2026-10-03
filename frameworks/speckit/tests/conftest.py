import pytest
from fastapi.testclient import TestClient

from splitit.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def make_group(client):
    """Create a group with the given member names; return (group_id, {name: member_id})."""

    def _make(*names: str, group_name: str = "Trip") -> tuple[str, dict[str, str]]:
        resp = client.post("/groups", json={"name": group_name})
        assert resp.status_code == 201, resp.text
        group_id = resp.json()["id"]
        ids = {}
        for name in names:
            r = client.post(f"/groups/{group_id}/members", json={"name": name})
            assert r.status_code == 201, r.text
            ids[name] = r.json()["id"]
        return group_id, ids

    return _make
