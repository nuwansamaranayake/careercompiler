"""Eval harness: the golden analyzer suite against the EVAL.md Phase 1 thresholds.

Deterministic and keyless (HashingEmbedder, fixture fact graph, labeled JDs, pre-authored
paraphrase sets). Writes eval_report.md so consecutive runs can be compared byte-for-byte.
The key-gated extraction section (real gateway) is reported separately by
scripts/eval_llm.py and is never a required check — and never a silent skip: this harness
says loudly whether it ran.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine.embedding import HashingEmbedder  # noqa: E402
from app.engine.facts import claims_from_entries  # noqa: E402
from app.engine.fit import build_report  # noqa: E402
from app.engine.jd import requirements_from_entries  # noqa: E402
from app.engine.matcher import match  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "data" / "synthetic" / "golden" / "golden.json"
REPORT = ROOT / "eval_report.md"

BOUNDS = {
    "matcher_accuracy": 0.90,
    "verdict_correctness": 1.00,
    "transferable_violations": 0,
    "paraphrase_invariance": 1.00,
    "match_set_stability_min": 0.85,
}


def _jaccard(a: set, b: set) -> float:
    union = a | b
    return (len(a & b) / len(union)) if union else 1.0


def main() -> None:
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    claims = claims_from_entries(data["fact_graph"], source_name="golden")
    embedder = HashingEmbedder()

    total_labels = correct_labels = 0
    verdict_ok = verdict_total = 0
    transfer_violations = 0
    invariant_ok = invariant_total = 0
    stability_min = 1.0
    rows_out: list[str] = []

    for case in data["cases"]:
        base_reqs = requirements_from_entries(case["requirements"])
        base_rows = match(base_reqs, claims, embedder)
        report = build_report(base_rows)

        for r in base_rows:
            if r.status == "partial" and r.direct:
                transfer_violations += 1
        for req_key, expected in case["labels"].items():
            got = next(r.status for r in base_rows if r.req_key == req_key)
            total_labels += 1
            correct_labels += int(got == expected)
        verdict_total += 1
        verdict_ok += int(report.verdict == case["expected_verdict"])
        base_matched = {r.req_key for r in base_rows if r.status == "matched"}

        for variant in case["paraphrases"]:
            v_rows = match(requirements_from_entries(variant), claims, embedder)
            v_report = build_report(v_rows)
            invariant_total += 1
            invariant_ok += int(v_report.verdict == report.verdict)
            v_matched = {r.req_key for r in v_rows if r.status == "matched"}
            stability_min = min(stability_min, _jaccard(base_matched, v_matched))
        rows_out.append(f"case {case['case_id']}: verdict={report.verdict} "
                        f"(expected {case['expected_verdict']}), "
                        f"matched={sorted(base_matched)}")

    metrics = {
        "matcher_accuracy": correct_labels / total_labels,
        "verdict_correctness": verdict_ok / verdict_total,
        "transferable_violations": transfer_violations,
        "paraphrase_invariance": invariant_ok / invariant_total,
        "match_set_stability_min": stability_min,
    }
    passes = {
        "matcher_accuracy": metrics["matcher_accuracy"] >= BOUNDS["matcher_accuracy"],
        "verdict_correctness": metrics["verdict_correctness"] >= BOUNDS["verdict_correctness"],
        "transferable_violations":
            metrics["transferable_violations"] <= BOUNDS["transferable_violations"],
        "paraphrase_invariance":
            metrics["paraphrase_invariance"] >= BOUNDS["paraphrase_invariance"],
        "match_set_stability_min":
            metrics["match_set_stability_min"] >= BOUNDS["match_set_stability_min"],
    }

    lines = ["# CareerCompiler golden analyzer eval report", ""]
    lines += rows_out + ["", "| metric | value | bound | pass |", "|---|---|---|---|"]
    for k, v in metrics.items():
        bound = BOUNDS[k]
        op = "<=" if k == "transferable_violations" else ">="
        val = round(v, 4) if isinstance(v, float) else v
        lines.append(f"| {k} | {val} | {op} {bound} | {'PASS' if passes[k] else 'FAIL'} |")
    if os.environ.get("OPENROUTER_API_KEY"):
        lines += ["", "key-gated extraction section: run scripts/eval_llm.py "
                      "(not part of this deterministic report)"]
    else:
        lines += ["", "key-gated extraction section: NOT RUN (no OPENROUTER_API_KEY); "
                      "deterministic bounds above are the required gate"]
    text = "\n".join(lines) + "\n"
    REPORT.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    if not all(passes.values()):
        print("EVAL FAILED: at least one threshold missed (see rows above)", file=sys.stderr)
        sys.exit(1)
    print("EVAL OK")


if __name__ == "__main__":
    main()
