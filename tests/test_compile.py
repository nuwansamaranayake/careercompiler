"""The compile pipeline end to end: select -> render -> link -> gate -> persist -> docx.

The renderer is stubbed (its output is whatever the stub says, which lets each test plant
exactly the draft it needs) and the NLI scorer is stubbed at the `_load` seam. What is NOT
stubbed: the selector, the linker, the gate logic, persistence, the provenance map, and the
docx writer. The planted-violation tests prove the pipeline fails builds; the happy path
proves a passed document persists with its provenance.
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app import db
from app.config import settings
from app.engine import entailment
from app.main import app
from app import routes

H = {}  # no SMOKE_TEST_TOKEN in tests unless a test sets one

FACTS = [
    {"claim_key": "team_lead", "kind": "role",
     "statement": "Led a team of 4 engineers at Acme Corp from 2019 to 2022."},
    {"claim_key": "deploy_time", "kind": "magnitude",
     "statement": "Cut deploy time 40% by rebuilding the CI pipeline in Python."},
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
    # Entailment passes unless a test overrides the seam.
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


def _stub_render(monkeypatch, drafts):
    """Plant the exact draft the pipeline will gate. The renderer's alias mechanics have
    their own unit test; these tests exercise select -> link -> gate -> persist, so the
    draft is injected at the renderer seam and everything downstream is real. The repair
    loop's revision seam is stubbed to "no repair possible" so a planted violation still
    reaches the gate verdict — these tests prove the gates, not the repair."""
    from app.engine.linker import Bullet
    monkeypatch.setattr(routes, "draft_bullets",
                        lambda gateway, model, claims, job_title, reqs:
                        [Bullet(d["text"], list(d["cites"])) for d in drafts])
    monkeypatch.setattr(routes, "revise_renderings",
                        lambda gateway, model, offending, letter=False: {})


def test_a_faithful_compile_passes_persists_and_serves_provenance(client, monkeypatch):
    cid, jid, ids = _seed(client)
    _stub_render(monkeypatch, [
        {"text": "Led a team of 4 engineers at Acme Corp from 2019 to 2022.",
         "cites": [ids[0]]},
        {"text": "Cut deploy time 40% by rebuilding the CI pipeline in Python.",
         "cites": [ids[1]]},
        {"text": "Ran Kubernetes in production at Globex.", "cites": [ids[2]]},
    ])

    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 201, r.text
    body = r.json()
    did = body["document_id"]
    assert body["uncovered_must"] == []
    assert all(b["entailment"] == 0.95 for b in body["bullets"])
    assert body["gate"]["revision"] == "f" * 40

    prov = client.get(f"/api/v1/compile/{did}", headers=H).json()
    assert len(prov["bullets"]) == 3
    first = prov["bullets"][0]
    assert first["facts"][0]["statement"].startswith("Led a team of 4")

    docx = client.get(f"/api/v1/compile/{did}/docx", headers=H)
    assert docx.status_code == 200
    assert docx.content[:2] == b"PK", "a docx is a zip; this is not one"
    assert len(docx.content) > 5000


def test_an_invented_number_fails_the_compile_and_persists_nothing(client, monkeypatch):
    cid, jid, ids = _seed(client)
    _stub_render(monkeypatch, [
        {"text": "Led a team of 40 engineers at Acme Corp.", "cites": [ids[0]]}])

    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "reference_integrity"
    assert detail["violations"][0]["failure"] == "unsupported_number"

    with db.get_session() as s:
        n = s.execute(sa.select(sa.func.count())
                      .select_from(db.compiled_documents)).scalar()
    assert n == 0, "a failed compile must persist nothing"


def test_a_sentence_stronger_than_its_evidence_fails_with_the_evidence_shown(
        client, monkeypatch):
    cid, jid, ids = _seed(client)
    _stub_render(monkeypatch, [
        {"text": "Directed engineering across the entire company.", "cites": [ids[0]]}])
    monkeypatch.setattr(entailment, "_load", lambda mid, rev: (lambda p, h: 0.03))

    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "entailment"
    v = detail["violations"][0]
    assert v["entailment"] == pytest.approx(0.03)
    assert "Led a team of 4" in v["premise"], "the failure must show the cited evidence"


def test_an_unavailable_entailment_model_is_a_typed_503_not_a_pass(client, monkeypatch):
    cid, jid, ids = _seed(client)
    _stub_render(monkeypatch, [
        {"text": "Led a team of 4 engineers at Acme Corp from 2019 to 2022.",
         "cites": [ids[0]]}])

    def unavailable(mid, rev):
        raise entailment.EntailmentUnavailable("weights missing from the image")
    monkeypatch.setattr(entailment, "_load", unavailable)

    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "entailment_unavailable"
    with db.get_session() as s:
        n = s.execute(sa.select(sa.func.count())
                      .select_from(db.compiled_documents)).scalar()
    assert n == 0


def test_citing_a_fact_the_selector_omitted_is_rejected(client, monkeypatch):
    """The model phrases; it does not choose content. A tiny budget forces omissions, and a
    draft citing an omitted fact must fail reference integrity."""
    cid, jid, ids = _seed(client)
    _stub_render(monkeypatch, [
        {"text": "Led a team of 4 engineers at Acme Corp from 2019 to 2022.",
         "cites": [ids[0]]},
        {"text": "Cut deploy time 40% by rebuilding the CI pipeline in Python.",
         "cites": [ids[1]]}])

    r = client.post("/api/v1/compile",
                    json={"candidate_id": cid, "job_id": jid, "budget_lines": 1},
                    headers=H)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "reference_integrity"
    assert any(v["failure"] == "cites_unselected_fact" for v in detail["violations"])


def test_the_check_endpoint_is_the_rejection_moment(client, monkeypatch):
    """E2's backend: edit a sentence, watch it rejected with the evidence beside it."""
    cid, jid, ids = _seed(client)
    _stub_render(monkeypatch, [
        {"text": "Led a team of 4 engineers at Acme Corp from 2019 to 2022.",
         "cites": [ids[0]]},
        {"text": "Cut deploy time 40% by rebuilding the CI pipeline in Python.",
         "cites": [ids[1]]},
        {"text": "Ran Kubernetes in production at Globex.", "cites": [ids[2]]}])
    did = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid},
                      headers=H).json()["document_id"]

    # the reviewer inflates the number
    r = client.post("/api/v1/compile/check",
                    json={"document_id": did,
                          "text": "Led a team of 400 engineers at Acme Corp.",
                          "cites": [ids[0]]}, headers=H)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["reference_integrity"]["violations"][0]["failure"] == "unsupported_number"

    # the reviewer inflates the verb: linker passes, entailment refuses
    monkeypatch.setattr(entailment, "_load", lambda mid, rev: (lambda p, h: 0.05))
    r = client.post("/api/v1/compile/check",
                    json={"document_id": did,
                          "text": "Directed engineering across the entire company.",
                          "cites": [ids[0]]}, headers=H)
    body = r.json()
    assert body["reference_integrity"]["ok"] is True
    assert body["entailment"]["ok"] is False
    assert "Led a team of 4" in body["entailment"]["violations"][0]["premise"]

    # the faithful edit passes
    monkeypatch.setattr(entailment, "_load", lambda mid, rev: (lambda p, h: 0.97))
    r = client.post("/api/v1/compile/check",
                    json={"document_id": did,
                          "text": "Led a team of 4 engineers at Acme Corp.",
                          "cites": [ids[0]]}, headers=H)
    assert r.json()["ok"] is True


def test_verify_endpoint_flips_state_and_a_rejected_fact_never_compiles(
        client, monkeypatch):
    cid, jid, ids = _seed(client)
    r = client.post(f"/api/v1/facts/{ids[2]}/verify", json={"status": "rejected"}, headers=H)
    assert r.status_code == 200 and r.json()["verification_status"] == "rejected"

    _stub_render(monkeypatch, [
        {"text": "Ran Kubernetes in production at Globex.", "cites": [ids[2]]}])
    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 422
    assert any(v["failure"] in ("cites_rejected_fact", "cites_unselected_fact")
               for v in r.json()["detail"]["violations"])


def test_verify_unknown_fact_is_404(client):
    assert client.post("/api/v1/facts/nope/verify", json={"status": "passed"},
                       headers=H).status_code == 404


def test_compile_without_a_key_is_the_same_typed_503_as_extract(client, monkeypatch):
    cid, jid, _ = _seed(client)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 503
