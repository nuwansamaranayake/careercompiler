# EVAL — CareerCompiler

## What good means

CareerCompiler is judged on one non-negotiable property and four supporting ones. The
non-negotiable: **no unsupported claim survives to a rendered document.** Fabrication is not a
quality slider here; it is a build failure, and the eval proves the gate actually fails builds. The
supporting properties keep the honest analyzer honest under real-world messiness — reworded JDs,
different phrasings of the same evidence, and machine parsers on the far side of a render.

## Status

`make eval` runs `scripts/eval.py`, which currently raises `NotImplementedError("eval harness lands
in Phase 1")` **on purpose**. Per the AiGNITE doctrine, a harness that cannot yet measure must fail
loud, never pass vacuously. The thresholds below are the acceptance targets the Phase-1 harness will
enforce — goals, not achieved measurements. Each release will publish its eval report once the
harness is wired.

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
