"""D2: reference integrity. The cheap, deterministic gate that runs before the model loads.

The expensive gate is entailment. This one is arithmetic and set membership, it costs
microseconds, and it catches the majority of the ways a rendered document goes wrong:

  - a bullet that cites nothing at all
  - a citation to a fact id that does not exist
  - a citation to a fact whose span anchor was rejected
  - a citation to a fact the selector deliberately left off the page
  - a number in the prose that appears in none of the cited facts

The last two are the ones that enforce the thesis. The model phrases; it does not choose
content and it does not compute a number. A bullet citing an omitted fact means the model
chose content. A bullet containing "6 years" when the evidence says "2019 to 2025" means the
model did arithmetic. Both are compile errors here, not style notes, because a document that
is 95% grounded is not grounded.

Running this first is not only an optimization. When the entailment model is unavailable the
build fails (D5), and it is worth knowing that the references were broken anyway.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .facts import AtomicClaim

# Numeric tokens as a reader would see them: 40, 40%, 8k, 12M, 1.2, 2019, $4,000.
_NUMBER = re.compile(r"\$?\d[\d,]*\.?\d*\s*%?|\b\d+[kKmMbB]\b")
_SENTENCE = re.compile(r"[^.!?]+[.!?]?")

# Numbers a bullet may carry without evidence, because they are not claims about the
# candidate: ordinals in list markers and the like. Kept deliberately tiny.
_ALWAYS_ALLOWED: frozenset[str] = frozenset()


class LinkFailure(str, Enum):
    cites_nothing = "cites_nothing"
    unknown_fact_id = "unknown_fact_id"
    cites_rejected_fact = "cites_rejected_fact"
    cites_unselected_fact = "cites_unselected_fact"
    unsupported_number = "unsupported_number"


@dataclass(frozen=True)
class Bullet:
    """One rendered line and the fact ids it claims to render."""

    text: str
    cites: list[str]


@dataclass(frozen=True)
class LinkViolation:
    bullet_index: int
    text: str
    failure: LinkFailure
    detail: str


@dataclass
class LinkReport:
    violations: list[LinkViolation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def raise_if_broken(self) -> None:
        if self.violations:
            raise ReferenceIntegrityError(self)


class ReferenceIntegrityError(Exception):
    """The document cites something it cannot support. This fails the build."""

    def __init__(self, report: LinkReport):
        self.report = report
        first = report.violations[0]
        super().__init__(
            f"{len(report.violations)} reference violation(s); first: "
            f"{first.failure.value} in bullet {first.bullet_index} — {first.detail}")


def normalise_number(token: str) -> str:
    """'$4,000' -> '4000', '40 %' -> '40%', '8K' -> '8k'. Comparison needs one spelling."""
    t = token.strip().lower().replace(",", "").replace("$", "").replace(" ", "")
    if t.endswith("%"):
        return t
    if t and t[-1] in "kmb":
        return t
    # 40.0 and 40 are the same number to a reader
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t


def numbers_in(text: str) -> set[str]:
    return {normalise_number(m.group()) for m in _NUMBER.finditer(text)} - _ALWAYS_ALLOWED


def check(
    bullets: list[Bullet],
    claims: list[AtomicClaim],
    selected_ids: list[str] | None = None,
) -> LinkReport:
    """Verify every bullet against the fact graph. Deterministic, no model involved."""
    by_id = {c.core.claim_id: c for c in claims}
    allowed = set(selected_ids) if selected_ids is not None else None
    report = LinkReport()

    for i, b in enumerate(bullets):
        text = b.text.strip()
        if not b.cites:
            report.violations.append(LinkViolation(
                i, text, LinkFailure.cites_nothing,
                "the sentence cites no fact, so nothing supports it"))
            continue

        supported_numbers: set[str] = set()
        resolved: list[AtomicClaim] = []
        for cid in b.cites:
            claim = by_id.get(cid)
            if claim is None:
                report.violations.append(LinkViolation(
                    i, text, LinkFailure.unknown_fact_id,
                    f"cites fact {cid!r}, which is not in the fact graph"))
                continue
            if claim.core.verification.status == "rejected":
                report.violations.append(LinkViolation(
                    i, text, LinkFailure.cites_rejected_fact,
                    f"cites fact {cid!r}, whose span anchor was rejected"))
                continue
            if allowed is not None and cid not in allowed:
                report.violations.append(LinkViolation(
                    i, text, LinkFailure.cites_unselected_fact,
                    f"cites fact {cid!r}, which the selector left off the page; the model "
                    "phrases content, it does not choose it"))
                continue
            resolved.append(claim)
            supported_numbers |= numbers_in(claim.core.statement)

        for token in sorted(numbers_in(text) - supported_numbers):
            report.violations.append(LinkViolation(
                i, text, LinkFailure.unsupported_number,
                f"the number {token!r} appears in no cited fact; the model computed or "
                "invented it"))

    return report


def sentences(text: str) -> list[str]:
    """Sentence split for the provenance map and per-sentence reporting."""
    return [s.strip() for s in _SENTENCE.findall(text) if s.strip()]
