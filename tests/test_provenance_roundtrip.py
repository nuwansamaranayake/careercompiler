"""A fact's provenance survives storage.

Found by the browser suite on 2026-11-09: a fact extracted from an uploaded resume was
shown as "self attested" beside the sentence it licensed. The claim was stored as
document_sourced and the loader rebuilt it through the data-entry constructor, which
stamps self_attested on everything. Every provenance map (the API, the PDF appendix, the
docx appendix) inherited the wrong label. Provenance is the product; a loader that
rewrites it is the GoviHub class of failure in miniature.
"""
from __future__ import annotations

import io

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import db, routes
from app.config import settings
from app.engine import entailment
from app.engine.linker import Bullet
from app.main import app

H = {}
RESUME = "Jordan Alvarez\n\nRan Kubernetes in production at Globex.\n"


class _Gateway:
    def complete(self, *, model, messages, json_schema=None, temperature=0.0):
        return {"claims": [{
            "claim_key": "k8s", "kind": "skill",
            "statement": "Ran Kubernetes in production at Globex.",
            "quote": "Ran Kubernetes in production at Globex.", "confidence": 0.9}]}


@pytest.fixture()
def client(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", poolclass=sa.pool.StaticPool,
        connect_args={"check_same_thread": False})
    db.metadata.create_all(engine)
    db.set_engine_for_tests(engine)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model_reasoning", "stub/model")
    monkeypatch.setattr(settings, "llm_model_extraction", "stub/model")
    monkeypatch.setattr(settings, "nli_model", "stub/nli")
    monkeypatch.setattr(settings, "nli_model_revision", "f" * 40)
    monkeypatch.setattr(entailment, "_load", lambda mid, rev: (lambda p, h: 0.95))
    monkeypatch.setattr(routes, "_gateway", lambda: _Gateway())
    monkeypatch.setattr(routes, "draft_bullets", lambda gateway, model, claims, job_title, reqs:
                        [Bullet(c.core.statement, [c.core.claim_id]) for c in claims])
    return TestClient(app)


def _compile(client, cid) -> int:
    jid = client.post("/api/v1/jobs", headers=H, json={
        "title": "Platform Engineer", "requirements": [
            {"req_key": "k8s", "text": "Kubernetes in production", "kind": "skill",
             "must_have": True}]}).json()["job_id"]
    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 201, r.text
    return r.json()["document_id"]


def _appendix(client, did) -> str:
    pdf = client.get(f"/api/v1/compile/{did}/pdf", headers=H)
    return " ".join("\n".join((p.extract_text() or "")
                              for p in PdfReader(io.BytesIO(pdf.content)).pages).split())


def test_an_extracted_fact_stays_document_sourced_with_its_span(client):
    cid = client.post("/api/v1/candidates", json={"resume_text": RESUME},
                      headers=H).json()["candidate_id"]
    ex = client.post(f"/api/v1/candidates/{cid}/claims/extract", headers=H).json()
    assert ex["provenance"] == "document_sourced" and ex["stored"] == 1

    with db.get_session() as s:
        [claim] = routes._load_claims(s, cid)
        text = s.execute(sa.select(db.source_documents.c.text)
                         .where(db.source_documents.c.candidate_id == cid)).scalar_one()
    assert claim.provenance.value == "document_sourced"
    start, end = claim.core.evidence_ref.span
    assert text[start:end] == "Ran Kubernetes in production at Globex."

    did = _compile(client, cid)
    fact = client.get(f"/api/v1/compile/{did}", headers=H).json()["bullets"][0]["facts"][0]
    assert fact["provenance"] == "document_sourced"
    appendix = _appendix(client, did)
    assert "document_sourced" in appendix and "self_attested" not in appendix


def test_an_entered_fact_stays_self_attested(client):
    cid = client.post("/api/v1/candidates", json={"name": "T. Reviewer"},
                      headers=H).json()["candidate_id"]
    client.post(f"/api/v1/candidates/{cid}/claims", headers=H, json={"entries": [
        {"claim_key": "k8s", "kind": "skill",
         "statement": "Ran Kubernetes in production at Globex."}]})

    with db.get_session() as s:
        [claim] = routes._load_claims(s, cid)
    assert claim.provenance.value == "self_attested"
    assert claim.core.evidence_ref.span is None

    did = _compile(client, cid)
    fact = client.get(f"/api/v1/compile/{did}", headers=H).json()["bullets"][0]["facts"][0]
    assert fact["provenance"] == "self_attested"
