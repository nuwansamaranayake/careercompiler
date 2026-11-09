"""Editing a compiled line: the same two gates, then persistence.

`/compile/check` answers "would this compile?" and saves nothing. The edit endpoint is the
modification path: an edit that passes both gates replaces the stored sentence and its
score, so the PDF and docx carry it. An edit that outruns its evidence is a 422 and the
stored sentence does not move. Cites are never editable — an edit changes wording, not
which facts license it.
"""
from __future__ import annotations

import io

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from groundwork.testing import FakeRedis
from pypdf import PdfReader

from app import db, demo, routes
from app.config import settings
from app.engine import entailment
from app.engine.linker import Bullet
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


def _compiled(client, monkeypatch, *, letter: bool = False, headers=H) -> tuple[int, list[str]]:
    cid = client.post("/api/v1/candidates", json={"name": "T. Reviewer"},
                      headers=headers).json()["candidate_id"]
    client.post(f"/api/v1/candidates/{cid}/claims", json={"entries": FACTS}, headers=headers)
    jid = client.post("/api/v1/jobs", json={"title": "Senior Backend Engineer",
                                            "requirements": REQS},
                      headers=headers).json()["job_id"]
    with db.get_session() as s:
        ids = [r.claim_id for r in s.execute(
            sa.select(db.atomic_claims.c.claim_id)
            .where(db.atomic_claims.c.candidate_id == cid)
            .order_by(db.atomic_claims.c.id)).all()]
    drafts = [Bullet("Led a team of 4 engineers at Acme Corp from 2019 to 2022.", [ids[0]]),
              Bullet("Ran Kubernetes in production at Globex.", [ids[1]])]
    seam = "draft_letter" if letter else "draft_bullets"
    monkeypatch.setattr(routes, seam,
                        lambda gateway, model, claims, job_title, reqs: list(drafts))
    monkeypatch.setattr(routes, "revise_renderings",
                        lambda gateway, model, offending, letter=False: {})
    path = "/api/v1/cover-letter" if letter else "/api/v1/compile"
    r = client.post(path, json={"candidate_id": cid, "job_id": jid}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["document_id"], ids


def _texts(client, did, headers=H) -> list[str]:
    return [b["text"] for b in
            client.get(f"/api/v1/compile/{did}", headers=headers).json()["bullets"]]


def test_a_faithful_edit_is_saved_with_its_new_score(client, monkeypatch):
    did, ids = _compiled(client, monkeypatch)
    monkeypatch.setattr(entailment, "_load", lambda mid, rev: (lambda p, h: 0.91))

    r = client.put(f"/api/v1/compile/{did}/bullets/0",
                   json={"text": "Led a team of 4 engineers at Acme Corp."}, headers=H)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"document_id": did, "position": 0, "saved": True,
                    "text": "Led a team of 4 engineers at Acme Corp.",
                    "cites": [ids[0]], "entailment": 0.91}
    prov = client.get(f"/api/v1/compile/{did}", headers=H).json()["bullets"]
    assert prov[0]["text"] == "Led a team of 4 engineers at Acme Corp."
    assert prov[0]["entailment"] == 0.91
    assert prov[0]["cites"] == [ids[0]]


def test_editing_one_position_never_touches_another(client, monkeypatch):
    did, _ = _compiled(client, monkeypatch)
    before = _texts(client, did)

    client.put(f"/api/v1/compile/{did}/bullets/0",
               json={"text": "Led a team of 4 engineers."}, headers=H)

    after = _texts(client, did)
    assert after[0] == "Led a team of 4 engineers."
    assert after[1] == before[1]


def test_an_invented_number_is_rejected_and_nothing_changes(client, monkeypatch):
    did, _ = _compiled(client, monkeypatch)
    before = _texts(client, did)

    r = client.put(f"/api/v1/compile/{did}/bullets/0",
                   json={"text": "Led a team of 400 engineers at Acme Corp."}, headers=H)

    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "edit_rejected"
    assert detail["reference_integrity"]["violations"][0]["failure"] == "unsupported_number"
    assert detail["entailment"] == {"checked": False}
    assert _texts(client, did) == before


def test_an_overstated_verb_is_rejected_by_entailment_and_nothing_changes(
        client, monkeypatch):
    did, _ = _compiled(client, monkeypatch)
    before = _texts(client, did)
    monkeypatch.setattr(entailment, "_load", lambda mid, rev: (lambda p, h: 0.05))

    r = client.put(f"/api/v1/compile/{did}/bullets/0",
                   json={"text": "Directed engineering across the entire company."},
                   headers=H)

    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "edit_rejected"
    assert detail["reference_integrity"]["ok"] is True
    assert detail["entailment"]["ok"] is False
    assert detail["entailment"]["score"] == 0.05
    assert "Led a team of 4" in detail["entailment"]["violations"][0]["premise"]
    assert _texts(client, did) == before


def test_unknown_document_and_unknown_position_are_404(client, monkeypatch):
    did, _ = _compiled(client, monkeypatch)
    assert client.put("/api/v1/compile/99999/bullets/0", json={"text": "x"},
                      headers=H).status_code == 404
    r = client.put(f"/api/v1/compile/{did}/bullets/7", json={"text": "x"}, headers=H)
    assert r.status_code == 404
    assert r.json()["detail"] == "no line at that position in this document"


def test_empty_text_is_a_validation_error(client, monkeypatch):
    did, _ = _compiled(client, monkeypatch)
    assert client.put(f"/api/v1/compile/{did}/bullets/0", json={"text": ""},
                      headers=H).status_code == 422


def test_entailment_outage_is_a_typed_503_and_nothing_changes(client, monkeypatch):
    did, _ = _compiled(client, monkeypatch)
    before = _texts(client, did)

    def down(mid, rev):
        raise entailment.EntailmentUnavailable("model not loaded")
    monkeypatch.setattr(entailment, "_load", down)

    r = client.put(f"/api/v1/compile/{did}/bullets/0",
                   json={"text": "Led a team of 4 engineers."}, headers=H)

    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "entailment_unavailable"
    assert _texts(client, did) == before


def test_another_tenant_cannot_edit_the_document(client, monkeypatch):
    monkeypatch.setattr(settings, "smoke_test_token", "estate-token")
    demo.set_redis_for_tests(FakeRedis())
    a = client.post("/api/v1/demo/session").json()
    b = client.post("/api/v1/demo/session").json()
    ah = {"Authorization": f"Bearer {a['token']}"}
    bh = {"Authorization": f"Bearer {b['token']}"}
    did, _ = _compiled(client, monkeypatch, headers=ah)

    r = client.put(f"/api/v1/compile/{did}/bullets/0",
                   json={"text": "Led a team of 4 engineers."}, headers=bh)

    assert r.status_code == 403
    assert client.put(f"/api/v1/compile/{did}/bullets/0",
                      json={"text": "Led a team of 4 engineers."}).status_code == 401
    assert _texts(client, did, ah)[0].startswith("Led a team of 4 engineers at Acme")


def test_a_saved_letter_edit_ships_in_the_letter_pdf(client, monkeypatch):
    did, _ = _compiled(client, monkeypatch, letter=True)

    r = client.put(f"/api/v1/compile/{did}/bullets/1",
                   json={"text": "I ran Kubernetes in production at Globex."}, headers=H)
    assert r.status_code == 200, r.text

    pdf = client.get(f"/api/v1/compile/{did}/pdf", headers=H)
    text = " ".join("\n".join((p.extract_text() or "")
                              for p in PdfReader(io.BytesIO(pdf.content)).pages).split())
    assert "I ran Kubernetes in production at Globex." in text
