"""Part B: demo access proven, not intended.

B2's three properties each get a test — a demo token cannot read another tenant's data,
cannot exceed its request budget, and expires. Plus the seeded verdicts (B3) including the
planted disqualifying gap, and the estate invariant (B5): no token, no read, 401.
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app import db, demo
from app.config import settings
from app.main import app

TOKEN = "estate-token"
H = {"Authorization": f"Bearer {TOKEN}"}


class FakeRedis:
    """The slice of redis the demo module uses, with a manual expiry lever for tests."""

    def __init__(self):
        self.store: dict[str, dict] = {}
        self.counters: dict[str, int] = {}

    def hset(self, key, mapping):
        self.store.setdefault(key, {}).update(
            {k: str(v) for k, v in mapping.items()})

    def hget(self, key, field):
        return self.store.get(key, {}).get(field)

    def hincrby(self, key, field, n):
        v = int(self.store.setdefault(key, {}).get(field, 0)) + n
        self.store[key][field] = str(v)
        return v

    def exists(self, key):
        return 1 if key in self.store else 0

    def incr(self, key):
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def expire(self, key, ttl):
        return True

    def expire_now(self, key):
        """What Redis does at TTL, done on demand."""
        self.store.pop(key, None)


@pytest.fixture()
def client(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", poolclass=sa.pool.StaticPool,
        connect_args={"check_same_thread": False})
    db.metadata.create_all(engine)
    db.set_engine_for_tests(engine)
    monkeypatch.setattr(settings, "smoke_test_token", TOKEN)
    fake = FakeRedis()
    demo.set_redis_for_tests(fake)
    c = TestClient(app)
    c.fake_redis = fake
    return c


def _session(client) -> dict:
    r = client.post("/api/v1/demo/session")
    assert r.status_code == 201, r.text
    return r.json()


def test_session_is_credential_free_and_seeds_both_verdicts(client):
    """B3: the reviewer sees the honest do-not-apply without typing anything."""
    s = _session(client)
    assert s["synthetic"] is True
    verdicts = {j["title"]: j["verdict"] for j in s["jobs"]}
    assert verdicts["Platform Engineer"] == "apply"
    assert verdicts["Site Reliability Lead, Defense Systems"] == "do_not_apply"

    dh = {"Authorization": f"Bearer {s['token']}"}
    gap_job = next(j for j in s["jobs"] if j["verdict"] == "do_not_apply")
    rep = client.get(f"/api/v1/fit/{gap_job['fit_report_id']}", headers=dh).json()
    assert "active_ts_sci_clearance" in rep["report"]["disqualifying"]
    assert rep["report"]["case_against"], "the case against applying must be stated"


def test_demo_token_cannot_read_another_tenants_data(client):
    """B2 property one. Two sessions; A's token on B's rows must 403, symmetrically."""
    a, b = _session(client), _session(client)
    ah = {"Authorization": f"Bearer {a['token']}"}
    bh = {"Authorization": f"Bearer {b['token']}"}

    assert client.get(f"/api/v1/fit/{b['jobs'][0]['fit_report_id']}",
                      headers=ah).status_code == 403
    assert client.get(f"/api/v1/fit/{a['jobs'][0]['fit_report_id']}",
                      headers=bh).status_code == 403
    r = client.post("/api/v1/compile",
                    json={"candidate_id": b["candidate_id"], "job_id": b["jobs"][0]["job_id"]},
                    headers=ah)
    assert r.status_code == 403
    # and the estate token still reads everything
    assert client.get(f"/api/v1/fit/{a['jobs'][0]['fit_report_id']}",
                      headers=H).status_code == 200


def test_demo_token_cannot_exceed_its_request_budget(client, monkeypatch):
    """B2 property two. The budget is a counter; crossing it is 429, not a slow fade."""
    monkeypatch.setattr(settings, "demo_request_budget", 3)
    s = _session(client)
    dh = {"Authorization": f"Bearer {s['token']}"}
    rid = s["jobs"][0]["fit_report_id"]
    for _ in range(3):
        assert client.get(f"/api/v1/fit/{rid}", headers=dh).status_code == 200
    assert client.get(f"/api/v1/fit/{rid}", headers=dh).status_code == 429


def test_demo_token_expires(client):
    """B2 property three. When Redis drops the key the token is any other bad bearer."""
    s = _session(client)
    dh = {"Authorization": f"Bearer {s['token']}"}
    rid = s["jobs"][0]["fit_report_id"]
    assert client.get(f"/api/v1/fit/{rid}", headers=dh).status_code == 200
    client.fake_redis.expire_now(f"demo:{s['token']}")
    assert client.get(f"/api/v1/fit/{rid}", headers=dh).status_code == 401


def test_no_token_is_still_401_everywhere(client):
    """B5: demo access must never become public access."""
    s = _session(client)
    rid = s["jobs"][0]["fit_report_id"]
    assert client.get(f"/api/v1/fit/{rid}").status_code == 401
    assert client.post("/api/v1/candidates", json={"name": "x"}).status_code == 401
    assert client.post("/api/v1/compile",
                       json={"candidate_id": 1, "job_id": 1}).status_code == 401


def test_session_creation_is_rate_limited_per_address(client, monkeypatch):
    monkeypatch.setattr(settings, "demo_sessions_per_ip_hour", 2)
    _session(client)
    _session(client)
    assert client.post("/api/v1/demo/session").status_code == 429


def test_demo_writes_are_tenant_prefixed_and_retention_shaped(client):
    """Every row a demo session creates must carry the prefix, or retention could never
    reclaim it and scope checks would not hold."""
    s = _session(client)
    dh = {"Authorization": f"Bearer {s['token']}"}
    cid = client.post("/api/v1/candidates", json={"name": "My Own"},
                      headers=dh).json()["candidate_id"]
    with db.get_session() as se:
        name = se.execute(sa.select(db.candidates.c.name)
                          .where(db.candidates.c.id == cid)).first().name
    assert name.startswith("demo-") and name.endswith("My Own")
    import re
    assert re.match(r"^demo-\d{8}T\d{6}Z-[0-9a-f]{6}-", name), \
        "the prefix must carry its creation time for retention to reclaim it"
