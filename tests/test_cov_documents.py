"""Document writers called directly, read back with pypdf and python-docx."""
from __future__ import annotations

import io

from docx import Document
from pypdf import PdfReader

from app.engine import docx_out, interview, pdf_out
from app.engine.facts import claims_from_entries
from app.engine.selector import Omission, OmissionReason


def _setup():
    claims = claims_from_entries([
        {"claim_key": "lead", "kind": "role",
         "statement": "Led a team of 4 engineers at Acme Corp from 2019 to 2022."},
    ])
    cid = claims[0].core.claim_id
    by_id = {cid: claims[0]}
    sentences = [
        {"position": 0, "text": "I led 4 engineers.", "cites": [cid], "entailment": 0.93},
        {"position": 1, "text": "Orphan <sentence> & more.", "cites": ["deadbeef"],
         "entailment": None},
    ]
    omissions = [Omission("x", "old_job", OmissionReason.budget_exhausted,
                          "no room on the page")]
    return by_id, sentences, omissions, cid


def _pdf_text(b: bytes) -> str:
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(b)).pages)


def _docx_text(b: bytes) -> str:
    return "\n".join(p.text for p in Document(io.BytesIO(b)).paragraphs)


def test_resume_pdf_shows_unresolved_cite_omissions_and_score():
    by_id, sentences, omissions, cid = _setup()
    text = _pdf_text(pdf_out.render_pdf("Ada L.", "Engineer", sentences, by_id, omissions,
                                        "NLI 0.5"))
    assert "Ada L." in text
    assert "deadbeef (not resolved)" in text
    assert "Orphan <sentence> & more." in text
    assert "entailment 0.93" in text
    assert "WHAT WAS LEFT OUT, AND WHY" in text
    assert "old_job: budget_exhausted" in text
    assert "no room on the page" in text
    assert "lead:" in text and cid in text


def test_resume_pdf_without_omissions_has_no_left_out_section():
    by_id, sentences, _, _ = _setup()
    text = _pdf_text(pdf_out.render_pdf("Ada L.", "Engineer", sentences, by_id, [], "n"))
    assert "WHAT WAS LEFT OUT" not in text


def test_letter_pdf_carries_frame_sentences_and_provenance():
    by_id, sentences, _, cid = _setup()
    frame = docx_out.letter_scaffold("Ada L.", "Engineer")
    text = _pdf_text(pdf_out.render_letter_pdf("Ada L.", "Engineer", sentences, by_id,
                                               "NLI 0.5", frame))
    assert "Dear Hiring Team," in text
    assert "apply for the Engineer role" in text
    assert "I led 4 engineers." in text
    assert "Sincerely," in text
    assert "deadbeef (not resolved)" in text
    assert "bracketed sentence" in text


def test_letter_scaffold_is_deterministic_and_names_role_and_candidate():
    f = docx_out.letter_scaffold("Ada L.", "Staff Engineer")
    assert f["signoff"] == "Sincerely,\nAda L."
    assert "Staff Engineer" in f["opening"]


def test_resume_docx_unresolved_omissions_and_score():
    by_id, sentences, omissions, cid = _setup()
    out = docx_out.render_docx("Ada L.", "Engineer", sentences, by_id, omissions, "NLI 0.5")
    text = _docx_text(out)
    assert "deadbeef (not resolved)" in text
    assert "entailment 0.93" in text
    assert "old_job: budget_exhausted — no room on the page" in text
    assert "lead: Led a team of 4 engineers" in text


def test_letter_docx_unresolved_cite_and_score():
    by_id, sentences, _, cid = _setup()
    text = _docx_text(docx_out.render_letter_docx("Ada L.", "Engineer", sentences, by_id,
                                                  "NLI 0.5"))
    assert "Dear Hiring Team," in text
    assert "deadbeef (not resolved)" in text
    assert "entailment 0.93" in text
    assert "Sincerely," in text


def test_interview_pack_with_gaps_questions_and_case_against():
    entries = [
        {"text": "I led 4 engineers.",
         "facts": [{"key": "lead", "statement": "Led a team of 4.", "provenance": "self_attested"}],
         "metrics": ["4"], "questions": ["Why only 4?"]},
        {"text": "Ran Kubernetes.",
         "facts": [{"key": "k8s", "statement": "Ran Kubernetes.", "provenance": "self_attested"}],
         "metrics": [], "questions": []},
    ]
    gaps = [{"requirement": "rust", "case": "No Rust anywhere.", "questions": ["Any Rust?"]}]
    out = interview.render_pack_docx("Ada L.", "Engineer", "do_not_apply", "Missing rust.",
                                     entries, gaps, "A note.")
    text = _docx_text(out)
    assert "Interview preparation — Ada L." in text
    assert "fit verdict: do not apply" in text
    assert "metrics in the evidence: 4" in text
    assert "none — the facts carry no number" in text
    assert "Why only 4?" in text
    assert "no questions generated for this bullet" in text
    assert "The fit report's case against applying: Missing rust." in text
    assert "rust: No Rust anywhere." in text
    assert "Any Rust?" in text
    assert "Prepare the honest answer" in text


def test_interview_pack_without_gaps_or_case():
    out = interview.render_pack_docx("Ada L.", "Engineer", "apply", None, [], [], "n")
    text = _docx_text(out)
    assert "The fit report found no unmatched requirements." in text
    assert "case against applying" not in text


def test_metrics_of_dedupes_and_keeps_order():
    assert interview.metrics_of(["Cut 40% in 2020", "40% again, 12"]) == ["40%", "2020", "12"]
    assert interview.metrics_of(["no digits"]) == []
