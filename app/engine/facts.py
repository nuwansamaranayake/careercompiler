"""The Career Fact Graph atoms: span-anchored atomic claims on the groundwork spine.

A resume bullet decomposes into typed claims, each anchored to a literal quote from the
source document. The anchor is the deterministic back-check: a claim whose quote cannot be
found verbatim in the source is marked rejected — kept, never silently dropped. Facts also
arrive by explicit data entry (self-attested), a real product path that needs no LLM.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

from groundwork import Claim, ClaimType, EvidenceRef, Extractor, Verification
from pydantic import BaseModel, Field


class FactKind(str, Enum):
    skill = "skill"
    role = "role"
    scope = "scope"
    outcome = "outcome"
    magnitude = "magnitude"
    education = "education"
    other = "other"


class Provenance(str, Enum):
    document_sourced = "document_sourced"
    self_attested = "self_attested"


class AtomicClaim(BaseModel):
    """One verifiable career fact. `core` is the portfolio-wide claim atom (provenance,
    bitemporality, verification state); the app adds its typed key and sourcing flag.

    `failed_quote` is transient extraction context, never persisted: the verbatim quote the
    model offered as evidence when that quote could not be located in the source. It exists
    so a rejection can be shown as what it is — the anchor check working — instead of a
    bare count."""
    core: Claim
    claim_key: str = Field(min_length=1)
    kind: FactKind
    provenance: Provenance
    failed_quote: str | None = None


EXTRACTION_SCHEMA = {
    "name": "atomic_claims",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim_key": {"type": "string"},
                        "kind": {"type": "string",
                                 "enum": [k.value for k in FactKind]},
                        "statement": {"type": "string"},
                        "quote": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["claim_key", "kind", "statement", "quote", "confidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["claims"],
        "additionalProperties": False,
    },
}


class CompletesJson(Protocol):
    def complete(self, *, model: str, messages: list[dict],
                 json_schema: dict | None = None, temperature: float = 0.0): ...


def _claim_id(source: str, claim_key: str, statement: str) -> str:
    return hashlib.sha256(f"{source}|{claim_key}|{statement}".encode()).hexdigest()[:16]


def extract_facts(
    gateway: CompletesJson,
    model: str,
    resume_text: str,
    source_name: str,
) -> list[AtomicClaim]:
    """LLM decomposes the resume into atomic claims; the span anchor disposes.

    Every returned claim carries verification: "pending" when its quote anchors verbatim in
    the source (span recorded), "rejected" when it does not. Nothing is silently dropped.
    """
    if not model:
        raise RuntimeError("LLM_MODEL_EXTRACTION is not set. Refusing to guess a model.")
    result = gateway.complete(
        model=model,
        messages=[
            {"role": "system",
             "content": ("Decompose the resume into atomic career claims. One fact per "
                         "claim: separate the action, the scope, the platform, and each "
                         "measured outcome. claim_key is a short snake_case label (e.g. "
                         "platform_kubernetes, scope_42_services). quote is a VERBATIM "
                         "substring of the resume that evidences the claim. Never infer "
                         "facts that are not in the text. Return JSON.")},
            {"role": "user", "content": resume_text},
        ],
        json_schema=EXTRACTION_SCHEMA,
    )
    # Provider quirk observed live (qwen3.6-flash): despite the strict object schema, the
    # model sometimes returns the claims array at the top level. Normalize the envelope
    # only — every item still validates strictly below.
    if isinstance(result, list):
        result = {"claims": result}
    now = datetime.now(timezone.utc)
    claims: list[AtomicClaim] = []
    for item in result.get("claims", []):
        quote = item["quote"]
        idx = resume_text.find(quote)
        anchored = idx >= 0 and bool(quote.strip())
        core = Claim(
            claim_id=_claim_id(source_name, item["claim_key"], item["statement"]),
            type=ClaimType.skill_evidence,
            statement=item["statement"],
            evidence_ref=EvidenceRef(
                source=source_name,
                span=(idx, idx + len(quote)) if anchored else None,
            ),
            recorded_at=now,
            extracted_by=Extractor(model=model, version="phase-1", temp=0.0),
            confidence=max(0.0, min(1.0, float(item["confidence"]))),
            verification=Verification(
                status="pending" if anchored else "rejected",
                gates=["span_anchor"],
                score=1.0 if anchored else 0.0,
            ),
        )
        claims.append(AtomicClaim(
            core=core,
            claim_key=item["claim_key"],
            kind=FactKind(item["kind"]),
            provenance=Provenance.document_sourced,
            failed_quote=None if anchored else quote,
        ))
    return claims


def claims_from_entries(entries: list[dict], source_name: str = "user-entry") -> list[AtomicClaim]:
    """Explicit data-entry path: the user types facts in. Self-attested, clearly flagged;
    no LLM involved. Raises on malformed entries — no partial silent acceptance."""
    now = datetime.now(timezone.utc)
    out: list[AtomicClaim] = []
    for e in entries:
        out.append(AtomicClaim(
            core=Claim(
                claim_id=_claim_id(source_name, e["claim_key"], e["statement"]),
                type=ClaimType.skill_evidence,
                statement=e["statement"],
                evidence_ref=EvidenceRef(source=source_name, span=None),
                recorded_at=now,
                extracted_by=Extractor(model="manual", version="entry", temp=0.0),
                confidence=1.0,
                verification=Verification(status="pending", gates=["self_attested"]),
            ),
            claim_key=e["claim_key"],
            kind=FactKind(e.get("kind", "other")),
            provenance=Provenance.self_attested,
        ))
    return out
