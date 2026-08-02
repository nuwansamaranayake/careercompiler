# Truth layer — CareerCompiler public frontend (pre-deploy, 2026-08-03)

Scope: every public-facing sentence on careercompiler.aigniteconsulting.ai. Rule: no claim
on the page that the evals do not support. Each canonical fact below carries its evidence.

## Diagnosis

The product's risk is not under-claiming, it is the default genre of AI copy: "AI-powered
resume builder" flattens into every competitor's sentence and invites exactly the
overclaiming this product exists to reject. The defensible position is the opposite: a
compiler that REFUSES output, with the refusal visible and scored. Lead with the rejection,
not the generation.

## Truth layer (canonical facts, with evidence)

| Fact | Evidence |
|---|---|
| Every rendered sentence cites the facts it renders; a sentence citing nothing, citing a nonexistent fact, or carrying a number found in no cited fact fails the compile deterministically | `tests/test_gates.py`, E2E `evidence/2026-08-02-local-e2e.txt` |
| A sentence claiming more than its cited evidence supports is rejected by an NLI cross-encoder, pinned by revision digest (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli @ 6f5cf0a2`, MIT) | `DECISIONS.md` 001 |
| Measured separation on real weights: a faithful sentence scored 0.9976; an inflated verb 0.0015; a fabricated employer 0.001. Threshold 0.7 | E2E evidence file |
| **The threshold is not yet calibrated between the extremes.** Borderline honest paraphrases can be rejected | `EVAL.md` limits; BLOCKED.md deferral |
| Tailoring selects evidence under a page budget (CP-SAT); every omitted fact carries a typed reason | `tests/test_selector.py`, mutation-checked |
| The renderer does not see the job posting and restates facts faithfully; wording does not shift per job | live failure 2026-08-02: requirement-steering produced gloss ("demonstrating leadership") the gate rejected; recorded in DECISIONS (H8) |
| If the entailment model is unavailable, compilation fails with a typed error; there is no weaker fallback | `test_no_configuration_can_substitute_a_weaker_check` |
| Extraction is span-anchored; a quote that fails to anchor is stored rejected and never matches | `routes.py` extract path, Phase 1 eval |
| Demo data is synthetic; demo sessions are scoped, budgeted, and expire | `tests/test_demo.py` (403/429/401 proven) |
| Uploaded resumes are personal data; demo-tenant rows are deleted within 7 days by prefix-match retention | portfolio-ops retention sweep extended to `demo-` prefix; proven by row count (must land before this claim ships) |

## AI-washing risk register (banned phrases → replacements)

- "AI-powered" → name the mechanism: "an NLI gate scores each sentence against its cited facts"
- "eliminates hallucinations / guarantees truth" → "rejects sentences that claim more than the cited evidence supports; the threshold is 0.7 and not yet calibrated between the measured extremes"
- "intelligent tailoring" → "tailoring is evidence selection under a page budget; wording does not change per job"
- "instant" → state measured timing or nothing (compile took ~30 s in the local E2E)
- Any invented user count, satisfaction number, or logo wall → forbidden; no users are claimed

## Human memory layer

- Wedge: **"A resume compiler with compile errors."** The demo moment is watching your own
  inflated sentence get rejected with the evidence beside it.
- Honest limits stated on the page build trust: do-not-apply verdicts, uncalibrated
  threshold, synthetic demo data labelled as such.

## Not for

- Not a cover-letter writer, not an ATS keyword stuffer, not an interview coach. It will
  tell you not to apply when a must-have requirement has no evidence.
