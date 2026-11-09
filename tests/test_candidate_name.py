"""The name on the documents.

The workspace asks for two things, a resume and a job description. It does not ask for a
name, so the name that signs the cover letter has to come from the resume, by a rule a
person can see and correct: the first line, when it looks like a name. When it does not,
the placeholder is an obvious placeholder, never a guess. A rename is one call and takes
effect on the next download, because documents read the name at render time.
"""
from __future__ import annotations

import io

import pytest
import sqlalchemy as sa
from docx import Document
from fastapi.testclient import TestClient
from groundwork.testing import FakeRedis
from pypdf import PdfReader

from app import db, demo, routes
from app.config import settings
from app.engine import entailment
from app.engine.linker import Bullet
from app.main import app
from app.routes import PLACEHOLDER_NAME, name_from_resume

H = {}
RESUME = "Jordan Alvarez\nPlatform engineer. Portland, Oregon.\n\nRan Kubernetes in production at Globex.\n"


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


@pytest.mark.parametrize("first_line, expected", [
    ("Jordan Alvarez", "Jordan Alvarez"),
    ("  Jordan  Alvarez  ", "Jordan Alvarez"),
    ("JORDAN ALVAREZ", "Jordan Alvarez"),
    ("Mary-Jane O'Neil", "Mary-Jane O'Neil"),
    ("Dr. Nuwan Samaranayake", "Dr. Nuwan Samaranayake"),
    ("José Álvarez Núñez", "José Álvarez Núñez"),
    ("Jordan Alvarez, PMP", "Jordan Alvarez"),
    ("Jordan Alvarez | Platform Engineer", "Jordan Alvarez"),
])
def test_a_name_like_first_line_is_the_name(first_line, expected):
    assert name_from_resume(f"{first_line}\nPortland, Oregon\n") == expected


@pytest.mark.parametrize("first_line", [
    "Curriculum Vitae", "RESUME", "Professional Summary",
    "jordan.alvarez@example.com", "+1 832 555 0100",
    "Senior platform engineer with 10 years of experience building services",
    "Built and operated Python services in production.",
    "Jordan", "platform engineer", "",
])
def test_a_first_line_that_is_not_a_name_is_not_guessed(first_line):
    assert name_from_resume(f"{first_line}\nmore text\n") is None


def test_leading_blank_lines_are_skipped_and_empty_text_has_no_name():
    assert name_from_resume("\n\n  \nJordan Alvarez\nrest") == "Jordan Alvarez"
    assert name_from_resume("") is None
    assert name_from_resume("   \n \n") is None


def test_pasted_resume_without_a_name_is_named_from_its_first_line(client):
    r = client.post("/api/v1/candidates", json={"resume_text": RESUME}, headers=H)
    assert r.status_code == 201, r.text
    assert r.json() == {"candidate_id": r.json()["candidate_id"],
                        "name": "Jordan Alvarez", "name_source": "resume_first_line"}


def test_a_provided_name_always_wins(client):
    r = client.post("/api/v1/candidates",
                    json={"name": "T. Reviewer", "resume_text": RESUME}, headers=H)
    assert r.json()["name"] == "T. Reviewer"
    assert r.json()["name_source"] == "provided"


def test_no_name_and_no_readable_first_line_is_an_obvious_placeholder(client):
    r = client.post("/api/v1/candidates",
                    json={"resume_text": "Professional Summary\nRan Kubernetes."}, headers=H)
    assert r.json()["name"] == PLACEHOLDER_NAME == "Your Name"
    assert r.json()["name_source"] == "placeholder"
    bare = client.post("/api/v1/candidates", json={}, headers=H).json()
    assert bare["name"] == PLACEHOLDER_NAME and bare["name_source"] == "placeholder"


def test_an_uploaded_docx_without_a_name_is_named_from_its_first_line(client):
    doc = Document()
    doc.add_paragraph("Jordan Alvarez")
    doc.add_paragraph("Ran Kubernetes in production at Globex.")
    buf = io.BytesIO()
    doc.save(buf)

    r = client.post("/api/v1/candidates/upload", headers=H, files={
        "file": ("cv.docx", buf.getvalue(),
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Jordan Alvarez" and body["name_source"] == "resume_first_line"
    assert body["chars"] > 20


def test_an_upload_with_a_name_keeps_it(client):
    doc = Document()
    doc.add_paragraph("Jordan Alvarez")
    buf = io.BytesIO()
    doc.save(buf)
    r = client.post("/api/v1/candidates/upload", headers=H, data={"name": "My upload"},
                    files={"file": ("cv.docx", buf.getvalue(), "application/octet-stream")})
    assert r.json()["name"] == "My upload" and r.json()["name_source"] == "provided"


def _letter(client, monkeypatch, cid, headers=H) -> int:
    client.post(f"/api/v1/candidates/{cid}/claims", headers=headers, json={"entries": [
        {"claim_key": "k8s", "kind": "skill",
         "statement": "Ran Kubernetes in production at Globex."}]})
    jid = client.post("/api/v1/jobs", headers=headers, json={
        "title": "Platform Engineer", "requirements": [
            {"req_key": "k8s", "text": "Kubernetes in production", "kind": "skill",
             "must_have": True}]}).json()["job_id"]
    monkeypatch.setattr(routes, "draft_letter", lambda gateway, model, claims, job_title, reqs:
                        [Bullet("I ran Kubernetes in production at Globex.",
                                [claims[0].core.claim_id])])
    r = client.post("/api/v1/cover-letter", json={"candidate_id": cid, "job_id": jid},
                    headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["signoff"].startswith("Sincerely,")
    return r.json()["document_id"]


def _pdf_text(client, did, headers=H) -> str:
    pdf = client.get(f"/api/v1/compile/{did}/pdf", headers=headers)
    return " ".join("\n".join((p.extract_text() or "")
                              for p in PdfReader(io.BytesIO(pdf.content)).pages).split())


def test_a_rename_signs_the_next_download_without_recompiling(client, monkeypatch):
    cid = client.post("/api/v1/candidates",
                      json={"resume_text": "Professional Summary\nx"},
                      headers=H).json()["candidate_id"]
    did = _letter(client, monkeypatch, cid)
    assert PLACEHOLDER_NAME in _pdf_text(client, did)

    r = client.patch(f"/api/v1/candidates/{cid}", json={"name": "  Jordan Alvarez "}, headers=H)

    assert r.status_code == 200, r.text
    assert r.json() == {"candidate_id": cid, "name": "Jordan Alvarez", "name_source": "provided"}
    text = _pdf_text(client, did)
    assert "Jordan Alvarez" in text and PLACEHOLDER_NAME not in text


def test_rename_validation_and_missing_candidate(client):
    cid = client.post("/api/v1/candidates", json={"name": "A B"}, headers=H).json()["candidate_id"]
    assert client.patch(f"/api/v1/candidates/{cid}", json={"name": "   "},
                        headers=H).status_code == 422
    assert client.patch(f"/api/v1/candidates/{cid}", json={"name": "x" * 121},
                        headers=H).status_code == 422
    assert client.patch(f"/api/v1/candidates/{cid}", json={}, headers=H).status_code == 422
    assert client.patch("/api/v1/candidates/99999", json={"name": "A B"},
                        headers=H).status_code == 404


def test_a_rename_keeps_the_tenant_prefix_and_respects_tenancy(client, monkeypatch):
    monkeypatch.setattr(settings, "smoke_test_token", "estate-token")
    demo.set_redis_for_tests(FakeRedis())
    a = client.post("/api/v1/demo/session").json()
    b = client.post("/api/v1/demo/session").json()
    ah = {"Authorization": f"Bearer {a['token']}"}
    bh = {"Authorization": f"Bearer {b['token']}"}
    cid = client.post("/api/v1/candidates", json={"resume_text": RESUME},
                      headers=ah).json()["candidate_id"]

    def stored() -> str:
        with db.get_session() as s:
            return s.execute(sa.select(db.candidates.c.name)
                             .where(db.candidates.c.id == cid)).scalar_one()

    prefix = stored()[: -len("Jordan Alvarez")]
    assert prefix.startswith("demo-") and stored().endswith("Jordan Alvarez")

    assert client.patch(f"/api/v1/candidates/{cid}", json={"name": "Eve"},
                        headers=bh).status_code == 403
    assert client.patch(f"/api/v1/candidates/{cid}", json={"name": "Eve"}).status_code == 401
    assert stored() == prefix + "Jordan Alvarez"

    # The estate token carries no prefix of its own; the row's prefix must survive it,
    # or the retention sweep would stop finding this tenant's personal data.
    for headers in (ah, {"Authorization": "Bearer estate-token"}):
        r = client.patch(f"/api/v1/candidates/{cid}", json={"name": "J. Alvarez"},
                         headers=headers)
        assert r.status_code == 200 and r.json()["name"] == "J. Alvarez"
        assert stored() == prefix + "J. Alvarez"
