# ruff: noqa: F811
"""Route branches not reached by the pipeline tests: input errors, tenancy, gate
exhaustion, the JD parse endpoint, and resume upload with real PDF and docx bytes."""
from __future__ import annotations

import io

import pytest
import sqlalchemy as sa
from docx import Document
from fastapi.testclient import TestClient
from groundwork.testing import FakeRedis
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app import db, demo, routes
from app.config import settings
from app.engine import entailment
from app.engine.linker import Bullet
from app.main import app
from tests.test_compile import FACTS, H, REQS, _seed, _stub_render, client  # noqa: F401


def _stub_letter(monkeypatch, drafts):
    monkeypatch.setattr(routes, "draft_letter",
                        lambda gateway, model, claims, job_title, reqs:
                        [Bullet(d["text"], list(d["cites"])) for d in drafts])
    monkeypatch.setattr(routes, "revise_renderings",
                        lambda gateway, model, offending, letter=False: {})


class FakeGateway:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def complete(self, *, model, messages, json_schema):
        self.calls.append(messages)
        return self.result


def _candidate(client, name="C"):
    return client.post("/api/v1/candidates", json={"name": name}, headers=H
                       ).json()["candidate_id"]


def _job(client, **kw):
    return client.post("/api/v1/jobs", json={"title": "Eng", **kw}, headers=H
                       ).json()["job_id"]


# ---- input validation and 404s -----------------------------------------------------

def test_add_claims_to_unknown_candidate_is_404(client):
    r = client.post("/api/v1/candidates/999/claims", json={"entries": FACTS}, headers=H)
    assert r.status_code == 404
    assert r.json()["detail"] == "candidate not found"


def test_extract_without_resume_document_is_422(client):
    cid = _candidate(client)
    r = client.post(f"/api/v1/candidates/{cid}/claims/extract", headers=H)
    assert r.status_code == 422
    assert "no resume document" in r.json()["detail"]


def test_create_job_with_malformed_requirement_is_422_and_stores_nothing(client):
    r = client.post("/api/v1/jobs", json={"title": "Eng", "requirements": [{"req_key": "x"}]},
                    headers=H)
    assert r.status_code == 422
    with db.get_session() as s:
        assert s.execute(sa.select(sa.func.count()).select_from(db.job_postings)).scalar() == 0


def test_fit_for_job_without_requirements_is_422(client):
    cid = _candidate(client)
    client.post(f"/api/v1/candidates/{cid}/claims", json={"entries": FACTS}, headers=H)
    jid = _job(client)
    r = client.post("/api/v1/fit", json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 422
    assert r.json()["detail"] == "job has no requirements"


def test_get_missing_fit_report_is_404(client):
    r = client.get("/api/v1/fit/12345", headers=H)
    assert r.status_code == 404
    assert r.json()["detail"] == "fit report not found"


# ---- JD parse endpoint -------------------------------------------------------------

def test_parse_requirements_stores_what_the_model_returns(client, monkeypatch):
    jid = _job(client, description="Must know Kubernetes. Terraform is a plus.")
    gw = FakeGateway({"requirements": [
        {"req_key": "k8s", "text": "Kubernetes", "kind": "skill", "must_have": True},
        {"req_key": "tf", "text": "Terraform", "kind": "skill", "must_have": False}]})
    monkeypatch.setattr(routes, "_gateway", lambda: gw)
    monkeypatch.setattr(settings, "llm_model_extraction", "stub/extract")
    r = client.post(f"/api/v1/jobs/{jid}/requirements/parse", headers=H)
    assert r.status_code == 201
    assert r.json() == {"parsed": 2}
    with db.get_session() as s:
        rows = s.execute(sa.select(db.requirements.c.req_key, db.requirements.c.must_have)
                         .where(db.requirements.c.job_id == jid)
                         .order_by(db.requirements.c.id)).all()
    assert [(r.req_key, bool(r.must_have)) for r in rows] == [("k8s", True), ("tf", False)]
    assert gw.calls[0][1]["content"] == "Must know Kubernetes. Terraform is a plus."


def test_parse_requirements_missing_job_and_missing_description(client):
    assert client.post("/api/v1/jobs/999/requirements/parse", headers=H).status_code == 404
    jid = _job(client)
    r = client.post(f"/api/v1/jobs/{jid}/requirements/parse", headers=H)
    assert r.status_code == 422
    assert r.json()["detail"] == "job has no description to parse"


# ---- compile and cover letter error branches ---------------------------------------

@pytest.mark.parametrize("path,extra", [("/api/v1/compile", {}),
                                        ("/api/v1/cover-letter", {})])
def test_pipeline_input_errors(client, path, extra):
    cid_empty = _candidate(client)
    jid = _job(client, requirements=REQS)
    r = client.post(path, json={"candidate_id": cid_empty, "job_id": jid, **extra}, headers=H)
    assert r.status_code == 422 and r.json()["detail"] == "candidate has no claims"

    cid, _, _ = _seed(client)
    r = client.post(path, json={"candidate_id": cid, "job_id": 9999, **extra}, headers=H)
    assert r.status_code == 404 and r.json()["detail"] == "job not found"

    bare = _job(client)
    r = client.post(path, json={"candidate_id": cid, "job_id": bare, **extra}, headers=H)
    assert r.status_code == 422 and r.json()["detail"] == "job has no requirements"


@pytest.mark.parametrize("path", ["/api/v1/compile", "/api/v1/cover-letter"])
def test_all_rejected_facts_give_typed_empty_selection(client, path):
    cid, jid, ids = _seed(client)
    for i in ids:
        assert client.post(f"/api/v1/facts/{i}/verify", json={"status": "rejected"},
                           headers=H).status_code == 200
    r = client.post(path, json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 422
    d = r.json()["detail"]
    assert d["error"] == "empty_selection"
    assert {v["reason"] for v in d["violations"]} == {"rejected_span_anchor"}
    assert {v["claim_key"] for v in d["violations"]} == {"team_lead", "deploy_time", "k8s"}


def test_compile_persists_omissions_for_unselected_facts(client, monkeypatch):
    cid, jid, ids = _seed(client)
    client.post(f"/api/v1/facts/{ids[1]}/verify", json={"status": "rejected"}, headers=H)
    _stub_render(monkeypatch, [
        {"text": "Led a team of 4 engineers at Acme Corp from 2019 to 2022.",
         "cites": [ids[0]]},
        {"text": "Ran Kubernetes in production at Globex.", "cites": [ids[2]]}])
    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 201, r.text
    assert [(o["claim_key"], o["reason"]) for o in r.json()["omitted"]] == [
        ("deploy_time", "rejected_span_anchor")]
    prov = client.get(f"/api/v1/compile/{r.json()['document_id']}", headers=H).json()
    assert [o["claim_key"] for o in prov["omitted"]] == ["deploy_time"]


def test_cover_letter_persists_omissions(client, monkeypatch):
    cid, jid, ids = _seed(client)
    client.post(f"/api/v1/facts/{ids[1]}/verify", json={"status": "rejected"}, headers=H)
    _stub_letter(monkeypatch, [
        {"text": "I led a team of 4 engineers at Acme Corp from 2019 to 2022.",
         "cites": [ids[0]]}])
    r = client.post("/api/v1/cover-letter", json={"candidate_id": cid, "job_id": jid},
                    headers=H)
    assert r.status_code == 201, r.text
    assert [o["claim_key"] for o in r.json()["omitted"]] == ["deploy_time"]
    pdf = client.get(f"/api/v1/compile/{r.json()['document_id']}/pdf", headers=H)
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "Dear Hiring Team," in text and "Senior Backend Engineer" in text


@pytest.mark.parametrize("path", ["/api/v1/compile", "/api/v1/cover-letter"])
def test_empty_render_is_502(client, monkeypatch, path):
    cid, jid, _ = _seed(client)
    monkeypatch.setattr(routes, "draft_bullets", lambda *a, **k: [])
    monkeypatch.setattr(routes, "draft_letter", lambda *a, **k: [])
    r = client.post(path, json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 502
    assert r.json()["detail"] == "the renderer returned no sentences to gate"


@pytest.mark.parametrize("path", ["/api/v1/compile", "/api/v1/cover-letter"])
def test_entailment_unavailable_is_503_and_persists_nothing(client, monkeypatch, path):
    cid, jid, ids = _seed(client)
    _stub_render(monkeypatch, [{"text": "Ran Kubernetes in production at Globex.",
                                "cites": [ids[2]]}])
    _stub_letter(monkeypatch, [{"text": "I ran Kubernetes in production at Globex.",
                                "cites": [ids[2]]}])

    def unavailable(mid, rev):
        raise entailment.EntailmentUnavailable("weights not in image")

    monkeypatch.setattr(entailment, "_load", unavailable)
    r = client.post(path, json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 503
    assert r.json()["detail"] == {"error": "entailment_unavailable",
                                  "message": "weights not in image"}
    with db.get_session() as s:
        assert s.execute(sa.select(sa.func.count()).select_from(db.compiled_documents)
                         ).scalar() == 0


def test_gates_are_the_authority_when_the_revision_changes_nothing(client, monkeypatch):
    """The first entailment pass objects, the revision returns nothing, and the final
    verdict is re-issued by the gate itself. A gate that now accepts ships the draft."""
    cid, jid, ids = _seed(client)
    _stub_render(monkeypatch, [{"text": "Ran Kubernetes in production at Globex.",
                                "cites": [ids[2]]}])
    loads = {"n": 0}

    def flaky_load(mid, rev):
        loads["n"] += 1
        first = loads["n"] == 1
        return lambda p, h: 0.001 if first else 0.95

    monkeypatch.setattr(entailment, "_load", flaky_load)
    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["bullets"][0]["entailment"] == 0.95
    assert [x["stage"] for x in body["repair"]] == ["entailment", "revision_unchanged"]


def test_exhausted_numeral_precheck_ends_in_linker_verdict(client, monkeypatch):
    cid, jid, ids = _seed(client)
    _stub_render(monkeypatch, [{"text": "Led a team of 40 engineers at Acme Corp.",
                                "cites": [ids[0]]}])
    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid}, headers=H)
    assert r.status_code == 422
    d = r.json()["detail"]
    assert d["error"] == "reference_integrity"
    assert d["violations"][0]["failure"] == "unsupported_number"
    assert d["repair"][0]["stage"] == "numeral_precheck"
    assert d["repair"][-1]["stage"] == "revision_unchanged"


# ---- tenancy on a job-only route ---------------------------------------------------

@pytest.fixture()
def demo_client(monkeypatch):
    engine = sa.create_engine("sqlite://", poolclass=sa.pool.StaticPool,
                              connect_args={"check_same_thread": False})
    db.metadata.create_all(engine)
    db.set_engine_for_tests(engine)
    monkeypatch.setattr(settings, "smoke_test_token", "estate-token")
    demo.set_redis_for_tests(FakeRedis())
    return TestClient(app)


def test_demo_token_cannot_parse_another_tenants_job(demo_client):
    a = demo_client.post("/api/v1/demo/session").json()
    b = demo_client.post("/api/v1/demo/session").json()
    ah = {"Authorization": f"Bearer {a['token']}"}
    r = demo_client.post(f"/api/v1/jobs/{b['jobs'][0]['job_id']}/requirements/parse",
                         headers=ah)
    assert r.status_code == 403
    # a job that does not exist is denied the same way: no existence oracle
    r = demo_client.post("/api/v1/jobs/987654/requirements/parse", headers=ah)
    assert r.status_code == 403


# ---- interview pack without a stored fit report ------------------------------------

def test_interview_pack_without_fit_report_reports_unknown_verdict(client, monkeypatch):
    cid, jid, ids = _seed(client)
    _stub_render(monkeypatch, [{"text": "Ran Kubernetes in production at Globex.",
                                "cites": [ids[2]]}])
    did = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid},
                      headers=H).json()["document_id"]
    monkeypatch.setattr(routes, "draft_questions",
                        lambda gw, model, title, bullets, gaps: {"B1": ["Which clusters?"]})
    r = client.post("/api/v1/interview-pack", json={"document_id": did}, headers=H)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["verdict"] == "unknown"
    assert body["case_against"] is None
    assert body["gaps"] == []
    assert body["bullets"][0]["questions"] == ["Which clusters?"]
    assert body["bullets"][0]["metrics"] == []


# ---- resume upload with real files -------------------------------------------------

def _pdf(lines):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for ln in lines:
        c.drawString(72, y, ln)
        y -= 20
    c.showPage()
    c.save()
    return buf.getvalue()


def _docx(paras):
    d = Document()
    for p in paras:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _upload(client, name, filename, data):
    return client.post("/api/v1/candidates/upload", data={"name": name},
                       files={"file": (filename, data, "application/octet-stream")},
                       headers=H)


def _stored_text(cid):
    with db.get_session() as s:
        return s.execute(sa.select(db.source_documents.c.text, db.source_documents.c.name)
                         .where(db.source_documents.c.candidate_id == cid)).one()


def test_upload_pdf_extracts_and_stores_text(client):
    r = _upload(client, "Pat", "Resume.PDF", _pdf(["Led a team of 4 engineers.",
                                                   "Ran Kubernetes in production."]))
    assert r.status_code == 201, r.text
    row = _stored_text(r.json()["candidate_id"])
    assert row.name == "resume.pdf"
    assert "Led a team of 4 engineers." in row.text
    assert "Ran Kubernetes in production." in row.text
    assert r.json()["chars"] == len(row.text)


def test_upload_docx_normalises_layout_and_keeps_paragraphs(client):
    r = _upload(client, "Pat", "cv.docx", _docx(["First   line", "wrapped  on", "",
                                                 "Second paragraph", ""]))
    assert r.status_code == 201, r.text
    row = _stored_text(r.json()["candidate_id"])
    assert row.text == "First line wrapped on\nSecond paragraph"


def test_upload_rejections(client):
    big = _upload(client, "Pat", "cv.pdf", b"0" * 2_000_001)
    assert big.status_code == 413
    assert "2 MB" in big.json()["detail"]

    txt = _upload(client, "Pat", "cv.txt", b"plain text")
    assert txt.status_code == 415
    assert "PDF or docx only" in txt.json()["detail"]

    junk = _upload(client, "Pat", "cv.pdf", b"this is not a pdf")
    assert junk.status_code == 422
    assert junk.json()["detail"] == "the file could not be parsed as PDF or docx"

    junk_docx = _upload(client, "Pat", "cv.docx", b"this is not a docx")
    assert junk_docx.status_code == 422

    empty = _upload(client, "Pat", "cv.pdf", _pdf([]))
    assert empty.status_code == 422
    assert "no extractable text" in empty.json()["detail"]
    with db.get_session() as s:
        assert s.execute(sa.select(sa.func.count()).select_from(db.candidates)).scalar() == 0


def test_upload_requires_the_token_when_armed(client, monkeypatch):
    monkeypatch.setattr(settings, "smoke_test_token", "armed")
    r = client.post("/api/v1/candidates/upload", data={"name": "Pat"},
                    files={"file": ("cv.pdf", _pdf(["x"]), "application/pdf")})
    assert r.status_code == 401


@pytest.mark.parametrize("raw,expected", [
    ("a  b\tc\r\nd", "a b c d"),
    ("one\n\ntwo\n\n\nthree", "one\ntwo\nthree"),
    ("\n\n  lone  \n\n", "lone"),
    ("", ""),
])
def test_normalize_doc_text(raw, expected):
    assert routes._normalize_doc_text(raw) == expected
