# EVAL — CareerCompiler

## What good means

CareerCompiler is judged on one non-negotiable property and four supporting ones. The
non-negotiable: **no unsupported claim survives to a rendered document.** Fabrication is not a
quality slider here; it is a build failure, and the eval proves the gate actually fails builds. The
supporting properties keep the honest analyzer honest under real-world messiness — reworded JDs,
different phrasings of the same evidence, and machine parsers on the far side of a render.

## Published limits

This sentence is what the root page publishes, verbatim. The gate fails if the page and this block drift apart.

<!-- LIMITS -->
On a golden suite of 4 labelled job cases against a 6-fact synthetic career graph, the analyzer places every requirement in the right bucket (matcher accuracy 1.0), returns the correct apply or do-not-apply verdict on every case including planted disqualifying gaps (1.0), never presents transferable evidence as direct (0 violations), and holds its verdict across pre-authored paraphrases of the job description (1.0); the suite is synthetic and small, so it does not measure performance on real resumes or real postings. The Phase 2 compiler rejects a sentence that claims more than its cited evidence supports: on the pinned entailment model a faithful sentence scored 0.9976 and an inflated verb 0.0015, but the 0.7 threshold is not yet calibrated between those extremes, so a borderline honest paraphrase can be rejected; compile-time rejection is measured, fabrication recall in the wild is not.
<!-- /LIMITS -->


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

## The render repair loop, before and after (measured 2026-08-03, FAIL-0010)

20 compiles of the seeded candidate (10 per seeded job), local stack,
production-identical models, same script both runs:

| | failed | rate | failing check |
|---|---|---|---|
| before the repair loop | 1/20 | 5% | entailment — "over 6 years" vs "for 6 years", 0.52 |
| after the repair loop | 0/20 | 0% | — |

In the after-sample every draft was clean on round 1 (the loop never fired), so the
0% alone does not prove the loop — the demo-path gate run does: its compile engaged
one repair round and shipped, and its cover letter exhausted three audited rounds and
was honestly refused, which exposed FAIL-0011 (name-subject facts) before any deploy.
The loop's mechanics are pinned by seven tests (repairable drafts ship repaired;
exhaustion returns the unchanged gates' verdict with the audit log; the round cap
holds; the letter path runs the same loop). The gates are byte-identical: the
planted-negative suites run unmodified and green, in CI and in production (estate G2).

## Span-anchor rejection rates by input format (measured in production, 2026-08-03)

The 2026-08-02 live run rejected 35 of 138 extracted facts on span anchoring from one
real resume. Root cause, measured (not assumed): the stored PDF text hard-wrapped
sentences at layout line breaks ("AI-native\nsystems in production") and doubled spaces
at layout gaps; the model quoted with normal spacing; the byte-verbatim find failed.
The fix normalizes what is stored — the anchor check itself is unchanged.

| input | storage | rejected | rate |
|---|---|---|---|
| real-world resume PDF (candidate 31) | pre-fix (raw pypdf text) | 35/138 | 25.4% |
| the same text, re-run through normalized storage | post-fix | 0/154 | 0.0% |
| clean single-column PDF (riley pair) | post-fix | 0/19 | 0.0% |
| identical content as docx (riley pair) | post-fix | 0/19 | 0.0% |

All post-fix rows measured against production (v0.4.0) through the real API with the
real extraction model. Rejections that do occur now ship with their evidence: the
claim, and the quote that could not be located, rendered in the product as the anchor
check working. (Counts differ across runs — the extraction model is not deterministic;
rates are the measure.)

## C4 paraphrase stability (measured 2026-08-03, acceptance NOT met — published)

Two JDs describing the identical role in different words, real parse, deterministic
matcher, fixed 6-fact set. Metric: Jaccard of matched-FACT sets (req keys are
model-chosen labels; comparing them would measure spelling).

| embedder | Jaccard | acceptance |
|---|---|---|
| hashing (keyless default) | 0.600 | >= 0.85 — FAIL |
| openrouter (text-embedding-3-small) | 0.833 | >= 0.85 — FAIL, by one fact |

The measured failure mode: paraphrase changes which nice-to-haves the parse emits and
the matcher resolves (JD B's "Bonus: experience leading engineers" matched the
leadership fact; JD A's "Nice to have: team leadership" did not reach it under hashing).
Must-have coverage — what drives the verdict — agreed across paraphrases in both runs.
Next measurement, not tuning: verdict stability under paraphrase, and Jaccard stratified
must-have vs nice-to-have. `scripts/eval_paraphrase.py`.

## Entailment threshold calibration (graded suite, 2026-08-03)

The 0.7 threshold sat uncalibrated between measured extremes (faithful 0.9976, inflated
0.0015). `scripts/eval_threshold.py` grades the space between against the pinned NLI
(`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli @ 6f5cf0a2`), 24 cases in six categories.

Measured: every faithful restatement and every weakening hedge scored ≥ 0.97; 15 of 17
planted violations scored ≤ 0.57 (most ≤ 0.10). The curve at candidate thresholds —
false accepts are should-reject cases surviving, false rejects are honest cases killed:

| threshold | false accepts | false rejects |
|---|---|---|
| 0.50 | 3 | 0 |
| 0.70 (current) | 2 | 0 |
| 0.95 | 1 | 0 |

**The choice, from the curve: keep 0.7.** Raising to 0.95 looks free on this suite, but
production letter-voice sentences measured 0.79–0.83 while faithful (local E2E,
2026-08-03) — a 0.95 gate would false-reject honest cover letters. A per-document-kind
threshold needs a letter-voice suite before it is anything but a guess.

**The published misses at 0.7 — claims this gate does not catch:**
- "Transformed engineering velocity by rebuilding the CI pipeline" scored 0.9785 against
  "Cut deploy time 40% by rebuilding the CI pipeline in Python" — requirement-flavored
  gloss without a checkable number. (This is why the renderer never sees requirements:
  the prompt discipline prevents what this gate would miss.)
- "Led 4 engineering teams at Acme Corp" scored 0.9463 against "Led a team of 4
  engineers at Acme Corp" — a quantifier inversion the linker's number check also
  passes, since the 4 is copied faithfully. Known hole, published, unfixed.

## Status

The harness is real as of Phase 1: `scripts/eval.py` enforces the table above (first
published run 2026-07-23, all bounds PASS at 1.0, byte-reproducible — `eval_report.md`),
and its first run caught two real matcher defects before they reached a verdict
(FAILURES.md FAIL-0002). The key-gated extraction section (`scripts/eval_llm.py`) observed
planted-fact recall 1.00 and paraphrase jaccard 0.92 on canonical anchors
(`eval_report_llm.md`). The CI eval job is required.

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
