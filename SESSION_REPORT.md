# Overnight run report — 2026-08-02/03

Production ends the night at **v0.4.0 (SHA 51ca391)**, two releases ahead of v0.3.1.
No rollback occurred. Beacon GoM untouched all night (5-week uptimes, memory flat,
8.1 GB host headroom). Fresh Hostinger snapshot 107426401 taken 02:35:50Z before the
first deploy. The full product vision works in the browser: upload a resume, paste any
job, get the verdict, and on a match download the targeted resume, the gated cover
letter, and the interview pack. No credentials, no ids shown, no API instructions.

## What shipped, with production evidence

1. **Custom job flow (Obj 1)** — upload → paste posting → parse → fit verdict →
   compile, one continuous flow. Proven in a production browser session:
   `evidence/2026-08-03-obj1-production-walkthrough.txt` (19 facts extracted from an
   uploaded PDF, 4/4 must-haves matched on a pasted JD, 19 gated bullets compiled).
2. **Legible rejections + the root cause fixed (Obj 2)** — rejections now ship with
   the failed quote and render as the anchor check working. The 25.4% rejection rate
   was root-caused to PDF layout artifacts in stored text (measured: "AI-native\n
   systems" vs the model's spaced quote) and fixed at storage; the gate is byte-verbatim
   unchanged. Measured in production: the same failing document went 35/138 (25.4%) →
   0/154 (0.0%). Rates by format in EVAL.md.
3. **Cover letters, gated (Obj 3)** — same pipeline and gates as the resume, letter
   voice, deterministic job-referential frame. **Pass condition met in production**: a
   planted overstatement in a letter sentence failed the compile with
   `unsupported_number`, evidence beside it.
   `evidence/2026-08-03-obj345-production-walkthrough.txt`.
4. **Interview pack (Obj 4)** — gate-survivors only; deterministic story/metrics/gaps
   with the case-against; model writes only the skeptical questions; docx download.
   Live in production (15 questions, 5 metrics lines in the walkthrough).
5. **Tailoring position stated (Obj 5)** — beside every compiled page in production;
   DECISION 004 carries the live failure and now the letter exception.
6. **Deferred items (Obj 6)** — threshold calibration DONE (graded suite, curve
   published, choice: keep 0.7 — a raise would false-reject honest letters measured at
   0.79–0.83). C4 paraphrase stability MEASURED and published as a FAIL (below).

## Blocked / deferred (one line each — full detail in BLOCKED.md)

- C4 paraphrase stability: measured 0.600 (hashing) / 0.833 (openrouter) vs ≥0.85 —
  unblocked by verdict-stability measurement + must/nice stratification, then an
  acceptance-metric decision. Deliberately not tuned to pass.
- F1 ATS parse-back gate: untouched, still deferred.
- Letter-voice graded suite: needed before any per-kind entailment threshold.

## Defects found tonight, and their state

- CI DuplicateColumn on fresh DBs (migration 0004 vs 0003's live-metadata create_all):
  FIXED with an existence guard; both paths proven on a throwaway postgres.
- Tenant scope prefix leaked into letter openings: FIXED (`_display`), regression test.
- Interview-pack docx returned 200 instead of 201: FIXED at the Response.
- cc-test image was stale (groundwork v0.1.0): environment fixed, invocation recorded.
- Test suite requires `WEB_DIR=/nonexistent` now that images bake /srv/web: recorded in
  LOOP_STATE (environment fact, not a code defect).
- NLI blind spots published in EVAL.md: requirement-flavored gloss at 0.9785 and a
  quantifier inversion at 0.9463 both survive 0.7 — known, published, unfixed.

## Version anomaly (cosmetic, recorded)

A concurrently-running earlier session pushed 00579ef and tagged v0.3.2 at it (21:32
CDT) while this run's Deploy 1 shipped a build self-reporting 0.3.2 at 82ae595. That
session went idle 21:46 CDT. Resolution: tag left untouched, Deploy 2 shipped as
v0.4.0 on 51ca391 (CI-green, watched to success), which is what production now runs
and reports. Detail in BLOCKED.md.

## Measured rejection rates by input format

See the EVAL.md table: real-world PDF pre-fix 25.4%; same content through normalized
storage 0.0%; clean single-column PDF 0.0%; identical-content docx 0.0% (all post-fix
rows measured against production v0.4.0 with real models).

## Next objective

Already in NEXT.md: C4 follow-up — measure verdict stability under paraphrase,
stratify Jaccard by must-have vs nice-to-have, then decide the acceptance metric.
