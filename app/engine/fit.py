"""The Fit Report, including the case against applying.

Deterministic assembly over MatchRows. A must-have requirement with no evidence at all is a
disqualifying gap, and the verdict says do_not_apply — the honesty commercial tools cannot
afford. Transferable evidence is labeled transferable in every rendering.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .matcher import MatchRow


@dataclass(frozen=True)
class FitReport:
    rows: list[MatchRow]
    matched: int
    partial: int
    gaps: int
    disqualifying_gaps: list[str] = field(default_factory=list)
    verdict: str = "apply"           # apply | do_not_apply
    case_against: str = ""


def build_report(rows: list[MatchRow]) -> FitReport:
    matched = sum(1 for r in rows if r.status == "matched")
    partial = sum(1 for r in rows if r.status == "partial")
    gaps = sum(1 for r in rows if r.status == "gap")
    disqualifying = [r.req_key for r in rows if r.status == "gap" and r.must_have]
    verdict = "do_not_apply" if disqualifying else "apply"
    case_against = ""
    if disqualifying:
        case_against = (
            "Must-have requirement(s) with no evidence in the fact graph: "
            + ", ".join(disqualifying)
            + ". For most postings of this type these are disqualifying. Add real evidence "
              "via the interview flow, or do not apply."
        )
    return FitReport(
        rows=rows, matched=matched, partial=partial, gaps=gaps,
        disqualifying_gaps=disqualifying, verdict=verdict, case_against=case_against,
    )


def render_markdown(report: FitReport, contract_note: str = "") -> str:
    n = len(report.rows)
    lines = [
        "# Fit Report",
        "",
        f"**Verdict: {report.verdict.replace('_', ' ').upper()}** — matched "
        f"{report.matched} of {n} requirements ({report.partial} transferable, "
        f"{report.gaps} gaps).",
        "",
    ]
    if report.case_against:
        lines += [f"> {report.case_against}", ""]
    lines += ["| requirement | must-have | status | evidence |", "|---|---|---|---|"]
    for r in report.rows:
        status = r.status if r.direct or r.status != "partial" else "partial (transferable)"
        lines.append(f"| {r.req_key} | {'yes' if r.must_have else 'no'} | {status} | "
                     f"{r.explanation} |")
    if contract_note:
        lines += ["", contract_note]
    return "\n".join(lines) + "\n"
