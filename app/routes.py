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

import io
import re

import sqlalchemy as sa
from docx import Document as DocxDocument
from fastapi import (APIRouter, File, Form, Header, HTTPException, Request, Response,
                     UploadFile)
from pypdf import PdfReader
from groundwork import BaseConfig, LLMGateway
from pydantic import BaseModel, Field

from groundwork import DemoRefused, ScopeDenied, guard_prefix

from . import db, demo
from .config import settings
from .engine import entailment, linker
from .engine.docx_out import letter_scaffold, render_docx, render_letter_docx
from .engine.embedding import HashingEmbedder, OpenRouterEmbedder
from .engine.entailment import EntailmentUnavailable
from .engine.facts import AtomicClaim, claims_from_entries, extract_facts
from .engine.fit import build_report
from .engine.interview import draft_questions, metrics_of, render_pack_docx
from .engine.jd import parse_jd, requirements_from_entries, Requirement
from .engine.linker import Bullet
from .engine.matcher import match
from .engine.renderer import draft_bullets, draft_letter
from .engine.selector import Omission, OmissionReason, select

router = APIRouter(prefix="/api/v1")


def _auth(authorization: str | None) -> str | None:
    """Full access for the estate token, a tenant prefix for a live demo token, 401 else.

    The demo changes who can hold a bearer, never whether one is required: with no token
    at all the answer stays 401, so the estate invariant (zero unauthenticated business
    reads) survives the demo unchanged.
    """
    token = settings.smoke_test_token
    raw = authorization or ""
    raw = raw[7:] if raw.startswith("Bearer ") else ""
    if token and raw == token:
        return None
    if raw:
        try:
            scope = demo.check_session(raw)
        except DemoRefused as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail)
        if scope:
            return scope
    if token:
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")
    return None


def _guard(s, scope: str | None, *, candidate_id=None, job_id=None) -> None:
    """Tenancy: a demo token touches only rows whose root identifier carries its prefix."""
    if scope is None:
        return
    try:
        if candidate_id is not None:
            row = s.execute(sa.select(db.candidates.c.name)
                            .where(db.candidates.c.id == candidate_id)).first()
            guard_prefix(scope, row.name if row else None)
        if job_id is not None:
            row = s.execute(sa.select(db.job_postings.c.title)
                            .where(db.job_postings.c.id == job_id)).first()
            guard_prefix(scope, row.title if row else None)
    except ScopeDenied as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


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
    scope = _auth(authorization)
    with db.get_session() as s, s.begin():
        cid = s.execute(db.candidates.insert().values(
            name=f"{scope or ''}{body.name}")).inserted_primary_key[0]
        if body.resume_text:
            s.execute(db.source_documents.insert().values(
                candidate_id=cid, name="resume.txt", text=body.resume_text))
    return {"candidate_id": cid}


@router.post("/candidates/{cid}/claims", status_code=201)
def add_claims(cid: int, body: ClaimsIn, authorization: str | None = Header(default=None)):
    scope = _auth(authorization)
    try:
        claims = claims_from_entries(body.entries)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    with db.get_session() as s, s.begin():
        if not s.execute(sa.select(db.candidates.c.id)
                         .where(db.candidates.c.id == cid)).first():
            raise HTTPException(status_code=404, detail="candidate not found")
        _guard(s, scope, candidate_id=cid)
        n = _store_claims(s, cid, claims)
    return {"stored": n, "provenance": "self_attested"}


@router.post("/candidates/{cid}/claims/extract", status_code=201)
def extract_claims(cid: int, authorization: str | None = Header(default=None)):
    scope = _auth(authorization)
    # Tenancy before the key gate: a 403 must not depend on whether a key is configured
    # Load inputs and close the session BEFORE the network call: a slow model must never
    # hold a DB connection or transaction open. Results are written in a second session.
    with db.get_session() as s:
        _guard(s, scope, candidate_id=cid)
        doc = s.execute(sa.select(db.source_documents)
                        .where(db.source_documents.c.candidate_id == cid)
                        .order_by(db.source_documents.c.id.desc())).first()
    if doc is None:
        raise HTTPException(status_code=422,
                            detail="candidate has no resume document to extract from")
    gateway = _gateway()
    claims = extract_facts(gateway, settings.llm_model_extraction, doc.text, doc.name)
    with db.get_session() as s, s.begin():
        n = _store_claims(s, cid, claims)
    # Rejections are the anchor check working, so they ship with their evidence: the
    # claim, and the quote the model offered that the source does not contain verbatim.
    rejected = [c for c in claims if c.core.verification.status == "rejected"]
    return {"stored": n, "rejected_span_anchor": len(rejected),
            "rejected": [{"claim_key": c.claim_key, "statement": c.core.statement,
                          "quote": c.failed_quote} for c in rejected],
            "provenance": "document_sourced"}


@router.post("/jobs", status_code=201)
def create_job(body: JobIn, authorization: str | None = Header(default=None)):
    scope = _auth(authorization)
    reqs: list[Requirement] = []
    if body.requirements:
        try:
            reqs = requirements_from_entries(body.requirements)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))
    with db.get_session() as s, s.begin():
        jid = s.execute(db.job_postings.insert().values(
            title=f"{scope or ''}{body.title}",
            description=body.description)).inserted_primary_key[0]
        for r in reqs:
            s.execute(db.requirements.insert().values(job_id=jid, **r.model_dump()))
    return {"job_id": jid, "requirements": len(reqs)}


@router.post("/jobs/{jid}/requirements/parse", status_code=201)
def parse_requirements(jid: int, authorization: str | None = Header(default=None)):
    scope = _auth(authorization)
    # Same discipline as extract_claims: read, close the session, call the LLM, then write.
    # Tenancy runs before the key gate.
    with db.get_session() as s:
        _guard(s, scope, job_id=jid)
        job = s.execute(sa.select(db.job_postings)
                        .where(db.job_postings.c.id == jid)).first()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if not job.description:
        raise HTTPException(status_code=422, detail="job has no description to parse")
    gateway = _gateway()
    reqs = parse_jd(gateway, settings.llm_model_extraction, job.description)
    with db.get_session() as s, s.begin():
        for r in reqs:
            s.execute(db.requirements.insert().values(job_id=jid, **r.model_dump()))
    return {"parsed": len(reqs)}


@router.post("/fit", status_code=201)
def run_fit(body: FitIn, authorization: str | None = Header(default=None)):
    scope = _auth(authorization)
    embedder = _embedder(body.embedder)
    with db.get_session() as s, s.begin():
        _guard(s, scope, candidate_id=body.candidate_id, job_id=body.job_id)
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
    scope = _auth(authorization)
    with db.get_session() as s:
        rep = s.execute(sa.select(db.fit_reports)
                        .where(db.fit_reports.c.id == rid)).mappings().first()
        if rep is None:
            raise HTTPException(status_code=404, detail="fit report not found")
        _guard(s, scope, candidate_id=rep["candidate_id"])
        rows = s.execute(sa.select(db.match_scores)
                         .where(db.match_scores.c.fit_report_id == rid)).mappings().all()
    return {"report": dict(rep), "rows": [dict(r) for r in rows]}


# --------------------------------------------------------------------------- Phase 2
class VerifyIn(BaseModel):
    status: str = Field(pattern="^(passed|rejected|pending)$")


class CompileIn(BaseModel):
    candidate_id: int
    job_id: int
    budget_lines: int = Field(default=0, ge=0)   # 0 -> settings.compile_budget_lines
    embedder: str = Field(default="hashing", pattern="^(hashing|openrouter)$")


class CheckIn(BaseModel):
    document_id: int
    text: str = Field(min_length=1)
    cites: list[str] = Field(default_factory=list)


@router.post("/facts/{claim_id}/verify")
def verify_fact(claim_id: str, body: VerifyIn,
                authorization: str | None = Header(default=None)):
    """Humans approve. This is the only way a claim's verification state changes after
    extraction — the model never does this."""
    scope = _auth(authorization)
    with db.get_session() as s, s.begin():
        row = s.execute(sa.select(db.atomic_claims.c.id, db.atomic_claims.c.candidate_id)
                        .where(db.atomic_claims.c.claim_id == claim_id)).first()
        if row is None:
            raise HTTPException(status_code=404, detail="fact not found")
        _guard(s, scope, candidate_id=row.candidate_id)
        s.execute(db.atomic_claims.update()
                  .where(db.atomic_claims.c.claim_id == claim_id)
                  .values(verification_status=body.status))
    return {"claim_id": claim_id, "verification_status": body.status}


def _load_reqs(s, job_id: int) -> list[Requirement]:
    req_rows = s.execute(sa.select(db.requirements)
                         .where(db.requirements.c.job_id == job_id)).mappings().all()
    return [Requirement.model_validate(
        {k: r[k] for k in ("req_key", "text", "kind", "must_have")}) for r in req_rows]


def _gate_detail(kind: str, violations: list[dict]) -> dict:
    """The typed shape every gate failure returns: what failed, and the evidence."""
    return {"error": kind, "violations": violations}


_TENANT_PREFIX = re.compile(r"^(?:demo|smoke)-\d{8}T\d{6}Z-[0-9a-f]+-")


def _display(name: str) -> str:
    """Tenant prefixes are scoping machinery, not names. They never belong in a
    document a user reads (observed live: a letter opening with
    'the demo-20260803T031221Z-bcd0dc-Platform Engineer role')."""
    return _TENANT_PREFIX.sub("", name)


@router.post("/compile", status_code=201)
def compile_resume(body: CompileIn, authorization: str | None = Header(default=None)):
    """select -> render -> link -> gate, failing on the first gate that objects.

    The selector chooses under the budget, the LLM phrases, the linker enforces reference
    integrity, the entailment gate rejects any sentence stronger than its cited evidence.
    Only a document that passed both gates is persisted: every stored row traced every
    sentence to a fact at the moment it was written.
    """
    scope = _auth(authorization)

    # Read everything, close the session, then call the model (same discipline as extract).
    # Tenancy runs before the key gate: 403 must not depend on key presence.
    with db.get_session() as s:
        _guard(s, scope, candidate_id=body.candidate_id, job_id=body.job_id)
        claims = _load_claims(s, body.candidate_id)
        if not claims:
            raise HTTPException(status_code=422, detail="candidate has no claims")
        job = s.execute(sa.select(db.job_postings)
                        .where(db.job_postings.c.id == body.job_id)).first()
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        reqs = _load_reqs(s, body.job_id)
        if not reqs:
            raise HTTPException(status_code=422, detail="job has no requirements")

    gateway = _gateway()
    rows = match(reqs, claims, _embedder(body.embedder))
    budget = body.budget_lines or settings.compile_budget_lines
    sel = select(claims, reqs, rows, budget)
    if not sel.selected:
        raise HTTPException(status_code=422, detail=_gate_detail(
            "empty_selection",
            [{"reason": o.reason.value, "claim_key": o.claim_key, "detail": o.detail}
             for o in sel.omitted]))

    chosen = [c for c in claims if c.core.claim_id in set(sel.selected)]
    bullets = draft_bullets(gateway, settings.llm_model_reasoning, chosen, job.title, reqs)
    if not bullets:
        raise HTTPException(status_code=502,
                            detail="the renderer returned no bullets to gate")

    link = linker.check(bullets, claims, selected_ids=sel.selected)
    if not link.ok:
        raise HTTPException(status_code=422, detail=_gate_detail(
            "reference_integrity",
            [{"bullet": v.bullet_index, "text": v.text, "failure": v.failure.value,
              "detail": v.detail} for v in link.violations]))

    try:
        rep = entailment.gate(bullets, claims, settings.nli_entail_threshold,
                              settings.nli_model, settings.nli_model_revision)
    except EntailmentUnavailable as e:
        # D5: fails loud or not at all. Never a weaker check, never a pass.
        raise HTTPException(status_code=503,
                            detail={"error": "entailment_unavailable", "message": str(e)})
    if not rep.ok:
        raise HTTPException(status_code=422, detail=_gate_detail(
            "entailment",
            [{"bullet": v.bullet_index, "text": v.text, "entailment": v.entailment,
              "threshold": v.threshold, "premise": v.premise, "detail": v.detail}
             for v in rep.violations]))

    scores = dict(rep.scored)
    with db.get_session() as s, s.begin():
        did = s.execute(db.compiled_documents.insert().values(
            candidate_id=body.candidate_id, job_id=body.job_id, kind="resume",
            budget_lines=sel.budget_lines, used_lines=sel.used_lines,
            nli_model=settings.nli_model, nli_revision=settings.nli_model_revision,
            nli_threshold=settings.nli_entail_threshold)).inserted_primary_key[0]
        for i, b in enumerate(bullets):
            s.execute(db.rendered_bullets.insert().values(
                document_id=did, position=i, text=b.text, cites=b.cites,
                entailment=scores.get(i)))
        for o in sel.omitted:
            s.execute(db.selection_omissions.insert().values(
                document_id=did, claim_id=o.claim_id, claim_key=o.claim_key,
                reason=o.reason.value, detail=o.detail))

    return {"document_id": did,
            "bullets": [{"position": i, "text": b.text, "cites": b.cites,
                         "entailment": scores.get(i)} for i, b in enumerate(bullets)],
            "omitted": [{"claim_key": o.claim_key, "reason": o.reason.value,
                         "detail": o.detail} for o in sel.omitted],
            "covered_must": sel.covered_must, "uncovered_must": sel.uncovered_must,
            "used_lines": sel.used_lines, "budget_lines": sel.budget_lines,
            "gate": {"model": settings.nli_model,
                     "revision": settings.nli_model_revision,
                     "threshold": settings.nli_entail_threshold}}


class CoverLetterIn(BaseModel):
    candidate_id: int
    job_id: int
    budget_lines: int = Field(default=6, ge=1, le=12)
    embedder: str = Field(default="hashing", pattern="^(hashing|openrouter)$")


@router.post("/cover-letter", status_code=201)
def compile_cover_letter(body: CoverLetterIn,
                         authorization: str | None = Header(default=None)):
    """The cover letter: same pipeline, same gates, letter voice.

    A letter is where fabrication is most tempting and least checked, so it gets exactly
    the resume's checks: selector chooses the evidence, the model restates it in first
    person, the linker enforces reference integrity, the entailment gate rejects any
    sentence stronger than its cited facts. The job-referential frame (greeting, role
    line, closing) is deterministic template text — it references the role and says
    nothing about the candidate, so nothing in it needs a gate or could use one."""
    scope = _auth(authorization)
    with db.get_session() as s:
        _guard(s, scope, candidate_id=body.candidate_id, job_id=body.job_id)
        claims = _load_claims(s, body.candidate_id)
        if not claims:
            raise HTTPException(status_code=422, detail="candidate has no claims")
        job = s.execute(sa.select(db.job_postings)
                        .where(db.job_postings.c.id == body.job_id)).first()
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        reqs = _load_reqs(s, body.job_id)
        if not reqs:
            raise HTTPException(status_code=422, detail="job has no requirements")
        cand = s.execute(sa.select(db.candidates.c.name)
                         .where(db.candidates.c.id == body.candidate_id)).first()

    gateway = _gateway()
    rows = match(reqs, claims, _embedder(body.embedder))
    sel = select(claims, reqs, rows, body.budget_lines)
    if not sel.selected:
        raise HTTPException(status_code=422, detail=_gate_detail(
            "empty_selection",
            [{"reason": o.reason.value, "claim_key": o.claim_key, "detail": o.detail}
             for o in sel.omitted]))

    chosen = [c for c in claims if c.core.claim_id in set(sel.selected)]
    sentences = draft_letter(gateway, settings.llm_model_reasoning, chosen,
                             job.title, reqs)
    if not sentences:
        raise HTTPException(status_code=502,
                            detail="the renderer returned no sentences to gate")

    link = linker.check(sentences, claims, selected_ids=sel.selected)
    if not link.ok:
        raise HTTPException(status_code=422, detail=_gate_detail(
            "reference_integrity",
            [{"bullet": v.bullet_index, "text": v.text, "failure": v.failure.value,
              "detail": v.detail} for v in link.violations]))

    try:
        rep = entailment.gate(sentences, claims, settings.nli_entail_threshold,
                              settings.nli_model, settings.nli_model_revision)
    except EntailmentUnavailable as e:
        raise HTTPException(status_code=503,
                            detail={"error": "entailment_unavailable", "message": str(e)})
    if not rep.ok:
        raise HTTPException(status_code=422, detail=_gate_detail(
            "entailment",
            [{"bullet": v.bullet_index, "text": v.text, "entailment": v.entailment,
              "threshold": v.threshold, "premise": v.premise, "detail": v.detail}
             for v in rep.violations]))

    scores = dict(rep.scored)
    with db.get_session() as s, s.begin():
        did = s.execute(db.compiled_documents.insert().values(
            candidate_id=body.candidate_id, job_id=body.job_id, kind="cover_letter",
            budget_lines=sel.budget_lines, used_lines=sel.used_lines,
            nli_model=settings.nli_model, nli_revision=settings.nli_model_revision,
            nli_threshold=settings.nli_entail_threshold)).inserted_primary_key[0]
        for i, b in enumerate(sentences):
            s.execute(db.rendered_bullets.insert().values(
                document_id=did, position=i, text=b.text, cites=b.cites,
                entailment=scores.get(i)))
        for o in sel.omitted:
            s.execute(db.selection_omissions.insert().values(
                document_id=did, claim_id=o.claim_id, claim_key=o.claim_key,
                reason=o.reason.value, detail=o.detail))

    frame = letter_scaffold(_display(cand.name) if cand else "unknown",
                            _display(job.title))
    return {"document_id": did, "kind": "cover_letter", **frame,
            "sentences": [{"position": i, "text": b.text, "cites": b.cites,
                           "entailment": scores.get(i)} for i, b in enumerate(sentences)],
            "omitted": [{"claim_key": o.claim_key, "reason": o.reason.value,
                         "detail": o.detail} for o in sel.omitted],
            "gate": {"model": settings.nli_model,
                     "revision": settings.nli_model_revision,
                     "threshold": settings.nli_entail_threshold}}


def _load_document(s, did: int):
    doc = s.execute(sa.select(db.compiled_documents)
                    .where(db.compiled_documents.c.id == did)).mappings().first()
    if doc is None:
        raise HTTPException(status_code=404, detail="compiled document not found")
    bullets = s.execute(sa.select(db.rendered_bullets)
                        .where(db.rendered_bullets.c.document_id == did)
                        .order_by(db.rendered_bullets.c.position)).mappings().all()
    omissions = s.execute(sa.select(db.selection_omissions)
                          .where(db.selection_omissions.c.document_id == did)).mappings().all()
    return doc, bullets, omissions


@router.get("/compile/{did}")
def get_compiled(did: int, authorization: str | None = Header(default=None)):
    """The provenance map: every bullet with its cited facts resolved to statements, and
    every omission with its typed reason."""
    scope = _auth(authorization)
    with db.get_session() as s:
        doc, bullets, omissions = _load_document(s, did)
        _guard(s, scope, candidate_id=doc["candidate_id"])
        claims = {c.core.claim_id: c for c in _load_claims(s, doc["candidate_id"])}
    return {"document": dict(doc),
            "bullets": [{**dict(b), "facts": [
                {"claim_id": cid,
                 "claim_key": claims[cid].claim_key if cid in claims else None,
                 "statement": claims[cid].core.statement if cid in claims else None,
                 "provenance": claims[cid].provenance.value if cid in claims else None}
                for cid in b["cites"]]} for b in bullets],
            "omitted": [dict(o) for o in omissions]}


@router.get("/compile/{did}/docx")
def get_compiled_docx(did: int, authorization: str | None = Header(default=None)):
    scope = _auth(authorization)
    with db.get_session() as s:
        doc, bullets, omissions = _load_document(s, did)
        _guard(s, scope, candidate_id=doc["candidate_id"])
        claims = {c.core.claim_id: c for c in _load_claims(s, doc["candidate_id"])}
        cand = s.execute(sa.select(db.candidates.c.name)
                         .where(db.candidates.c.id == doc["candidate_id"])).first()
        job = s.execute(sa.select(db.job_postings.c.title)
                        .where(db.job_postings.c.id == doc["job_id"])).first()
    note = (f"NLI {doc['nli_model']}@{doc['nli_revision'][:12]}, "
            f"threshold {doc['nli_threshold']}")
    if doc.get("kind") == "cover_letter":
        payload = render_letter_docx(
            candidate_name=_display(cand.name) if cand else "unknown",
            job_title=_display(job.title) if job else "unknown",
            sentences=[dict(b) for b in bullets],
            claims_by_id=claims,
            entailment_note=note)
        stem = "careercompiler-letter"
    else:
        payload = render_docx(
            candidate_name=_display(cand.name) if cand else "unknown",
            job_title=_display(job.title) if job else "unknown",
            bullets=[dict(b) for b in bullets],
            claims_by_id=claims,
            omissions=[Omission(o["claim_id"], o["claim_key"],
                                OmissionReason(o["reason"]), o["detail"])
                       for o in omissions],
            entailment_note=note)
        stem = "careercompiler"
    return Response(
        content=payload,
        media_type=("application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"),
        headers={"Content-Disposition":
                 f'attachment; filename="{stem}-{did}.docx"'})


@router.post("/compile/check")
def check_bullet(body: CheckIn, authorization: str | None = Header(default=None)):
    """The rejection moment, live. Runs both gates on one edited sentence against its cited
    facts and returns the verdict with evidence. Persists nothing, always 200: the outcome
    of a check is a result, not an error."""
    scope = _auth(authorization)
    with db.get_session() as s:
        doc, _, _ = _load_document(s, body.document_id)
        _guard(s, scope, candidate_id=doc["candidate_id"])
        claims = _load_claims(s, doc["candidate_id"])

    bullet = Bullet(text=body.text, cites=body.cites)
    link = linker.check([bullet], claims, selected_ids=None)
    link_violations = [{"failure": v.failure.value, "detail": v.detail}
                      for v in link.violations]

    entail: dict = {"checked": False}
    if link.ok:
        try:
            rep = entailment.gate([bullet], claims, settings.nli_entail_threshold,
                                  settings.nli_model, settings.nli_model_revision)
        except EntailmentUnavailable as e:
            raise HTTPException(status_code=503,
                                detail={"error": "entailment_unavailable",
                                        "message": str(e)})
        entail = {"checked": True, "ok": rep.ok,
                  "score": rep.scored[0][1] if rep.scored else None,
                  "threshold": settings.nli_entail_threshold,
                  "violations": [{"detail": v.detail, "premise": v.premise}
                                 for v in rep.violations]}

    return {"ok": link.ok and bool(entail.get("ok", False)),
            "reference_integrity": {"ok": link.ok, "violations": link_violations},
            "entailment": entail}


class InterviewPackIn(BaseModel):
    document_id: int
    format: str = Field(default="json", pattern="^(json|docx)$")


@router.post("/interview-pack", status_code=201)
def build_interview_pack(body: InterviewPackIn,
                         authorization: str | None = Header(default=None)):
    """The interview pack, from gate-survivors only.

    Everything that asserts is deterministic: the story is the cited fact statements
    verbatim with provenance, the metrics are the numbers those statements carry, the
    gaps and the case against come from the stored fit report. The model's only
    authority is interrogative — the skeptical questions — and every question ships
    beside the facts that bound its honest answer. Stateless: nothing persists, and a
    docx request regenerates the questions."""
    scope = _auth(authorization)
    with db.get_session() as s:
        doc, bullets, _ = _load_document(s, body.document_id)
        _guard(s, scope, candidate_id=doc["candidate_id"])
        claims = {c.core.claim_id: c for c in _load_claims(s, doc["candidate_id"])}
        cand = s.execute(sa.select(db.candidates.c.name)
                         .where(db.candidates.c.id == doc["candidate_id"])).first()
        job = s.execute(sa.select(db.job_postings.c.title)
                        .where(db.job_postings.c.id == doc["job_id"])).first()
        rep = s.execute(sa.select(db.fit_reports)
                        .where(db.fit_reports.c.candidate_id == doc["candidate_id"],
                               db.fit_reports.c.job_id == doc["job_id"])
                        .order_by(db.fit_reports.c.id.desc())).mappings().first()
        gap_rows = []
        if rep is not None:
            gap_rows = s.execute(
                sa.select(db.match_scores)
                .where(db.match_scores.c.fit_report_id == rep["id"],
                       db.match_scores.c.status != "matched")).mappings().all()

    job_title = _display(job.title) if job else "unknown"
    b_items, entries = [], []
    for b in bullets:
        facts = [claims[cid] for cid in b["cites"] if cid in claims]
        statements = [f.core.statement for f in facts]
        b_items.append({"id": f"B{b['position'] + 1}", "text": b["text"],
                        "facts": statements})
        entries.append({
            "id": f"B{b['position'] + 1}", "text": b["text"],
            "facts": [{"key": f.claim_key, "statement": f.core.statement,
                       "provenance": f.provenance.value} for f in facts],
            "metrics": metrics_of(statements)})
    g_items, gap_entries = [], []
    for i, g in enumerate(gap_rows):
        case = g["explanation"] or "no evidence in the fact graph"
        g_items.append({"id": f"G{i + 1}", "requirement": g["req_key"], "case": case})
        gap_entries.append({"id": f"G{i + 1}", "requirement": g["req_key"],
                            "case": case, "status": g["status"],
                            "must_have": g["must_have"]})

    gateway = _gateway()
    questions = draft_questions(gateway, settings.llm_model_reasoning, job_title,
                                b_items, g_items)
    for e in entries:
        e["questions"] = questions.get(e.pop("id"), [])
    for g in gap_entries:
        g["questions"] = questions.get(g.pop("id"), [])

    note = ("Built only from facts that survived the compile gates. Questions are "
            "generated; the facts beside them are the boundary every honest answer "
            "must respect. Nothing here licenses a claim the resume could not support.")
    verdict = rep["verdict"] if rep is not None else "unknown"
    case_against = rep["case_against"] if rep is not None else None

    if body.format == "docx":
        payload = render_pack_docx(
            candidate_name=_display(cand.name) if cand else "unknown",
            job_title=job_title,
            verdict=verdict, case_against=case_against, entries=entries,
            gap_entries=gap_entries, note=note)
        return Response(
            content=payload, status_code=201,
            media_type=("application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document"),
            headers={"Content-Disposition":
                     f'attachment; filename="careercompiler-prep-{body.document_id}.docx"'})

    return {"document_id": body.document_id, "job_title": job_title,
            "verdict": verdict, "case_against": case_against,
            "note": note, "bullets": entries, "gaps": gap_entries}


# --------------------------------------------------------------------------- demo (Part B)
@router.post("/demo/session", status_code=201)
def open_demo_session(request: Request):
    """Public by design: this endpoint ISSUES credentials, it does not bypass them.

    Rate-limited per source address, and the token it returns is scoped (tenant prefix),
    budgeted (request counter), and short-lived (Redis TTL). Seeding is entry-path only,
    so a session opens without an LLM call and costs nothing per visitor.
    """
    forwarded = request.headers.get("x-forwarded-for") or ""
    ip = (forwarded.split(",")[0].strip()
          or (request.client.host if request.client else "unknown"))
    try:
        token, prefix = demo.create_session(ip)
    except DemoRefused as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    with db.get_session() as s, s.begin():
        seeded = demo.seed_tenant(s, prefix, _store_claims)
    return {"token": token, "token_type": "bearer",
            "expires_in": settings.demo_session_ttl_seconds,
            "request_budget": settings.demo_request_budget,
            "synthetic": True, **seeded}


def _normalize_doc_text(text: str) -> str:
    """Layout artifacts out of the stored text, before it becomes the anchoring source.

    Measured root cause (candidate 31 in production, 35 of 138 rejected): PDF extraction
    hard-wraps lines mid-sentence ("AI-native\\nsystems in production") and doubles spaces
    at layout gaps, while the model quotes the sentence with normal spacing — so a
    faithful quote fails a verbatim find. The defect is extraction leaking layout into
    text. The fix normalizes what we STORE: spaces collapsed within lines, single line
    breaks (layout wraps) joined with a space, blank-line paragraph boundaries kept.
    The anchor check itself stays byte-verbatim against this stored text — the gate is
    not loosened, the source is made faithful to the document's sentences."""
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.replace("\r", "").split("\n")]
    paras: list[str] = []
    cur: list[str] = []
    for ln in lines:
        if ln:
            cur.append(ln)
        elif cur:
            paras.append(" ".join(cur))
            cur = []
    if cur:
        paras.append(" ".join(cur))
    return "\n".join(paras)


@router.post("/candidates/upload", status_code=201)
async def upload_candidate(name: str = Form(...), file: UploadFile = File(...),
                           authorization: str | None = Header(default=None)):
    """Resume upload, PDF or docx (E5). Text is extracted server-side, normalized of
    layout artifacts, and stored as the source document; span anchoring during claim
    extraction then works against exactly this text, and a quote that fails to anchor
    is stored rejected and never matches."""
    scope = _auth(authorization)
    data = await file.read()
    if len(data) > 2_000_000:
        raise HTTPException(status_code=413, detail="file exceeds the 2 MB upload limit")
    fn = (file.filename or "").lower()
    try:
        if fn.endswith(".pdf"):
            text = "\n".join((p.extract_text() or "")
                             for p in PdfReader(io.BytesIO(data)).pages)
        elif fn.endswith(".docx"):
            text = "\n".join(p.text for p in DocxDocument(io.BytesIO(data)).paragraphs)
        else:
            raise HTTPException(status_code=415,
                                detail="PDF or docx only; paste-in text is not accepted")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422,
                            detail="the file could not be parsed as PDF or docx")
    text = _normalize_doc_text(text)
    if not text.strip():
        raise HTTPException(status_code=422,
                            detail="no extractable text in the document; a scanned image "
                                   "needs OCR, which this demo does not run")
    with db.get_session() as s, s.begin():
        cid = s.execute(db.candidates.insert().values(
            name=f"{scope or ''}{name}")).inserted_primary_key[0]
        s.execute(db.source_documents.insert().values(
            candidate_id=cid, name=fn, text=text))
    return {"candidate_id": cid, "chars": len(text)}
