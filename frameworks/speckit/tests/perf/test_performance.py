"""SC-005: balances + settle-up for 20 members and 1,000 expenses in under one second."""

import random
import time

from splitit.money import format_money


def test_balances_and_settle_up_under_one_second(client, make_group):
    rng = random.Random(20261003)
    group_id, ids = make_group(*[f"Member {i}" for i in range(20)])
    members = list(ids.values())
    for i in range(1000):
        resp = client.post(
            f"/groups/{group_id}/expenses",
            json={
                "payer_id": rng.choice(members),
                "amount": format_money(rng.randint(1, 500_000)),
                "description": f"expense {i}",
                "participant_ids": rng.sample(members, rng.randint(1, 20)),
            },
        )
        assert resp.status_code == 201

    balances = client.get(f"/groups/{group_id}/balances").json()["balances"]
    assert all(b["balance"] != "0.00" for b in balances), "worst case needs all 20 balances nonzero"

    start = time.perf_counter()
    assert client.get(f"/groups/{group_id}/balances").status_code == 200
    resp = client.get(f"/groups/{group_id}/settle-up")
    elapsed = time.perf_counter() - start

    assert resp.status_code == 200
    assert len(resp.json()["transfers"]) <= 19
    assert elapsed < 1.0, f"took {elapsed:.3f}s"
