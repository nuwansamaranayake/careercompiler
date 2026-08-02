"""Part C: the knapsack content selector, and the gates that stop it passing vacuously.

The estate has shipped two vacuous passes already — Almanac at 130/130/130 from a noiseless
fixture, Parallax at drift 0.0000 from an all-done board. Both "passed" by measuring nothing.
The tests below are written so that a selector which simply selects everything, or omits
everything without a reason, fails.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.engine.facts import claims_from_entries
from app.engine.jd import requirements_from_entries
from app.engine.matcher import MatchRow
from app.engine.selector import OmissionReason, select

TODAY = date(2026, 8, 2)


def _claims(*specs):
    """specs: (claim_key, statement, kind)."""
    return claims_from_entries([
        {"claim_key": k, "statement": s, "kind": kind} for k, s, kind in specs])


def _reqs(*specs):
    """specs: (req_key, text, must_have)."""
    return requirements_from_entries([
        {"req_key": k, "text": t, "kind": "skill", "must_have": m} for k, t, m in specs])


def _row(req_key, must_have, claim_ids, status="matched", score=0.9):
    return MatchRow(req_key=req_key, must_have=must_have, status=status, direct=True,
                    evidence_claim_ids=list(claim_ids), score=score,
                    explanation="test fixture")


def test_selection_covers_must_haves_within_the_budget():
    claims = _claims(("k8s", "Ran Kubernetes in production for 3 years.", "skill"),
                     ("py", "Wrote Python services for 6 years.", "skill"))
    reqs = _reqs(("k8s", "Kubernetes required", True), ("py", "Python required", True))
    rows = [_row("k8s", True, [claims[0].core.claim_id]),
            _row("py", True, [claims[1].core.claim_id])]

    sel = select(claims, reqs, rows, budget_lines=10, today=TODAY)

    assert sel.covered_must == ["k8s", "py"]
    assert sel.uncovered_must == []
    assert sel.used_lines <= sel.budget_lines


def test_a_budget_too_small_to_fit_everything_produces_omissions_with_reasons():
    """C3: the load-bearing test. A selector that passes by selecting everything has
    measured nothing, so force the budget below the total and require real reasons."""
    claims = _claims(*[(f"k{i}", f"Fact number {i} about a skill.", "skill")
                       for i in range(6)])
    reqs = _reqs(*[(f"k{i}", f"Requirement {i}", i < 2) for i in range(6)])
    rows = [_row(f"k{i}", i < 2, [claims[i].core.claim_id]) for i in range(6)]

    sel = select(claims, reqs, rows, budget_lines=3, today=TODAY)

    assert sel.used_lines <= 3
    assert len(sel.selected) == 3, "the budget was not actually binding"
    assert sel.rejected_anything, "the selector selected everything: it measured nothing"
    assert len(sel.omitted) == 3

    # every omission carries a typed reason and a human sentence, not a shrug
    for o in sel.omitted:
        assert isinstance(o.reason, OmissionReason)
        assert o.detail.strip(), f"omission of {o.claim_key} carries no explanation"

    # must-haves outrank nice-to-haves when the budget bites
    assert set(sel.covered_must) == {"k0", "k1"}


def test_must_have_coverage_outranks_a_stronger_but_irrelevant_fact():
    """The objective must not be talked out of a hard requirement by a prettier fact."""
    claims = _claims(("k8s", "Kubernetes in production.", "skill"),
                     ("award", "Won a large industry award with a big number, 99%.",
                      "magnitude"))
    reqs = _reqs(("k8s", "Kubernetes required", True))
    rows = [_row("k8s", True, [claims[0].core.claim_id])]

    sel = select(claims, reqs, rows, budget_lines=1, today=TODAY)

    assert sel.selected == [claims[0].core.claim_id]
    assert sel.covered_must == ["k8s"]
    omitted = {o.claim_key: o for o in sel.omitted}
    assert omitted["award"].reason is OmissionReason.no_requirement_matched


def test_a_fact_nothing_asked_for_is_distinguished_from_one_that_lost_on_budget():
    """Two different answers a reviewer is entitled to tell apart."""
    claims = _claims(("k8s", "Kubernetes in production.", "skill"),
                     ("py", "Python for six years.", "skill"),
                     ("juggling", "Can juggle five clubs.", "other"))
    reqs = _reqs(("k8s", "Kubernetes required", True), ("py", "Python required", True))
    rows = [_row("k8s", True, [claims[0].core.claim_id]),
            _row("py", True, [claims[1].core.claim_id])]

    sel = select(claims, reqs, rows, budget_lines=1, today=TODAY)

    reasons = {o.claim_key: o.reason for o in sel.omitted}
    assert reasons["juggling"] is OmissionReason.no_requirement_matched
    lost = [k for k, r in reasons.items() if r is OmissionReason.budget_exhausted]
    assert lost, "a fact that competed and lost must say so, not claim nobody asked"


def test_a_rejected_span_anchor_is_never_selected_and_says_why():
    claims = _claims(("k8s", "Kubernetes in production.", "skill"))
    claims[0].core.verification.status = "rejected"
    reqs = _reqs(("k8s", "Kubernetes required", True))
    rows = [_row("k8s", True, [claims[0].core.claim_id])]

    sel = select(claims, reqs, rows, budget_lines=10, today=TODAY)

    assert sel.selected == []
    assert sel.uncovered_must == ["k8s"], "an unanchored fact must not cover a requirement"
    assert sel.omitted[0].reason is OmissionReason.rejected_span_anchor


def test_redundant_coverage_is_reported_as_redundant_not_as_budget():
    claims = _claims(("k8s_a", "Kubernetes in production at Acme.", "skill"),
                     ("k8s_b", "Also used Kubernetes at Globex.", "skill"))
    reqs = _reqs(("k8s", "Kubernetes required", True))
    rows = [_row("k8s", True, [c.core.claim_id for c in claims])]

    sel = select(claims, reqs, rows, budget_lines=1, today=TODAY)

    assert len(sel.selected) == 1
    assert sel.omitted[0].reason is OmissionReason.redundant_coverage
    assert "already covered" in sel.omitted[0].detail


def test_recency_breaks_a_tie_and_an_undated_fact_gets_no_credit():
    claims = _claims(("a", "Recent work on the platform.", "skill"),
                     ("b", "Older work on the platform.", "skill"))
    claims[0].core.observed_at = TODAY - timedelta(days=30)
    claims[1].core.observed_at = TODAY - timedelta(days=9 * 365)
    reqs = _reqs(("plat", "Platform work", True))
    rows = [_row("plat", True, [c.core.claim_id for c in claims])]

    sel = select(claims, reqs, rows, budget_lines=1, today=TODAY)

    assert sel.selected == [claims[0].core.claim_id], "the older fact won a recency tie-break"


def test_selection_is_deterministic():
    """The eval numbers mean nothing if the same inputs can produce a different page."""
    claims = _claims(*[(f"k{i}", f"Fact number {i} about a skill.", "skill")
                       for i in range(8)])
    reqs = _reqs(*[(f"k{i}", f"Requirement {i}", i < 3) for i in range(8)])
    rows = [_row(f"k{i}", i < 3, [claims[i].core.claim_id]) for i in range(8)]

    first = select(claims, reqs, rows, budget_lines=4, today=TODAY)
    for _ in range(3):
        again = select(claims, reqs, rows, budget_lines=4, today=TODAY)
        assert again.selected == first.selected
        assert [o.reason for o in again.omitted] == [o.reason for o in first.omitted]


def test_zero_budget_selects_nothing_and_explains_every_fact():
    claims = _claims(("k8s", "Kubernetes in production.", "skill"))
    reqs = _reqs(("k8s", "Kubernetes required", True))
    rows = [_row("k8s", True, [claims[0].core.claim_id])]

    sel = select(claims, reqs, rows, budget_lines=0, today=TODAY)

    assert sel.selected == []
    assert len(sel.omitted) == len(claims), "a dropped fact with no reason is not explainable"


def test_negative_budget_is_rejected():
    with pytest.raises(ValueError, match="must not be negative"):
        select([], [], [], budget_lines=-1, today=TODAY)
