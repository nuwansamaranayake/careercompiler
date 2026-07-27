# EVAL — CareerCompiler

## What good means

CareerCompiler is judged on one non-negotiable property and four supporting ones. The
non-negotiable: **no unsupported claim survives to a rendered document.** Fabrication is not a
quality slider here; it is a build failure, and the eval proves the gate actually fails builds. The
supporting properties keep the honest analyzer honest under real-world messiness — reworded JDs,
different phrasings of the same evidence, and machine parsers on the far side of a render.

## Phase 1 acceptance thresholds (written before the harness, 2026-07-23)

Phase 1 ships the honest analyzer (extraction, JD parsing, matcher, Fit Report — no
generation), so its bounds measure the analyzer. The suite is deterministic and keyless:
golden synthetic fact graphs and labeled JDs with planted matches, planted disqualifying
gaps, and pre-authored JD paraphrase sets; the deterministic HashingEmbedder keeps it
byte-reproducible as a required CI check. `scripts/eval.py` exits nonzero on any miss.

| Metric | Definition | Bound |
|---|---|---|
| Matcher accuracy | requirement rows scored matched/partial/gap agreeing with golden labels | >= 0.90 |
| Verdict correctness | apply / do-not-apply agreeing with golden labels (incl. every planted disqualifying gap) | = 1.00 |
| Transferable honesty | transferable evidence presented as a direct match | 0 violations |
| Paraphrase invariance | verdict unchanged across each pre-authored JD paraphrase set | = 1.00 |
| Match-set stability | Jaccard of matched-requirement sets across a paraphrase set | >= 0.85 |
| Reproducibility | two consecutive `make eval` runs | identical reports |

Extraction quality (LLM stage) is measured separately and key-gated — planted-fact recall on
synthetic resumes through the real gateway, plus the Seismograph paraphrase-invariance
contract in `contracts/` — reported when a key is present, never a required keyless check,
and never silently skipped: the report states loudly when the key-gated section did not run.
The gate-test, selection-stability, ATS, and human-preference bounds below join in Phase 2/3
with the code they measure.

## Status

`scripts/eval.py` currently raises `NotImplementedError("eval harness lands in Phase 1")`
**on purpose**; the real harness enforcing the table above lands in Phase 1 milestone M6
(see LOOP_STATE.md), and the CI eval job becomes required in M9.

## How `make eval` will measure it

Mapped to the blueprint's evaluation section:

- **Fabrication rate — the gate test.** A held-out entailment model audits generated sentences
  against their cited facts. We plant known violations (a stronger verb, a new number, a new
  employer) and assert the linker catches every one. **Target: zero unsupported claims survive the
  gate.**
- **Fit Report paraphrase invariance.** Feed semantically equivalent rewrites of the same JD; the
  matched / partial / gap verdict and the apply-or-not decision must not swing. **Target: verdict
  stable across paraphrase sets.**
- **Selection stability under JD paraphrase.** The knapsack selector must pick substantially the same
  evidence for equivalent JDs. **Target: high selection overlap across paraphrases.**
- **ATS parse-back survival.** Render to docx/pdf, parse back with an open-source ATS-style parser,
  and confirm name, dates, titles, and skills survive. **Target: 100% survival.**
- **Blind human preference.** On identical inputs, blind reviewers compare CareerCompiler output
  against a leading commercial tool. **Target: preferred at parity or better, without inflation.**

Red-team prompt-injection cases (a source resume or JD carrying instructions) ship in the same suite;
the gate and the input-channel separation must hold. The eval report publishes with every release.
