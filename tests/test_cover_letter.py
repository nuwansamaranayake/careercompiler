"""The cover-letter pipeline: same gates as the resume, letter voice, letter docx.

The renderer is stubbed at the draft_letter seam (each test plants the exact draft the
pipeline will gate); the NLI scorer is stubbed at the `_load` seam. NOT stubbed: the
selector, the linker, the gate logic, persistence, and the letter docx writer. The planted
overstatement test is the objective's pass condition at unit level: a letter sentence
stronger than its evidence fails the compile and persists nothing.
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


def _seed(client) -> tuple[int, int, list[str]]:
    cid = client.post("/api/v1/candidates", json={"name": "T. Reviewer"},
                      headers=H).json()["candidate_id"]
    client.post(f"/api/v1/candidates/{cid}/claims", json={"entries": FACTS}, headers=H)
    jid = client.post("/api/v1/jobs", json={"title": "Senior Backend Engineer",
                                            "requirements": REQS},
                      headers=H).json()["job_id"]
    with db.get_session() as s:
        ids = [r.claim_id for r in s.execute(
            sa.select(db.atomic_claims.c.claim_id)
            .where(db.atomic_claims.c.candidate_id == cid)
            .order_by(db.atomic_claims.c.id)).all()]
    return cid, jid, ids


def _stub_letter(monkeypatch, drafts):
    from app.engine.linker import Bullet
    monkeypatch.setattr(routes, "draft_letter",
                        lambda gateway, model, claims, job_title, reqs:
                        [Bullet(d["text"], list(d["cites"])) for d in drafts])
    # Repair impossible by stub: planted violations must still reach the gate verdict.
    monkeypatch.setattr(routes, "revise_renderings",
                        lambda gateway, model, offending, letter=False: {})


def test_a_faithful_letter_passes_with_frame_and_letter_docx(client, monkeypatch):
    cid, jid, ids = _seed(client)
    _stub_letter(monkeypatch, [
        {"text": "I led a team of 4 engineers at Acme Corp from 2019 to 2022.",
         "cites": [ids[0]]},
        {"text": "I ran Kubernetes in production at Globex.", "cites": [ids[1]]},
    ])

    r = client.post("/api/v1/cover-letter",
                    json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "cover_letter"
    # The deterministic frame is present and references the role; the model never wrote it.
    assert body["greeting"] == "Dear Hiring Team,"
    assert "Senior Backend Engineer" in body["opening"]
    assert all(s["entailment"] == 0.95 for s in body["sentences"])

    # Stored as a gated document; the provenance read works unchanged.
    prov = client.get(f"/api/v1/compile/{body['document_id']}", headers=H).json()
    assert prov["document"]["kind"] == "cover_letter"
    assert len(prov["bullets"]) == 2

    docx = client.get(f"/api/v1/compile/{body['document_id']}/docx", headers=H)
    assert docx.status_code == 200
    assert docx.content[:2] == b"PK"
    assert b"letter" in docx.headers["content-disposition"].encode()


def test_a_planted_overstatement_fails_the_letter_and_persists_nothing(client, monkeypatch):
    cid, jid, ids = _seed(client)
    _stub_letter(monkeypatch, [
        {"text": "I directed the entire engineering organisation at Acme Corp.",
         "cites": [ids[0]]},
        {"text": "I ran Kubernetes in production at Globex.", "cites": [ids[1]]},
    ])
    # The gate scores the overstatement as not entailed, exactly as the real NLI did live
    # (faithful 0.9976 / inflated 0.0015 measured in production).
    monkeypatch.setattr(
        entailment, "_load",
        lambda mid, rev: (lambda p, h: 0.001 if "directed" in h else 0.95))

    r = client.post("/api/v1/cover-letter",
                    json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "entailment"
    assert "directed" in detail["violations"][0]["text"]

    with db.get_session() as s:
        n = s.execute(sa.select(sa.func.count())
                      .select_from(db.compiled_documents)).scalar()
    assert n == 0, "a failed letter must persist nothing"


def test_an_invented_number_fails_the_letter_via_reference_integrity(client, monkeypatch):
    cid, jid, ids = _seed(client)
    _stub_letter(monkeypatch, [
        {"text": "I led a team of 40 engineers at Acme Corp.", "cites": [ids[0]]},
        {"text": "I ran Kubernetes in production at Globex.", "cites": [ids[1]]},
    ])
    r = client.post("/api/v1/cover-letter",
                    json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "reference_integrity"
