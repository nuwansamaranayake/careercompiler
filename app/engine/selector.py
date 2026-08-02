"""C1/C2: choose what goes on the page, and say why everything else did not.

A resume is a knapsack problem wearing a suit. There is a hard page budget, every fact costs
lines, and the value of a fact depends on which requirement it covers and how well the
evidence supports it. This module solves that with CP-SAT and returns both halves of the
answer: what was selected, and a typed reason for every fact that was not.

The second half is the product. A selector that silently drops evidence is not explainable,
and explainability is the whole claim this application makes. So `Selection.omitted` carries
one `Omission` per eligible-but-unselected fact, and the four reasons are distinguishable:
a fact nothing in the posting asked for is a different answer than a fact that lost on value
per line, and a reviewer is entitled to know which one happened.

Deterministic by construction: single search worker, fixed seed, integer objective. The same
inputs produce the same page.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from ortools.sat.python import cp_model

from .facts import AtomicClaim, FactKind
from .jd import Requirement
from .matcher import MatchRow

# Objective weights, integer because CP-SAT is integer. Covering a must-have dominates every
# quality term: a page that reads beautifully and misses a hard requirement has failed.
W_MUST_HAVE = 5000
W_NICE_TO_HAVE = 1500
W_STRENGTH = 100
W_RECENCY = 60
W_QUANTIFIED = 80

RECENCY_HALF_LIFE_YEARS = 10.0
DEFAULT_CONFIDENCE = 0.5
CHARS_PER_LINE = 90

# Facts that carry a number or a measured outcome. These are what a hiring manager reads.
QUANTIFIED_KINDS = (FactKind.magnitude, FactKind.outcome)


class OmissionReason(str, Enum):
    """Why a fact did not reach the page. Four distinguishable answers, not one shrug."""

    rejected_span_anchor = "rejected_span_anchor"
    no_requirement_matched = "no_requirement_matched"
    redundant_coverage = "redundant_coverage"
    budget_exhausted = "budget_exhausted"


@dataclass(frozen=True)
class Omission:
    claim_id: str
    claim_key: str
    reason: OmissionReason
    detail: str


@dataclass(frozen=True)
class Selection:
    selected: list[str]
    omitted: list[Omission]
    covered_must: list[str]
    covered_nice: list[str]
    uncovered_must: list[str]
    budget_lines: int
    used_lines: int

    @property
    def rejected_anything(self) -> bool:
        """C3: a selector that selected everything has measured nothing."""
        return bool(self.omitted)


def _lines_for(claim: AtomicClaim) -> int:
    return 1 + len(claim.core.statement) // CHARS_PER_LINE


def _recency(claim: AtomicClaim, today: date) -> float:
    """1.0 for a fact observed today, decaying to 0 over the half-life. Unknown dates score 0
    rather than a flattering guess: an undated fact has not earned recency credit."""
    observed = claim.core.observed_at
    if observed is None:
        return 0.0
    years = (today - observed).days / 365.25
    return max(0.0, 1.0 - years / RECENCY_HALF_LIFE_YEARS)


def _quality(claim: AtomicClaim, today: date) -> int:
    strength = claim.core.confidence if claim.core.confidence is not None else DEFAULT_CONFIDENCE
    quantified = 1.0 if claim.kind in QUANTIFIED_KINDS else 0.0
    return int(round(
        W_STRENGTH * strength
        + W_RECENCY * _recency(claim, today)
        + W_QUANTIFIED * quantified
    ))


def select(
    claims: list[AtomicClaim],
    requirements: list[Requirement],
    rows: list[MatchRow],
    budget_lines: int,
    today: date | None = None,
) -> Selection:
    """Maximize requirement coverage and evidence quality under a hard line budget."""
    if budget_lines < 0:
        raise ValueError("budget_lines must not be negative")
    today = today or date.today()

    by_id = {c.core.claim_id: c for c in claims}
    omitted: list[Omission] = []

    # A fact whose span anchor failed verification is never eligible. It is recorded as an
    # omission rather than dropped quietly, because "we could not anchor this to your resume"
    # is exactly the kind of thing a candidate needs to be told.
    eligible: list[AtomicClaim] = []
    for c in claims:
        if c.core.verification.status == "rejected":
            omitted.append(Omission(
                c.core.claim_id, c.claim_key, OmissionReason.rejected_span_anchor,
                "the quote could not be anchored to a span in the source document"))
        else:
            eligible.append(c)

    # Which facts support which requirement, from the deterministic matcher's evidence.
    supporting: dict[str, list[str]] = {r.req_key: [] for r in requirements}
    for row in rows:
        if row.status == "gap":
            continue
        for cid in row.evidence_claim_ids:
            if cid in by_id and cid in {c.core.claim_id for c in eligible}:
                supporting.setdefault(row.req_key, []).append(cid)

    supports_something = {cid for ids in supporting.values() for cid in ids}

    model = cp_model.CpModel()
    x = {c.core.claim_id: model.new_bool_var(f"x_{c.core.claim_id}") for c in eligible}
    y = {r.req_key: model.new_bool_var(f"y_{r.req_key}") for r in requirements}

    model.add(sum(x[c.core.claim_id] * _lines_for(c) for c in eligible) <= budget_lines)

    # A requirement counts as covered only if at least one selected fact supports it.
    for r in requirements:
        ids = supporting.get(r.req_key, [])
        if ids:
            model.add(y[r.req_key] <= sum(x[i] for i in ids))
        else:
            model.add(y[r.req_key] == 0)

    model.maximize(
        sum(y[r.req_key] * (W_MUST_HAVE if r.must_have else W_NICE_TO_HAVE)
            for r in requirements)
        + sum(x[c.core.claim_id] * _quality(c, today) for c in eligible)
    )

    solver = cp_model.CpSolver()
    # Determinism over speed: one worker, fixed seed. The same inputs must produce the same
    # page, or the eval numbers below mean nothing.
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            f"content selection found no feasible page within {budget_lines} lines "
            f"(solver status {solver.status_name(status)})")

    selected = [c.core.claim_id for c in eligible if solver.value(x[c.core.claim_id])]
    selected_set = set(selected)
    covered = {r.req_key for r in requirements if solver.value(y[r.req_key])}

    for c in eligible:
        cid = c.core.claim_id
        if cid in selected_set:
            continue
        if cid not in supports_something:
            omitted.append(Omission(
                cid, c.claim_key, OmissionReason.no_requirement_matched,
                "nothing in this posting asks for it"))
            continue
        its_reqs = [rk for rk, ids in supporting.items() if cid in ids]
        if all(rk in covered for rk in its_reqs):
            omitted.append(Omission(
                cid, c.claim_key, OmissionReason.redundant_coverage,
                f"{', '.join(sorted(its_reqs))} already covered by stronger evidence"))
        else:
            omitted.append(Omission(
                cid, c.claim_key, OmissionReason.budget_exhausted,
                f"lost on value per line within the {budget_lines}-line budget"))

    used = sum(_lines_for(by_id[cid]) for cid in selected)
    return Selection(
        selected=selected,
        omitted=omitted,
        covered_must=sorted(r.req_key for r in requirements
                            if r.must_have and r.req_key in covered),
        covered_nice=sorted(r.req_key for r in requirements
                            if not r.must_have and r.req_key in covered),
        uncovered_must=sorted(r.req_key for r in requirements
                              if r.must_have and r.req_key not in covered),
        budget_lines=budget_lines,
        used_lines=used,
    )
