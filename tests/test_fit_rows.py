"""A fit row names the requirement in the posting's own words.

A row used to carry only `req_key`, a machine label the model coins ("led_a_team_of").
The reader of a fit report is a job seeker: the row now also carries `requirement`, the
requirement text as read from the posting, so the table says what the employer said.
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app import db
from app.main import app

FACTS = [{"claim_key": "k8s", "kind": "skill",
          "statement": "Ran Kubernetes in production at Globex."}]
REQS = [
    {"req_key": "k8s_prod", "text": "Kubernetes in production", "kind": "skill",
     "must_have": True},
    {"req_key": "clearance", "text": "Active TS/SCI security clearance", "kind": "other",
     "must_have": True},
]


@pytest.fixture()
def client():
    engine = sa.create_engine(
        "sqlite://", poolclass=sa.pool.StaticPool,
        connect_args={"check_same_thread": False})
    db.metadata.create_all(engine)
    db.set_engine_for_tests(engine)
    return TestClient(app)


def test_each_fit_row_carries_the_requirement_text(client):
    cid = client.post("/api/v1/candidates", json={"name": "T"}).json()["candidate_id"]
    client.post(f"/api/v1/candidates/{cid}/claims", json={"entries": FACTS})
    jid = client.post("/api/v1/jobs", json={"title": "SRE", "requirements": REQS}).json()["job_id"]
    rid = client.post("/api/v1/fit", json={"candidate_id": cid, "job_id": jid,
                                           "embedder": "hashing"}).json()["fit_report_id"]

    rows = client.get(f"/api/v1/fit/{rid}").json()["rows"]

    assert {r["req_key"]: r["requirement"] for r in rows} == {
        "k8s_prod": "Kubernetes in production",
        "clearance": "Active TS/SCI security clearance"}
    assert all("status" in r and "explanation" in r for r in rows)


def test_a_row_whose_requirement_was_since_removed_says_so_plainly(client):
    cid = client.post("/api/v1/candidates", json={"name": "T"}).json()["candidate_id"]
    client.post(f"/api/v1/candidates/{cid}/claims", json={"entries": FACTS})
    jid = client.post("/api/v1/jobs", json={"title": "SRE", "requirements": REQS}).json()["job_id"]
    rid = client.post("/api/v1/fit", json={"candidate_id": cid, "job_id": jid,
                                           "embedder": "hashing"}).json()["fit_report_id"]
    with db.get_session() as s, s.begin():
        s.execute(db.requirements.delete().where(db.requirements.c.req_key == "clearance"))

    rows = {r["req_key"]: r for r in client.get(f"/api/v1/fit/{rid}").json()["rows"]}

    assert rows["k8s_prod"]["requirement"] == "Kubernetes in production"
    assert rows["clearance"]["requirement"] is None
