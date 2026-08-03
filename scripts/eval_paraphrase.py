"""C4: paraphrase stability of the fit loop.

The claim: the matched-requirement set should survive a paraphrase of the same job
description. Two JDs describing the identical role in different words go through the
real LLM parse and the deterministic matcher against a fixed fact set; the metric is
Jaccard similarity of the matched req-key sets. Acceptance (EVAL.md): >= 0.85.

Requirement keys are model-chosen labels, so raw key strings differ across paraphrases
("k8s_production" vs "kubernetes_production"). Comparing keys would measure spelling,
not matching. This eval therefore compares WHICH FACTS matched, by claim id — the
matcher's actual decision — and reports both views.

Run: python scripts/eval_paraphrase.py   (needs OPENROUTER_API_KEY + models in env)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groundwork import BaseConfig, LLMGateway

from app.engine.embedding import HashingEmbedder, OpenRouterEmbedder
from app.engine.facts import claims_from_entries
from app.engine.jd import parse_jd
from app.engine.matcher import match

FACTS = [
    {"claim_key": "team_lead", "kind": "role",
     "statement": "Led a team of 4 engineers at Acme Corp from 2019 to 2022."},
    {"claim_key": "k8s", "kind": "skill",
     "statement": "Ran Kubernetes in production at Globex across 3 clusters."},
    {"claim_key": "terraform", "kind": "skill",
     "statement": "Wrote Terraform modules that provisioned all cloud infrastructure."},
    {"claim_key": "ci", "kind": "outcome",
     "statement": "Cut deploy time 40% by rebuilding the CI pipeline in Python."},
    {"claim_key": "oncall", "kind": "role",
     "statement": "Carried the on-call pager and led incident response."},
    {"claim_key": "python", "kind": "skill",
     "statement": "Built and operated Python services in production for 6 years."},
]

JD_A = """Platform Engineer. We run our product on Kubernetes and manage everything
with Terraform. Requirements: Kubernetes in production. Infrastructure as code with
Terraform. CI/CD pipeline ownership. On-call incident response. Python services in
production. Nice to have: team leadership."""

JD_B = """We are hiring a Platform Engineer. You will operate our container platform
and codify our cloud. Must have: production experience operating Kubernetes clusters.
Defining infrastructure in Terraform. Owning continuous integration and deployment
pipelines. Taking part in the on-call rotation and handling incidents. Running Python
backend services in production. Bonus: experience leading engineers."""


def main() -> int:
    key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("LLM_MODEL_EXTRACTION")
    if not key or not model:
        print("BLOCKED: OPENROUTER_API_KEY and LLM_MODEL_EXTRACTION must be set")
        return 2
    gw = LLMGateway(BaseConfig(
        openrouter_api_key=key,
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL") or None))
    claims = claims_from_entries(FACTS)
    if os.getenv("EVAL_EMBEDDER") == "openrouter":
        emb = OpenRouterEmbedder(
            api_key=key, model=os.environ["EMBEDDING_MODEL"],
            base_url=os.getenv("OPENROUTER_BASE_URL") or None)
    else:
        emb = HashingEmbedder()
    print(f"embedder: {emb.name}")

    results = []
    for name, jd in (("A", JD_A), ("B", JD_B)):
        reqs = parse_jd(gw, model, jd)
        rows = match(reqs, claims, emb)
        matched_facts = frozenset(
            cid for r in rows if r.status == "matched" for cid in r.evidence_claim_ids)
        matched_keys = sorted(r.req_key for r in rows if r.status == "matched")
        results.append((name, len(reqs), matched_keys, matched_facts))
        print(f"JD {name}: {len(reqs)} requirements parsed; "
              f"matched req keys: {matched_keys}")

    fa, fb = results[0][3], results[1][3]
    union = fa | fb
    jacc = (len(fa & fb) / len(union)) if union else 1.0
    print(f"\nMatched-FACT sets: |A|={len(fa)} |B|={len(fb)} "
          f"intersection={len(fa & fb)} union={len(union)}")
    print(f"Jaccard(matched facts) = {jacc:.3f}  (acceptance >= 0.85)")
    print("C4 PASS" if jacc >= 0.85 else "C4 FAIL")
    return 0 if jacc >= 0.85 else 1


if __name__ == "__main__":
    raise SystemExit(main())
