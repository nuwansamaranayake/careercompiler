"""Demo access for CareerCompiler, on the shared kit (groundwork.demokit).

Session issuance, tenant prefixes, budgets, TTLs, and the tenancy guard live in groundwork
now — extracted from this app after v0.3.1 shipped, so the next products inherit them.
What stays here is the product-specific seed: the synthetic fact graph and the two jobs
whose verdicts are deterministic (a clear fit, and a planted TS/SCI must-have producing the
honest do-not-apply).
"""
from __future__ import annotations

import redis as redis_lib
from groundwork import DemoKit

from . import db
from .config import settings
from .engine.embedding import HashingEmbedder
from .engine.facts import claims_from_entries
from .engine.fit import build_report
from .engine.jd import requirements_from_entries
from .engine.matcher import match

_client = None
_kit: DemoKit | None = None


def get_redis():
    global _client
    if _client is None:
        _client = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def set_redis_for_tests(client) -> None:
    global _client, _kit
    _client = client
    _kit = None


def kit() -> DemoKit:
    global _kit
    if _kit is None:
        _kit = DemoKit(get_redis(),
                       ttl_seconds=settings.demo_session_ttl_seconds,
                       request_budget=settings.demo_request_budget,
                       sessions_per_ip_hour=settings.demo_sessions_per_ip_hour)
    return _kit


def create_session(client_ip: str) -> tuple[str, str]:
    return kit().create_session(client_ip)


def check_session(token: str) -> str | None:
    return kit().check_session(token)


# --------------------------------------------------------------------------- seed (B3)
# Synthetic on purpose and labelled as such in the UI. The graph is designed so the two
# verdicts are deterministic under the hashing embedder: every requirement of the first
# job has direct evidence; the second job plants one must-have nothing in the graph can
# satisfy, so its report carries a disqualifying gap and the honest do-not-apply.
SEED_NAME = "Jordan Alvarez"

SEED_CLAIMS = [
    {"claim_key": "python_services", "kind": "skill",
     "statement": "Built and operated Python services in production for 6 years at Acme Corp."},
    {"claim_key": "kubernetes_production", "kind": "skill",
     "statement": "Ran Kubernetes in production at Globex, operating 40 services."},
    {"claim_key": "team_leadership", "kind": "role",
     "statement": "Led a team of 4 engineers at Acme Corp from 2019 to 2022."},
    {"claim_key": "postgres_scale", "kind": "scope",
     "statement": "Migrated a 12M row Postgres table at Acme Corp with zero downtime."},
    {"claim_key": "ci_pipeline", "kind": "outcome",
     "statement": "Cut deploy time 40% at Acme Corp by rebuilding the CI pipeline."},
]

SEED_JOB_FIT = {
    "title": "Platform Engineer",
    "requirements": [
        {"req_key": "python_services", "text": "Python services in production",
         "kind": "skill", "must_have": True},
        {"req_key": "kubernetes_production", "text": "Kubernetes in production",
         "kind": "skill", "must_have": True},
        {"req_key": "postgres_scale", "text": "Postgres at scale",
         "kind": "experience", "must_have": False},
        {"req_key": "team_leadership", "text": "Team leadership",
         "kind": "experience", "must_have": False},
    ],
}

SEED_JOB_GAP = {
    "title": "Site Reliability Lead, Defense Systems",
    "requirements": [
        {"req_key": "kubernetes_production", "text": "Kubernetes in production",
         "kind": "skill", "must_have": True},
        {"req_key": "team_leadership", "text": "Team leadership",
         "kind": "experience", "must_have": True},
        # The planted disqualifier: nothing in the seed graph evidences it, and no amount
        # of phrasing should. The honest product says do-not-apply, visibly.
        {"req_key": "active_ts_sci_clearance", "text": "Active TS/SCI security clearance",
         "kind": "other", "must_have": True},
    ],
}


def seed_tenant(s, prefix: str, store_claims) -> dict:
    """Create the tenant's fact graph, two jobs, and both fit reports, deterministically.

    Entry paths only — no LLM call, so a session opens in milliseconds and seeding costs
    nothing per visitor. `store_claims` is routes._store_claims, passed in to keep the
    dependency one-directional.
    """
    claims = claims_from_entries(SEED_CLAIMS)
    cid = s.execute(db.candidates.insert().values(
        name=f"{prefix}{SEED_NAME}")).inserted_primary_key[0]
    store_claims(s, cid, claims)

    embedder = HashingEmbedder()
    out = []
    for job in (SEED_JOB_FIT, SEED_JOB_GAP):
        reqs = requirements_from_entries(job["requirements"])
        jid = s.execute(db.job_postings.insert().values(
            title=f"{prefix}{job['title']}",
            description=None)).inserted_primary_key[0]
        for rq in reqs:
            s.execute(db.requirements.insert().values(job_id=jid, **rq.model_dump()))
        rows = match(reqs, claims, embedder)
        report = build_report(rows)
        rid = s.execute(db.fit_reports.insert().values(
            candidate_id=cid, job_id=jid, verdict=report.verdict,
            matched=report.matched, partial=report.partial, gaps=report.gaps,
            disqualifying=report.disqualifying_gaps, case_against=report.case_against,
            embedder=embedder.name)).inserted_primary_key[0]
        for r in rows:
            s.execute(db.match_scores.insert().values(
                fit_report_id=rid, req_key=r.req_key, must_have=r.must_have,
                status=r.status, direct=r.direct, evidence=r.evidence_claim_ids,
                score=r.score, explanation=r.explanation))
        out.append({"job_id": jid, "fit_report_id": rid, "title": job["title"],
                    "verdict": report.verdict})
    return {"candidate_id": cid, "candidate_name": SEED_NAME, "jobs": out}
