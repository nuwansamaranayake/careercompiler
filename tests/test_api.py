import json
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app import db
from app.main import app

GOLDEN = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "synthetic" / "golden" /
     "golden.json").read_text(encoding="utf-8"))


@pytest.fixture()
def client():
    engine = sa.create_engine(
        "sqlite://",
        poolclass=sa.pool.StaticPool,
        connect_args={"check_same_thread": False},   # TestClient serves on another thread
    )
    db.metadata.create_all(engine)
    db.set_engine_for_tests(engine)
    return TestClient(app)


def _seed(client):
    cid = client.post("/api/v1/candidates",
                      json={"name": "T"}).json()["candidate_id"]
    client.post(f"/api/v1/candidates/{cid}/claims",
                json={"entries": GOLDEN["fact_graph"]})
    jid = client.post("/api/v1/jobs", json={
        "title": "Role", "requirements": GOLDEN["cases"][0]["requirements"]
    }).json()["job_id"]
    return cid, jid


def test_full_fit_loop(client):
    cid, jid = _seed(client)
    r = client.post("/api/v1/fit", json={"candidate_id": cid, "job_id": jid})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["verdict"] == "apply"
    full = client.get(f"/api/v1/fit/{body['fit_report_id']}").json()
    assert len(full["rows"]) == 4
    assert full["report"]["embedder"] == "hashing"


def test_fit_requires_claims_and_requirements(client):
    cid = client.post("/api/v1/candidates", json={"name": "T"}).json()["candidate_id"]
    jid = client.post("/api/v1/jobs", json={"title": "R"}).json()["job_id"]
    r = client.post("/api/v1/fit", json={"candidate_id": cid, "job_id": jid})
    assert r.status_code == 422


def test_extract_without_key_fails_loud(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    cid = client.post("/api/v1/candidates",
                      json={"name": "T", "resume_text": "x"}).json()["candidate_id"]
    r = client.post(f"/api/v1/candidates/{cid}/claims/extract")
    assert r.status_code == 503
    assert "OPENROUTER_API_KEY" in r.json()["detail"]


def test_bearer_auth_enforced_when_token_set(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "smoke_test_token", "sekrit")
    assert client.post("/api/v1/candidates", json={"name": "T"}).status_code == 401
    assert client.post("/api/v1/candidates", json={"name": "T"},
                       headers={"Authorization": "Bearer sekrit"}).status_code == 201


def test_malformed_claims_rejected(client):
    cid = client.post("/api/v1/candidates", json={"name": "T"}).json()["candidate_id"]
    r = client.post(f"/api/v1/candidates/{cid}/claims",
                    json={"entries": [{"statement": "no key"}]})
    assert r.status_code == 422
