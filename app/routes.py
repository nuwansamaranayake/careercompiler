"""Business endpoints: the fact-graph -> requirements -> fit loop, persisted.

POST /api/v1/candidates                       create candidate (+resume document)
POST /api/v1/candidates/{id}/claims           data-entry claims (keyless, self-attested)
POST /api/v1/candidates/{id}/claims/extract   LLM extraction from the stored resume (key-gated)
POST /api/v1/jobs                             create job (+entry-path requirements)
POST /api/v1/jobs/{id}/requirements/parse     LLM JD parse (key-gated)
POST /api/v1/fit                              deterministic match + Fit Report, persisted
GET  /api/v1/fit/{id}                         stored report with rows

The keyless entry paths are real product features (self-attested facts, hand-typed
requirements). The LLM paths refuse loudly without a key — no silent fallback between the
two (Standard 3). Bearer auth on mutations and fit-report reads when SMOKE_TEST_TOKEN is set.
"""
from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Header, HTTPException
from groundwork import BaseConfig, LLMGateway
from pydantic import BaseModel, Field

from . import db
from .config import settings
from .engine.embedding import HashingEmbedder, OpenRouterEmbedder
from .engine.facts import AtomicClaim, claims_from_entries, extract_facts
from .engine.fit import build_report
from .engine.jd import parse_jd, requirements_from_entries, Requirement
from .engine.matcher import match

router = APIRouter(prefix="/api/v1")


def _auth(authorization: str | None) -> None:
    token = settings.smoke_test_token
    if token and authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")


def _gateway() -> LLMGateway:
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=503,
            detail="LLM extraction requires OPENROUTER_API_KEY; use the data-entry "
                   "endpoint for the keyless path",
        )
    gw = LLMGateway(BaseConfig(
        openrouter_api_key=settings.openrouter_api_key,
        openrouter_base_url=settings.openrouter_base_url,
    ))
    # Bound the client so a slow model cannot pin the connection pool. Clamped here (not
    # only via groundwork config) so the app's LLM_TIMEOUT_SECONDS applies regardless of
    # the groundwork version in use — the pinned v0.1.0 gateway has no timeout knob and
    # ships the OpenAI SDK defaults (600s, 2 retries).
    gw._client = gw._client.with_options(
        timeout=settings.llm_timeout_seconds, max_retries=settings.llm_max_retries)
    return gw


def _embedder(name: str):
    if name == "openrouter":
        if not settings.openrouter_api_key or not settings.embedding_model:
            raise HTTPException(
                status_code=503,
                detail="embedder 'openrouter' requires OPENROUTER_API_KEY and "
                       "EMBEDDING_MODEL; use embedder 'hashing' for the keyless path",
            )
        return OpenRouterEmbedder(
            api_key=settings.openrouter_api_key,
            model=settings.embedding_model,
            base_url=settings.openrouter_base_url,
        )
    return HashingEmbedder()


def _store_claims(s, candidate_id: int, claims: list[AtomicClaim]) -> int:
    for c in claims:
        span = c.core.evidence_ref.span
        s.execute(db.atomic_claims.insert().values(
            candidate_id=candidate_id, claim_id=c.core.claim_id, claim_key=c.claim_key,
            kind=c.kind.value, statement=c.core.statement,
            source=c.core.evidence_ref.source,
            span_start=span[0] if span else None, span_end=span[1] if span else None,
            provenance=c.provenance.value, confidence=c.core.confidence or 0.0,
            verification_status=c.core.verification.status,
            gates=c.core.verification.gates))
    return len(claims)


def _load_claims(s, candidate_id: int) -> list[AtomicClaim]:
    rows = s.execute(sa.select(db.atomic_claims)
                     .where(db.atomic_claims.c.candidate_id == candidate_id)).mappings().all()
    out = []
    for r in rows:
        entry = {"claim_key": r["claim_key"], "kind": r["kind"], "statement": r["statement"]}
        [c] = claims_from_entries([entry], source_name=r["source"])
        c.core.verification.status = r["verification_status"]
        out.append(c)
    return out


class CandidateIn(BaseModel):
    name: str = Field(min_length=1)
    resume_text: str | None = None


class ClaimsIn(BaseModel):
    entries: list[dict] = Field(min_length=1)


class JobIn(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    requirements: list[dict] | None = None


class FitIn(BaseModel):
    candidate_id: int
    job_id: int
    embedder: str = Field(default="hashing", pattern="^(hashing|openrouter)$")


@router.post("/candidates", status_code=201)
def create_candidate(body: CandidateIn, authorization: str | None = Header(default=None)):
    _auth(authorization)
    with db.get_session() as s, s.begin():
        cid = s.execute(db.candidates.insert().values(name=body.name)).inserted_primary_key[0]
        if body.resume_text:
            s.execute(db.source_documents.insert().values(
                candidate_id=cid, name="resume.txt", text=body.resume_text))
    return {"candidate_id": cid}


@router.post("/candidates/{cid}/claims", status_code=201)
def add_claims(cid: int, body: ClaimsIn, authorization: str | None = Header(default=None)):
    _auth(authorization)
    try:
        claims = claims_from_entries(body.entries)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    with db.get_session() as s, s.begin():
        if not s.execute(sa.select(db.candidates.c.id)
                         .where(db.candidates.c.id == cid)).first():
            raise HTTPException(status_code=404, detail="candidate not found")
        n = _store_claims(s, cid, claims)
    return {"stored": n, "provenance": "self_attested"}


@router.post("/candidates/{cid}/claims/extract", status_code=201)
def extract_claims(cid: int, authorization: str | None = Header(default=None)):
    _auth(authorization)
    gateway = _gateway()
    # Load inputs and close the session BEFORE the network call: a slow model must never
    # hold a DB connection or transaction open. Results are written in a second session.
    with db.get_session() as s:
        doc = s.execute(sa.select(db.source_documents)
                        .where(db.source_documents.c.candidate_id == cid)
                        .order_by(db.source_documents.c.id.desc())).first()
    if doc is None:
        raise HTTPException(status_code=422,
                            detail="candidate has no resume document to extract from")
    claims = extract_facts(gateway, settings.llm_model_extraction, doc.text, doc.name)
    with db.get_session() as s, s.begin():
        n = _store_claims(s, cid, claims)
    rejected = sum(1 for c in claims if c.core.verification.status == "rejected")
    return {"stored": n, "rejected_span_anchor": rejected, "provenance": "document_sourced"}


@router.post("/jobs", status_code=201)
def create_job(body: JobIn, authorization: str | None = Header(default=None)):
    _auth(authorization)
    reqs: list[Requirement] = []
    if body.requirements:
        try:
            reqs = requirements_from_entries(body.requirements)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))
    with db.get_session() as s, s.begin():
        jid = s.execute(db.job_postings.insert().values(
            title=body.title, description=body.description)).inserted_primary_key[0]
        for r in reqs:
            s.execute(db.requirements.insert().values(job_id=jid, **r.model_dump()))
    return {"job_id": jid, "requirements": len(reqs)}


@router.post("/jobs/{jid}/requirements/parse", status_code=201)
def parse_requirements(jid: int, authorization: str | None = Header(default=None)):
    _auth(authorization)
    gateway = _gateway()
    # Same discipline as extract_claims: read, close the session, call the LLM, then write.
    with db.get_session() as s:
        job = s.execute(sa.select(db.job_postings)
                        .where(db.job_postings.c.id == jid)).first()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if not job.description:
        raise HTTPException(status_code=422, detail="job has no description to parse")
    reqs = parse_jd(gateway, settings.llm_model_extraction, job.description)
    with db.get_session() as s, s.begin():
        for r in reqs:
            s.execute(db.requirements.insert().values(job_id=jid, **r.model_dump()))
    return {"parsed": len(reqs)}


@router.post("/fit", status_code=201)
def run_fit(body: FitIn, authorization: str | None = Header(default=None)):
    _auth(authorization)
    embedder = _embedder(body.embedder)
    with db.get_session() as s, s.begin():
        claims = _load_claims(s, body.candidate_id)
        if not claims:
            raise HTTPException(status_code=422, detail="candidate has no claims")
        req_rows = s.execute(sa.select(db.requirements)
                             .where(db.requirements.c.job_id == body.job_id)).mappings().all()
        if not req_rows:
            raise HTTPException(status_code=422, detail="job has no requirements")
        reqs = [Requirement.model_validate(
            {k: r[k] for k in ("req_key", "text", "kind", "must_have")}) for r in req_rows]
        rows = match(reqs, claims, embedder)
        report = build_report(rows)
        rid = s.execute(db.fit_reports.insert().values(
            candidate_id=body.candidate_id, job_id=body.job_id, verdict=report.verdict,
            matched=report.matched, partial=report.partial, gaps=report.gaps,
            disqualifying=report.disqualifying_gaps, case_against=report.case_against,
            embedder=embedder.name)).inserted_primary_key[0]
        for r in rows:
            s.execute(db.match_scores.insert().values(
                fit_report_id=rid, req_key=r.req_key, must_have=r.must_have,
                status=r.status, direct=r.direct, evidence=r.evidence_claim_ids,
                score=r.score, explanation=r.explanation))
    return {"fit_report_id": rid, "verdict": report.verdict, "matched": report.matched,
            "partial": report.partial, "gaps": report.gaps,
            "disqualifying_gaps": report.disqualifying_gaps}


@router.get("/fit/{rid}")
def get_fit(rid: int, authorization: str | None = Header(default=None)):
    _auth(authorization)
    with db.get_session() as s:
        rep = s.execute(sa.select(db.fit_reports)
                        .where(db.fit_reports.c.id == rid)).mappings().first()
        if rep is None:
            raise HTTPException(status_code=404, detail="fit report not found")
        rows = s.execute(sa.select(db.match_scores)
                         .where(db.match_scores.c.fit_report_id == rid)).mappings().all()
    return {"report": dict(rep), "rows": [dict(r) for r in rows]}
