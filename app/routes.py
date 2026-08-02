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
from fastapi import APIRouter, Header, HTTPException, Response
from groundwork import BaseConfig, LLMGateway
from pydantic import BaseModel, Field

from . import db
from .config import settings
from .engine import entailment, linker
from .engine.docx_out import render_docx
from .engine.embedding import HashingEmbedder, OpenRouterEmbedder
from .engine.entailment import EntailmentUnavailable
from .engine.facts import AtomicClaim, claims_from_entries, extract_facts
from .engine.fit import build_report
from .engine.jd import parse_jd, requirements_from_entries, Requirement
from .engine.linker import Bullet
from .engine.matcher import match
from .engine.renderer import draft_bullets
from .engine.selector import Omission, OmissionReason, select

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
    _auth(authorization)
    with db.get_session() as s, s.begin():
        row = s.execute(sa.select(db.atomic_claims.c.id)
                        .where(db.atomic_claims.c.claim_id == claim_id)).first()
        if row is None:
            raise HTTPException(status_code=404, detail="fact not found")
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


@router.post("/compile", status_code=201)
def compile_resume(body: CompileIn, authorization: str | None = Header(default=None)):
    """select -> render -> link -> gate, failing on the first gate that objects.

    The selector chooses under the budget, the LLM phrases, the linker enforces reference
    integrity, the entailment gate rejects any sentence stronger than its cited evidence.
    Only a document that passed both gates is persisted: every stored row traced every
    sentence to a fact at the moment it was written.
    """
    _auth(authorization)
    gateway = _gateway()

    # Read everything, close the session, then call the model (same discipline as extract).
    with db.get_session() as s:
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
            candidate_id=body.candidate_id, job_id=body.job_id,
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
    _auth(authorization)
    with db.get_session() as s:
        doc, bullets, omissions = _load_document(s, did)
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
    _auth(authorization)
    with db.get_session() as s:
        doc, bullets, omissions = _load_document(s, did)
        claims = {c.core.claim_id: c for c in _load_claims(s, doc["candidate_id"])}
        cand = s.execute(sa.select(db.candidates.c.name)
                         .where(db.candidates.c.id == doc["candidate_id"])).first()
        job = s.execute(sa.select(db.job_postings.c.title)
                        .where(db.job_postings.c.id == doc["job_id"])).first()
    payload = render_docx(
        candidate_name=cand.name if cand else "unknown",
        job_title=job.title if job else "unknown",
        bullets=[dict(b) for b in bullets],
        claims_by_id=claims,
        omissions=[Omission(o["claim_id"], o["claim_key"],
                            OmissionReason(o["reason"]), o["detail"])
                   for o in omissions],
        entailment_note=(f"NLI {doc['nli_model']}@{doc['nli_revision'][:12]}, "
                         f"threshold {doc['nli_threshold']}"))
    return Response(
        content=payload,
        media_type=("application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"),
        headers={"Content-Disposition":
                 f'attachment; filename="careercompiler-{did}.docx"'})


@router.post("/compile/check")
def check_bullet(body: CheckIn, authorization: str | None = Header(default=None)):
    """The rejection moment, live. Runs both gates on one edited sentence against its cited
    facts and returns the verdict with evidence. Persists nothing, always 200: the outcome
    of a check is a result, not an error."""
    _auth(authorization)
    with db.get_session() as s:
        doc, _, _ = _load_document(s, body.document_id)
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
