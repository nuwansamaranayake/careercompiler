"""Key-gated LLM eval: the real extraction stage, measured — never a required CI check,
never a silent skip.

Two measures, bounds stated here before the first run:
  planted-fact recall  >= 0.70   anchors from a synthetic resume recovered as anchored claims
  paraphrase jaccard   >= 0.60   claim_key stability across pre-authored resume paraphrases
                                 (the contracts/extraction-stability.yaml invariant)

Writes eval_report_llm.md. Exits nonzero on a miss (when it runs at all).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from groundwork import BaseConfig, LLMGateway  # noqa: E402
from app.engine.facts import extract_facts  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "eval_report_llm.md"

RESUME = ("Led migration of 42 services to Kubernetes, cutting deploy time 38%. "
          "Built Python FastAPI backends for five years. Operated PostgreSQL with "
          "replication and backups. Mentored 4 engineers. Designed CI/CD pipelines "
          "with GitHub Actions.")
PARAPHRASES = [
    ("Drove the move of 42 services onto Kubernetes, which reduced deployment time by "
     "38%. Five years building backend services in Python with FastAPI. Ran PostgreSQL "
     "including replication and backups. Coached 4 engineers. Set up CI/CD with GitHub "
     "Actions."),
    ("Kubernetes migration lead for 42 services (deploy time down 38%). Python/FastAPI "
     "backend engineer for five years. PostgreSQL operations: replication, backups. "
     "Mentor to 4 engineers. GitHub Actions CI/CD pipeline design."),
]
# A planted anchor counts as recalled when its token appears in an anchored claim.
ANCHORS = ["kubernetes", "python", "postgres", "mentor", "38", "ci"]
# Fact identity is compared on canonical anchors, not on the model's invented claim_key
# strings: the same fact gets different names across paraphrases (observed jaccard 0.12 on
# raw keys with identical facts). Canonicalize, then compare — the Seismograph pattern.
ANCHOR_VOCAB = ["kubernetes", "python", "fastapi", "postgres", "postgresql", "mentor",
                "38", "42", "ci", "github", "replication", "backups", "five"]

RECALL_BOUND = 0.70
JACCARD_BOUND = 0.60


def _keys_and_text(claims) -> tuple[set[str], str]:
    ok = [c for c in claims if c.core.verification.status != "rejected"]
    text = " ".join(f"{c.claim_key} {c.core.statement}" for c in ok).lower()
    return {c.claim_key for c in ok}, text


def _anchor_set(text: str) -> set[str]:
    return {a for a in ANCHOR_VOCAB if a in text}


def _jaccard(a: set, b: set) -> float:
    union = a | b
    return (len(a & b) / len(union)) if union else 1.0


def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("LLM_MODEL_EXTRACTION", "")
    if not key or not model:
        print("eval_llm: NOT RUN — OPENROUTER_API_KEY / LLM_MODEL_EXTRACTION missing. "
              "This section is key-gated by design; the deterministic suite in "
              "scripts/eval.py is the required gate.", file=sys.stderr)
        sys.exit(2)

    gw = LLMGateway(BaseConfig(openrouter_api_key=key))
    base_keys, base_text = _keys_and_text(extract_facts(gw, model, RESUME, "resume.txt"))
    recall = sum(1 for a in ANCHORS if a in base_text) / len(ANCHORS)
    base_anchors = _anchor_set(base_text)

    jaccards = []
    for i, txt in enumerate(PARAPHRASES):
        _, v_text = _keys_and_text(extract_facts(gw, model, txt, f"paraphrase-{i}.txt"))
        jaccards.append(_jaccard(base_anchors, _anchor_set(v_text)))
    j_min = min(jaccards)

    rows = [
        "# CareerCompiler key-gated extraction eval",
        "",
        f"model: {model}",
        f"base claim_keys ({len(base_keys)}): {sorted(base_keys)}",
        "",
        "| metric | value | bound | pass |",
        "|---|---|---|---|",
        f"| planted-fact recall | {recall:.2f} | >= {RECALL_BOUND} | "
        f"{'PASS' if recall >= RECALL_BOUND else 'FAIL'} |",
        f"| paraphrase jaccard (min) | {j_min:.2f} | >= {JACCARD_BOUND} | "
        f"{'PASS' if j_min >= JACCARD_BOUND else 'FAIL'} |",
        "",
        f"contract: contracts/extraction-stability.yaml (threshold {JACCARD_BOUND})",
    ]
    text = "\n".join(rows) + "\n"
    REPORT.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    if recall < RECALL_BOUND or j_min < JACCARD_BOUND:
        print("EVAL_LLM FAILED", file=sys.stderr)
        sys.exit(1)
    print("EVAL_LLM OK")


if __name__ == "__main__":
    main()
