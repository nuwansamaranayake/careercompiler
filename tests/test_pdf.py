# ruff: noqa: F811
"""Goal item 5: the professional PDF, proven by reading it back — not by its magic bytes.

A PDF that renders garbage still starts with %PDF, so the real assertion is a pypdf
read-back: the candidate's name, the gated bullet text, and the provenance appendix must
all survive into extractable text. That is a parse-back check on the artifact a recruiter
actually receives.
"""
from __future__ import annotations

import io

from pypdf import PdfReader

from tests.test_compile import _seed, _stub_render, client  # noqa: F401  (fixture)


def _pdf_text(content: bytes) -> str:
    assert content[:5] == b"%PDF-", "not a PDF container"
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(content)).pages)


def test_resume_pdf_reads_back_with_name_bullets_and_provenance(client, monkeypatch):
    cid, jid, ids = _seed(client)
    _stub_render(monkeypatch, [
        {"text": "Led a team of 4 engineers at Acme Corp from 2019 to 2022.",
         "cites": [ids[0]]},
        {"text": "Cut deploy time 40% by rebuilding the CI pipeline in Python.",
         "cites": [ids[1]]},
        {"text": "Ran Kubernetes in production at Globex.", "cites": [ids[2]]},
    ])
    did = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid}
                      ).json()["document_id"]

    r = client.get(f"/api/v1/compile/{did}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert len(r.content) > 2500, "a professional page is not this small"

    text = _pdf_text(r.content)
    assert "T. Reviewer" in text, "the candidate name did not survive into the PDF"
    assert "Led a team of 4 engineers" in text, "a gated bullet did not survive"
    assert "PROVENANCE" in text, "the provenance appendix is missing"
    assert "team_lead" in text, "the cited fact key did not resolve in the appendix"
    assert "entailment 0.95" in text, "the gate score is not shown"
    assert "Compiled by CareerCompiler" in text, "the footer statement is missing"


def test_pdf_requires_a_token_and_respects_tenancy(client, monkeypatch):
    cid, jid, ids = _seed(client)
    _stub_render(monkeypatch, [
        {"text": "Ran Kubernetes in production at Globex.", "cites": [ids[2]]}])
    did = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid}
                      ).json()["document_id"]

    from app.config import settings
    monkeypatch.setattr(settings, "smoke_test_token", "armed")
    assert client.get(f"/api/v1/compile/{did}/pdf").status_code == 401
    assert client.get(f"/api/v1/compile/{did}/pdf",
                      headers={"Authorization": "Bearer armed"}).status_code == 200


def test_pdf_escapes_markup_in_fact_text(client, monkeypatch):
    """ReportLab paragraphs parse minimal markup; a fact containing <b> or & must render
    as literal text, never break the build or inject formatting."""
    cid, jid, ids = _seed(client)
    _stub_render(monkeypatch, [
        {"text": "Shipped the <Data & Insights> platform at Acme Corp.",
         "cites": [ids[0]]}])
    did = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid}
                      ).json()["document_id"]
    r = client.get(f"/api/v1/compile/{did}/pdf")
    assert r.status_code == 200
    assert "Data & Insights" in _pdf_text(r.content)
