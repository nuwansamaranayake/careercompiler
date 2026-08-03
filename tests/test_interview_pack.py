"""The interview pack: deterministic assembly from gate-survivors, questions stubbed.

The question generator is stubbed at the draft_questions seam; everything that asserts —
fact statements, provenance, metrics, gaps, the case against — is real code over real
rows. The pack must never carry a claim the compiled document's facts do not state.
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app import db, routes
from app.config import settings
from app.engine import entailment
from app.main import app

H = {}

FACTS = [
    {"claim_key": "team_lead", "kind": "role",
     "statement": "Led a team of 4 engineers at Acme Corp from 2019 to 2022."},
    {"claim_key": "k8s", "kind": "skill",
     "statement": "Ran Kubernetes in production at Globex."},
]
REQS = [
    {"req_key": "lead", "text": "Team leadership", "kind": "experience", "must_have": True},
    {"req_key": "k8s", "text": "Kubernetes in production", "kind": "skill",
     "must_have": True},
    {"req_key": "terraform", "text": "Terraform IaC", "kind": "skill", "must_have": True},
]


@pytest.fixture()
def client(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", poolclass=sa.pool.StaticPool,
        connect_args={"check_same_thread": False})
    db.metadata.create_all(engine)
    db.set_engine_for_tests(engine)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model_reasoning", "stub/model")
    monkeypatch.setattr(settings, "nli_model", "stub/nli")
    monkeypatch.setattr(settings, "nli_model_revision", "f" * 40)
    monkeypatch.setattr(entailment, "_load", lambda mid, rev: (lambda p, h: 0.95))
    return TestClient(app)


def _compiled_doc(client, monkeypatch) -> int:
    from app.engine.linker import Bullet
    cid = client.post("/api/v1/candidates", json={"name": "T. Reviewer"},
                      headers=H).json()["candidate_id"]
    client.post(f"/api/v1/candidates/{cid}/claims", json={"entries": FACTS}, headers=H)
    jid = client.post("/api/v1/jobs", json={"title": "Senior Backend Engineer",
                                            "requirements": REQS},
                      headers=H).json()["job_id"]
    client.post("/api/v1/fit", json={"candidate_id": cid, "job_id": jid}, headers=H)
    with db.get_session() as s:
        ids = [r.claim_id for r in s.execute(
            sa.select(db.atomic_claims.c.claim_id)
            .where(db.atomic_claims.c.candidate_id == cid)
            .order_by(db.atomic_claims.c.id)).all()]
    monkeypatch.setattr(routes, "draft_bullets",
                        lambda gateway, model, claims, job_title, reqs: [
                            Bullet("Led a team of 4 engineers at Acme Corp.", [ids[0]]),
                            Bullet("Ran Kubernetes in production at Globex.", [ids[1]])])
    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid},
                    headers=H)
    assert r.status_code == 201, r.text
    return r.json()["document_id"]


def _stub_questions(monkeypatch, mapping):
    monkeypatch.setattr(routes, "draft_questions",
                        lambda gateway, model, job_title, bullets, gaps: mapping)


def test_pack_assembles_facts_metrics_and_gaps_deterministically(client, monkeypatch):
    did = _compiled_doc(client, monkeypatch)
    _stub_questions(monkeypatch, {
        "B1": ["How large was the team of 4?", "What did Acme Corp ship in 2019?"],
        "G1": ["How much Terraform have you actually run?"],
    })
    r = client.post("/api/v1/interview-pack", json={"document_id": did}, headers=H)
    assert r.status_code == 201, r.text
    pack = r.json()

    b1 = pack["bullets"][0]
    assert b1["facts"][0]["statement"] == FACTS[0]["statement"]
    assert "4" in b1["metrics"] and "2019" in b1["metrics"]
    assert b1["questions"][0].startswith("How large")
    # The unmatched requirement made the gaps section, with the honest case.
    assert any(g["requirement"] == "terraform" for g in pack["gaps"])
    tf = next(g for g in pack["gaps"] if g["requirement"] == "terraform")
    assert tf["questions"] == ["How much Terraform have you actually run?"]
    assert pack["verdict"] in ("apply", "do_not_apply")

    # A bullet id the model skipped renders as empty questions, never invented filler.
    assert pack["bullets"][1]["questions"] == []


def test_pack_docx_downloads(client, monkeypatch):
    did = _compiled_doc(client, monkeypatch)
    _stub_questions(monkeypatch, {"B1": ["Q?"], "B2": ["Q?"]})
    r = client.post("/api/v1/interview-pack",
                    json={"document_id": did, "format": "docx"}, headers=H)
    assert r.status_code == 201
    assert r.content[:2] == b"PK"
    assert b"prep" in r.headers["content-disposition"].encode()


def test_pack_requires_a_real_document(client):
    r = client.post("/api/v1/interview-pack", json={"document_id": 999}, headers=H)
    assert r.status_code == 404
