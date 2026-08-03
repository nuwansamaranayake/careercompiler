"""Deterministic matcher: requirements versus the fact graph.

Direct match requires shared key tokens or strong semantic similarity; anything weaker that
still clears the transferable floor is PARTIAL and is never presented as direct — the
`direct` flag is load-bearing honesty, asserted by the eval suite. Rejected claims (failed
span anchor) never match anything.
"""
from __future__ import annotations

from dataclasses import dataclass

from .embedding import Embedder, cosine
from .facts import AtomicClaim
from .jd import Requirement

# Tuned on the golden suite with the deterministic embedder; real embeddings score the same
# or higher for genuinely related text, so the floors are conservative in production.
DIRECT_SIM = 0.55
TRANSFER_SIM = 0.22
_STOP = {"and", "or", "of", "with", "in", "to", "the", "a", "for", "on", "at"}
# Generic tokens may not, on their own, establish a direct key match: "development" in
# people_development must not directly satisfy "golang development" (observed in the
# golden eval). Specific tokens (kubernetes, postgres, rust...) carry the match.
# Extended 2026-08-03 from measured real-corpus false matches: "architecture" bridged
# css_in_js to a RAG-architecture fact and "certification" bridged a WCAG requirement
# to an unrelated AI certification — category nouns, not skills. Each addition is a
# measured offender or its direct inflection, never a guess; the golden eval is the
# regression gate.
_GENERIC = {"development", "engineering", "experience", "operations", "management",
            "services", "systems", "team", "platform", "senior", "junior",
            "architecture", "architectures", "certification", "certifications",
            "certified", "testing", "framework", "frameworks"}


def _tokens(text: str) -> set[str]:
    import re
    return {t for t in re.findall(r"[a-z0-9+#]+", text.lower()) if t not in _STOP}


@dataclass(frozen=True)
class MatchRow:
    req_key: str
    must_have: bool
    status: str                  # matched | partial | gap
    direct: bool                 # True only for direct evidence; transferable is never direct
    evidence_claim_ids: list[str]
    score: float
    explanation: str


def match(
    requirements: list[Requirement],
    claims: list[AtomicClaim],
    embedder: Embedder,
) -> list[MatchRow]:
    usable = [c for c in claims if c.core.verification.status != "rejected"]
    rows: list[MatchRow] = []
    if not requirements:
        return rows

    req_texts = [f"{r.req_key} {r.text}" for r in requirements]
    claim_texts = [f"{c.claim_key} {c.core.statement}" for c in usable]
    vecs = embedder.embed(req_texts + claim_texts) if claim_texts else embedder.embed(req_texts)
    req_vecs, claim_vecs = vecs[: len(requirements)], vecs[len(requirements):]

    for r, r_vec in zip(requirements, req_vecs):
        best: tuple[float, AtomicClaim | None, bool] = (0.0, None, False)
        r_toks = _tokens(f"{r.req_key} {r.text}")
        for c, c_vec in zip(usable, claim_vecs):
            sim = cosine(r_vec, c_vec)
            key_overlap = bool(
                (_tokens(c.claim_key.replace("_", " ")) & r_toks) - _GENERIC
            )
            direct = key_overlap or sim >= DIRECT_SIM
            score = sim + (0.35 if key_overlap else 0.0)
            if score > best[0]:
                best = (score, c, direct)
        score, c, direct = best
        if c is not None and direct:
            rows.append(MatchRow(
                req_key=r.req_key, must_have=r.must_have, status="matched", direct=True,
                evidence_claim_ids=[c.core.claim_id], score=round(score, 4),
                explanation=f"direct evidence: {c.claim_key} — {c.core.statement}"))
        elif c is not None and score >= TRANSFER_SIM:
            rows.append(MatchRow(
                req_key=r.req_key, must_have=r.must_have, status="partial", direct=False,
                evidence_claim_ids=[c.core.claim_id], score=round(score, 4),
                explanation=(f"transferable (not direct): {c.claim_key} — "
                             f"{c.core.statement}")))
        else:
            rows.append(MatchRow(
                req_key=r.req_key, must_have=r.must_have, status="gap", direct=False,
                evidence_claim_ids=[], score=round(score, 4),
                explanation="no evidence in the fact graph"))
    return rows
