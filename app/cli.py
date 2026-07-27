"""CLI Fit Report: keyless, serverless, honest.

Usage:
    python -m app.cli fit --facts data/synthetic/golden/golden.json --case platform-role
                          [--report out.md]

Loads the fact graph and one labeled case from a golden-format JSON file, runs the
deterministic matcher, prints the Fit Report, and exits nonzero on a do-not-apply verdict
so a script can branch on it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine.embedding import HashingEmbedder
from .engine.facts import claims_from_entries
from .engine.fit import build_report, render_markdown
from .engine.jd import requirements_from_entries
from .engine.matcher import match


def fit(facts_path: str, case_id: str, report_path: str | None) -> int:
    data = json.loads(Path(facts_path).read_text(encoding="utf-8"))
    claims = claims_from_entries(data["fact_graph"])
    case = next((c for c in data["cases"] if c["case_id"] == case_id), None)
    if case is None:
        print(f"unknown case '{case_id}'; available: "
              f"{[c['case_id'] for c in data['cases']]}", file=sys.stderr)
        return 2
    reqs = requirements_from_entries(case["requirements"])
    report = build_report(match(reqs, claims, HashingEmbedder()))
    text = render_markdown(report)
    if report_path:
        Path(report_path).write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0 if report.verdict == "apply" else 1


def main() -> None:
    ap = argparse.ArgumentParser(prog="careercompiler")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit", help="run a fit report from a golden-format facts file")
    f.add_argument("--facts", required=True)
    f.add_argument("--case", required=True)
    f.add_argument("--report", default=None)
    args = ap.parse_args()
    sys.exit(fit(args.facts, args.case, args.report))


if __name__ == "__main__":
    main()
