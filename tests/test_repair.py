"""The repair loop: pre-check arithmetic, constrained revision, bounded rounds, and the
gates' authority over the verdict.

What must hold: a bad draft that CAN be repaired ships repaired; one that cannot fails
with the same typed verdict the gates always issued, plus the audited repair log; the
loop is bounded at three rounds; and the honest numeral cases (words, formatting, years)
never trigger a repair at all. The gates themselves are exercised unstubbed except the
NLI scorer seam, exactly as the planted-negative suites do.
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app import db, routes
from app.config import settings
from app.engine import entailment
from app.engine.facts import claims_from_entries
from app.engine.linker import Bullet
from app.engine.revise import numeral_violations
from app.main import app

H = {}

FACTS = [
    {"claim_key": "ci_pipeline", "kind": "outcome",
     "statement": "Cut deploy time 40% at Acme Corp by rebuilding the CI pipeline."},
    {"claim_key": "k8s", "kind": "skill",
     "statement": "Ran Kubernetes in production at Globex, operating 40 services."},
]
REQS = [
    {"req_key": "ci", "text": "CI/CD ownership", "kind": "experience", "must_have": True},
    {"req_key": "k8s", "text": "Kubernetes in production", "kind": "skill",
     "must_have": True},
]


# ------------------------------------------------------------------ pre-check unit tests
def _claims_by_id(entries):
    claims = claims_from_entries(entries)
    return claims, {c.core.claim_id: c for c in claims}


def test_percent_vs_bare_number_is_flagged_with_the_licensed_spelling():
    claims, by_id = _claims_by_id(FACTS)
    cid = claims[0].core.claim_id  # the 40% fact
    v = numeral_violations([Bullet("Cut deploy time by 40 percent at Acme Corp.",
                                   [cid])], by_id)
    assert len(v) == 1
    assert v[0]["bad_tokens"] == ["40"]
    assert "40%" in v[0]["allowed_tokens"]


def test_the_count_fact_licenses_the_bare_number():
    claims, by_id = _claims_by_id(FACTS)
    cid = claims[1].core.claim_id  # "operating 40 services"
    assert numeral_violations([Bullet("Operated 40 services on Kubernetes at Globex.",
                                      [cid])], by_id) == []


def test_honest_cases_never_trigger_the_precheck():
    claims, by_id = _claims_by_id([
        {"claim_key": "pay", "kind": "outcome", "statement": "Saved $4,000 per month."},
        {"claim_key": "yr", "kind": "role", "statement": "Joined Acme Corp in 2019."},
    ])
    pay, yr = claims[0].core.claim_id, claims[1].core.claim_id
    # A formatted variant folds to the same token; a word-numeral carries no digit;
    # a year present in the fact passes.
    assert numeral_violations([Bullet("Saved 4000 per month.", [pay])], by_id) == []
    assert numeral_violations([Bullet("Saved four thousand monthly.", [pay])], by_id) == []
    assert numeral_violations([Bullet("Joined Acme Corp in 2019.", [yr])], by_id) == []


def test_suffix_facts_license_their_digit_prefix_exactly_as_the_linker_does():
    # The linker's extraction reads "12M" as the token "12" (digit branch wins the
    # alternation), so "12 million" in a draft is licensed by a "12M" fact — for the
    # pre-check AND the linker, identically. The pre-check must mirror the linker's
    # arithmetic, not invent a stricter one: strictness changes belong to the gate,
    # and the gate does not change.
    claims, by_id = _claims_by_id([
        {"claim_key": "rows", "kind": "scope", "statement": "Migrated a 12M row table."}])
    cid = claims[0].core.claim_id
    assert numeral_violations(
        [Bullet("Migrated a 12 million row table.", [cid])], by_id) == []
    # A digit from nowhere is still flagged.
    v = numeral_violations([Bullet("Migrated a 15M row table.", [cid])], by_id)
    assert v and v[0]["bad_tokens"] == ["15"]


# ---------------------------------------------------------------- embedder resolution
def test_auto_embedder_resolves_by_configuration(monkeypatch):
    """FAIL-0012: the hashing embedder's noise floor sits at the match threshold, so
    'auto' must resolve to real embeddings whenever the deployment can run them, and
    to hashing only on the keyless path — and never silently: the resolved name rides
    the fit response and the stored report."""
    from app.engine.embedding import HashingEmbedder, OpenRouterEmbedder
    from app.routes import _embedder
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "embedding_model", "stub/embed")
    assert isinstance(_embedder("auto"), OpenRouterEmbedder)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    assert isinstance(_embedder("auto"), HashingEmbedder)


# ------------------------------------------------------------------ loop tests (API)
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


def _seed(client):
    cid = client.post("/api/v1/candidates", json={"name": "T. Reviewer"},
                      headers=H).json()["candidate_id"]
    client.post(f"/api/v1/candidates/{cid}/claims", json={"entries": FACTS}, headers=H)
    jid = client.post("/api/v1/jobs", json={"title": "Platform Engineer",
                                            "requirements": REQS},
                      headers=H).json()["job_id"]
    with db.get_session() as s:
        ids = [r.claim_id for r in s.execute(
            sa.select(db.atomic_claims.c.claim_id)
            .where(db.atomic_claims.c.candidate_id == cid)
            .order_by(db.atomic_claims.c.id)).all()]
    return cid, jid, ids


def test_a_repairable_numeral_draft_ships_repaired(client, monkeypatch):
    cid, jid, ids = _seed(client)
    monkeypatch.setattr(routes, "draft_bullets",
                        lambda *a, **k: [
                            Bullet("Cut deploy time by 40 percent at Acme Corp.", [ids[0]]),
                            Bullet("Ran Kubernetes at Globex, operating 40 services.", [ids[1]])])
    calls = []

    def fake_revise(gateway, model, offending, letter=False):
        calls.append(offending[0])
        return {ids[0]: "Cut deploy time 40% at Acme Corp by rebuilding the CI pipeline."}

    monkeypatch.setattr(routes, "revise_renderings", fake_revise)
    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid},
                    headers=H)
    assert r.status_code == 201, r.text
    body = r.json()
    # The repaired spelling shipped; the audit log names the round and the stage.
    assert any("40%" in b["text"] for b in body["bullets"])
    assert not any("40 percent" in b["text"] for b in body["bullets"])
    assert body["repair"][0]["stage"] == "numeral_precheck"
    # The revision was told the exact licensed spelling and the offending token.
    assert "40%" in calls[0]["allowed_tokens"]
    assert "'40'" in calls[0]["reasons"][0]
    # The repaired draft persisted, not the rejected one.
    prov = client.get(f"/api/v1/compile/{body['document_id']}", headers=H).json()
    assert any("40%" in b["text"] for b in prov["bullets"])


def test_unrepairable_draft_fails_with_the_gates_verdict_and_the_audit_log(client, monkeypatch):
    cid, jid, ids = _seed(client)
    monkeypatch.setattr(routes, "draft_bullets",
                        lambda *a, **k: [
                            Bullet("Cut deploy time by 40 percent at Acme Corp.", [ids[0]]),
                            Bullet("Operated 40 services at Globex.", [ids[1]])])
    monkeypatch.setattr(routes, "revise_renderings",
                        lambda gateway, model, offending, letter=False: {})
    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid},
                    headers=H)
    assert r.status_code == 422
    d = r.json()["detail"]
    # The verdict is the linker's, exactly as before the loop existed.
    assert d["error"] == "reference_integrity"
    assert d["violations"][0]["failure"] == "unsupported_number"
    assert "40" in d["violations"][0]["detail"]
    # The UX gets what it needs to be honest: the sentence and the fact reached for.
    assert "40 percent" in d["violations"][0]["text"]
    assert d["violations"][0]["cited"] == [FACTS[0]["statement"]]
    # The audit log shows the loop ran and stopped honestly.
    assert d["repair"][0]["stage"] == "numeral_precheck"
    assert d["repair"][1]["stage"] == "revision_unchanged"
    # Nothing persisted.
    with db.get_session() as s:
        n = s.execute(sa.select(sa.func.count())
                      .select_from(db.compiled_documents)).scalar()
    assert n == 0


def test_an_entailment_rejection_feeds_back_and_repairs(client, monkeypatch):
    cid, jid, ids = _seed(client)
    monkeypatch.setattr(routes, "draft_bullets",
                        lambda *a, **k: [
                            Bullet("Cut deploy time 40% at Acme Corp.", [ids[0]]),
                            Bullet("Directed all engineering at Globex.", [ids[1]])])
    # The scorer rejects the overreach and accepts the faithful restatement.
    monkeypatch.setattr(entailment, "_load",
                        lambda mid, rev: (lambda p, h: 0.03 if "Directed" in h else 0.95))
    seen = {}

    def fake_revise(gateway, model, offending, letter=False):
        seen["reasons"] = offending[0]["reasons"]
        return {ids[1]: "Ran Kubernetes in production at Globex, operating 40 services."}

    monkeypatch.setattr(routes, "revise_renderings", fake_revise)
    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid},
                    headers=H)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["repair"][0]["stage"] == "entailment"
    assert "claims more than" in seen["reasons"][0]
    assert all(b["entailment"] == 0.95 for b in body["bullets"])


def test_the_loop_is_bounded_at_three_rounds(client, monkeypatch):
    cid, jid, ids = _seed(client)
    monkeypatch.setattr(routes, "draft_bullets",
                        lambda *a, **k: [Bullet("Cut deploy time by 40 percent.", [ids[0]]),
                                         Bullet("Operated 40 services.", [ids[1]])])
    variants = iter(["Cut deploy time by forty percent, roughly 40.",
                     "Reduced deploys 40, give or take."])

    def always_bad(gateway, model, offending, letter=False):
        return {ids[0]: next(variants)}

    monkeypatch.setattr(routes, "revise_renderings", always_bad)
    r = client.post("/api/v1/compile", json={"candidate_id": cid, "job_id": jid},
                    headers=H)
    assert r.status_code == 422
    d = r.json()["detail"]
    rounds = [e["round"] for e in d["repair"] if e["stage"] == "numeral_precheck"]
    assert rounds == [1, 2, 3], "exactly three audited rounds, then the honest stop"
    assert d["error"] == "reference_integrity"


def test_letter_path_runs_the_same_loop(client, monkeypatch):
    cid, jid, ids = _seed(client)
    monkeypatch.setattr(routes, "draft_letter",
                        lambda *a, **k: [
                            Bullet("I cut deploy time by 40 percent at Acme Corp.", [ids[0]])])
    monkeypatch.setattr(routes, "revise_renderings",
                        lambda gateway, model, offending, letter=False:
                        {ids[0]: "I cut deploy time 40% at Acme Corp."})
    r = client.post("/api/v1/cover-letter", json={"candidate_id": cid, "job_id": jid},
                    headers=H)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["repair"][0]["stage"] == "numeral_precheck"
    assert any("40%" in s["text"] for s in body["sentences"])
