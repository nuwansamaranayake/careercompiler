import pytest

from app.engine.embedding import HashingEmbedder
from app.engine.facts import claims_from_entries, extract_facts, Provenance
from app.engine.fit import build_report, render_markdown
from app.engine.jd import parse_jd, requirements_from_entries
from app.engine.matcher import match


class StubGateway:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def complete(self, *, model, messages, json_schema=None, temperature=0.0):
        self.calls.append({"model": model, "json_schema": json_schema})
        return self.payload


RESUME = ("Led migration of 42 services to Kubernetes, cutting deploy time 38%. "
          "Mentored 4 engineers.")


def test_extraction_anchors_spans_and_rejects_unanchored():
    gw = StubGateway({"claims": [
        {"claim_key": "platform_kubernetes", "kind": "skill",
         "statement": "Has migrated services to Kubernetes.",
         "quote": "migration of 42 services to Kubernetes", "confidence": 0.9},
        {"claim_key": "led_cross_functional_team", "kind": "role",
         "statement": "Led a cross-functional team of 12.",
         "quote": "led a cross-functional team of 12", "confidence": 0.8},
    ]})
    claims = extract_facts(gw, "m", RESUME, "resume.txt")
    assert len(claims) == 2                                   # nothing silently dropped
    ok, bad = claims
    assert ok.core.verification.status == "pending"
    start, end = ok.core.evidence_ref.span
    assert RESUME[start:end] == "migration of 42 services to Kubernetes"
    assert bad.core.verification.status == "rejected"         # quote not in source
    assert bad.core.evidence_ref.span is None
    assert gw.calls[0]["json_schema"] is not None


def test_extraction_refuses_without_model():
    with pytest.raises(RuntimeError, match="Refusing to guess"):
        extract_facts(StubGateway({}), "", RESUME, "resume.txt")


def test_data_entry_claims_are_self_attested():
    claims = claims_from_entries(
        [{"claim_key": "platform_kubernetes", "kind": "skill",
          "statement": "Runs production Kubernetes."}])
    assert claims[0].provenance is Provenance.self_attested
    assert "self_attested" in claims[0].core.verification.gates


def test_jd_entry_path_validates():
    reqs = requirements_from_entries(
        [{"req_key": "kubernetes", "text": "Production Kubernetes experience",
          "kind": "skill", "must_have": True}])
    assert reqs[0].must_have is True
    with pytest.raises(Exception):
        requirements_from_entries([{"req_key": "", "text": "x", "kind": "skill",
                                    "must_have": False}])


def test_jd_parse_uses_schema():
    gw = StubGateway({"requirements": [
        {"req_key": "kubernetes", "text": "Kubernetes required", "kind": "skill",
         "must_have": True}]})
    reqs = parse_jd(gw, "m", "We require Kubernetes.")
    assert reqs[0].req_key == "kubernetes"
    assert gw.calls[0]["json_schema"] is not None


def _graph():
    return claims_from_entries([
        {"claim_key": "platform_kubernetes", "kind": "skill",
         "statement": "Migrated 42 services to Kubernetes in production."},
        {"claim_key": "mentored_engineers", "kind": "role",
         "statement": "Mentored a team of 4 engineers."},
    ])


def test_matcher_direct_transferable_and_gap():
    reqs = requirements_from_entries([
        {"req_key": "kubernetes", "text": "Production Kubernetes experience",
         "kind": "skill", "must_have": True},
        {"req_key": "team_leadership", "text": "Experience mentoring or leading engineers",
         "kind": "experience", "must_have": False},
        {"req_key": "rust", "text": "Rust systems programming", "kind": "skill",
         "must_have": True},
    ])
    rows = match(reqs, _graph(), HashingEmbedder())
    by_key = {r.req_key: r for r in rows}
    assert by_key["kubernetes"].status == "matched" and by_key["kubernetes"].direct
    assert by_key["rust"].status == "gap"
    lead = by_key["team_leadership"]
    assert lead.status in ("matched", "partial")
    if lead.status == "partial":
        assert lead.direct is False and "transferable" in lead.explanation


def test_rejected_claims_never_match():
    gw = StubGateway({"claims": [
        {"claim_key": "platform_kubernetes", "kind": "skill",
         "statement": "Kubernetes expert.", "quote": "NOT IN SOURCE", "confidence": 0.9}]})
    rejected_only = extract_facts(gw, "m", RESUME, "resume.txt")
    reqs = requirements_from_entries(
        [{"req_key": "kubernetes", "text": "Kubernetes", "kind": "skill",
          "must_have": True}])
    rows = match(reqs, rejected_only, HashingEmbedder())
    assert rows[0].status == "gap"


def test_fit_verdict_honest_about_musthave_gap():
    reqs = requirements_from_entries([
        {"req_key": "kubernetes", "text": "Kubernetes", "kind": "skill", "must_have": True},
        {"req_key": "rust", "text": "Rust systems programming", "kind": "skill",
         "must_have": True},
    ])
    report = build_report(match(reqs, _graph(), HashingEmbedder()))
    assert report.verdict == "do_not_apply"
    assert report.disqualifying_gaps == ["rust"]
    md = render_markdown(report)
    assert "DO NOT APPLY" in md and "rust" in md


def test_fit_verdict_apply_when_no_musthave_gap():
    reqs = requirements_from_entries([
        {"req_key": "kubernetes", "text": "Kubernetes", "kind": "skill", "must_have": True}])
    report = build_report(match(reqs, _graph(), HashingEmbedder()))
    assert report.verdict == "apply" and report.case_against == ""
