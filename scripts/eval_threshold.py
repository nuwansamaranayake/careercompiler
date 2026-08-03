"""Entailment threshold calibration: the graded suite the 0.7 threshold never had.

Passing bullets sat at 0.99+ and rejections at ~0.001 — nothing between was measured, so
0.7 was a guess standing between two cliffs. This suite grades the space between: mild
overstatement, right number wrong unit, right claim wrong employer, stretched timeframe,
and hedges that weaken a supported claim. Run against the pinned NLI (the same model and
revision production gates with), it draws the curve a threshold should be chosen from.

Run: python scripts/eval_threshold.py   (inside cc-test; the model is baked into the image)
Writes a markdown table to stdout — paste into EVAL.md, publish the misses.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine.entailment import _load  # the exact scorer the gate uses

MODEL = os.getenv("NLI_MODEL", "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")
REV = os.getenv("NLI_MODEL_REVISION", "6f5cf0a2b59cabb106aca4c287eed12e357e90eb")

# (category, expected, premise, hypothesis)
# expected: "entail" — a faithful gate should pass it; "reject" — it must not survive.
CASES = [
    # Faithful controls — restatements that claim nothing extra.
    ("faithful", "entail",
     "Led a team of 4 engineers at Acme Corp from 2019 to 2022.",
     "Led a team of 4 engineers at Acme Corp."),
    ("faithful", "entail",
     "Cut deploy time 40% by rebuilding the CI pipeline in Python.",
     "Reduced deployment time by 40% through a CI pipeline rebuild."),
    ("faithful", "entail",
     "Ran Kubernetes in production at Globex.",
     "Operated production Kubernetes at Globex."),
    ("faithful", "entail",
     "Migrated a 12M row Postgres table with zero downtime.",
     "Completed a zero-downtime migration of a 12M row Postgres table."),

    # Mild overstatement — one notch beyond the evidence.
    ("mild_overstatement", "reject",
     "Led a team of 4 engineers at Acme Corp from 2019 to 2022.",
     "Led a large engineering team at Acme Corp."),
    ("mild_overstatement", "reject",
     "Ran Kubernetes in production at Globex.",
     "Expert in running Kubernetes in production at Globex."),
    ("mild_overstatement", "reject",
     "Cut deploy time 40% by rebuilding the CI pipeline in Python.",
     "Transformed engineering velocity by rebuilding the CI pipeline."),
    ("mild_overstatement", "reject",
     "Wrote Terraform modules that provisioned cloud infrastructure.",
     "Owned all cloud infrastructure strategy through Terraform."),

    # Right number, wrong unit.
    ("wrong_unit", "reject",
     "Cut deploy time 40% by rebuilding the CI pipeline in Python.",
     "Cut deploy time by 40 minutes by rebuilding the CI pipeline in Python."),
    ("wrong_unit", "reject",
     "Migrated a 12M row Postgres table with zero downtime.",
     "Migrated a 12GB Postgres table with zero downtime."),
    ("wrong_unit", "reject",
     "Led a team of 4 engineers at Acme Corp.",
     "Led 4 engineering teams at Acme Corp."),
    ("wrong_unit", "reject",
     "Served 40 microservices across 3 clusters.",
     "Served 40 customers across 3 clusters."),

    # Right claim, wrong employer.
    ("wrong_employer", "reject",
     "Ran Kubernetes in production at Globex.",
     "Ran Kubernetes in production at Initech."),
    ("wrong_employer", "reject",
     "Led a team of 4 engineers at Acme Corp from 2019 to 2022.",
     "Led a team of 4 engineers at Globex from 2019 to 2022."),
    ("wrong_employer", "reject",
     "Cut deploy time 40% at Acme Corp.",
     "Cut deploy time 40% at Vandelay Industries."),

    # Stretched timeframe.
    ("stretched_time", "reject",
     "Led a team of 4 engineers at Acme Corp from 2019 to 2022.",
     "Led a team of 4 engineers at Acme Corp for over a decade."),
    ("stretched_time", "reject",
     "Built and operated Python services in production for 6 years.",
     "Built and operated Python services in production for 10+ years."),
    ("stretched_time", "reject",
     "Ran Kubernetes in production at Globex since 2021.",
     "Ran Kubernetes in production at Globex since 2015."),

    # Hedge that weakens a supported claim — honest, should still entail.
    ("weakening_hedge", "entail",
     "Led a team of 4 engineers at Acme Corp from 2019 to 2022.",
     "Helped lead a small team of engineers at Acme Corp."),
    ("weakening_hedge", "entail",
     "Cut deploy time 40% by rebuilding the CI pipeline in Python.",
     "Contributed to cutting deploy time by rebuilding the CI pipeline."),
    ("weakening_hedge", "entail",
     "Ran Kubernetes in production at Globex.",
     "Worked with Kubernetes in production at Globex."),
]


def main() -> int:
    scorer = _load(MODEL, REV)
    rows = []
    for cat, expected, premise, hyp in CASES:
        rows.append((cat, expected, scorer(premise, hyp), premise, hyp))

    print(f"NLI {MODEL} @ {REV[:12]}\n")
    print("| category | expected | score | hypothesis |")
    print("|---|---|---|---|")
    for cat, expected, score, _, hyp in rows:
        print(f"| {cat} | {expected} | {score:.4f} | {hyp[:70]} |")

    # The curve: how each candidate threshold does against the graded labels.
    print("\n| threshold | false accepts (should-reject above t) | "
          "false rejects (should-entail below t) |")
    print("|---|---|---|")
    best = None
    for t10 in range(1, 100):
        t = t10 / 100
        fa = sum(1 for _, e, s, _, _ in rows if e == "reject" and s >= t)
        fr = sum(1 for _, e, s, _, _ in rows if e == "entail" and s < t)
        if best is None or fa + fr < best[1] + best[2]:
            best = (t, fa, fr)
    for t in (0.3, 0.5, 0.6, 0.7, 0.8, 0.9, best[0]):
        fa = sum(1 for _, e, s, _, _ in rows if e == "reject" and s >= t)
        fr = sum(1 for _, e, s, _, _ in rows if e == "entail" and s < t)
        mark = "  <-- best by total misses" if abs(t - best[0]) < 1e-9 else ""
        print(f"| {t:.2f} | {fa} | {fr} |{mark}")

    print("\nMisses at the best threshold "
          f"({best[0]:.2f}: {best[1]} false accepts, {best[2]} false rejects):")
    for cat, expected, score, premise, hyp in rows:
        miss = (expected == "reject" and score >= best[0]) or \
               (expected == "entail" and score < best[0])
        if miss:
            print(f"- [{cat}] expected {expected}, scored {score:.4f}: "
                  f"\"{hyp}\" vs \"{premise}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
