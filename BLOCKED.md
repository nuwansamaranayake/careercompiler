# BLOCKED / deferred — needs a decision or scheduled work, with what unblocks it

- **DIRECT_SIM calibration for real embeddings (FAIL-0012 follow-up, 2026-08-03):**
  the 0.55 direct-match floor was tuned on the hashing embedder; measured tonight,
  real embeddings score six UNRELATED requirement/fact pairs at 0.62–0.86 (WCAG cert ↔
  AI certification 0.769, CSS-in-JS ↔ RAG architecture 0.621, React Native ↔ React
  0.859), so a hard-mismatch posting can read apply. A pure threshold cannot separate
  React-Native↔React (0.859) from true positives (0.85–0.95): the calibration needs a
  labeled near-neighbor suite (same discipline as the entailment threshold), likely
  per-embedder floors plus a specific-token requirement for certification/years-type
  must-haves. The six measured pairs are the seed set. Not dial-twisted overnight.

- **Estate runs consume 2 of the 10/hour per-IP demo sessions (review finding,
  2026-08-03):** loop_careercompiler's B5 check opens one demo session and the
  demo-path gate opens another, so more than 5 estate runs from one IP in an hour
  false-fails careercompiler with 429. Tonight's cadence never exceeds 3. Unblocked
  by an operator decision: reuse one session across both checks, or let the estate
  bearer mint sessions exempt from the per-IP limit. Not band-aided overnight.
- **beacon-gom's portfolio-ops checkout has local modifications (2026-08-03):**
  `scripts/estate_smoke.py` diverges from origin by +191/−53 (an old hot-patch), plus
  untracked `scripts/retention.py` / `scripts/retention_drill.py` (content-identical to
  what origin now tracks) and an `evidence/` directory. `git pull` on the host aborts.
  Discarding host modifications is a forbidden operation, and nothing requires the
  host copy: the estate gate runs from the workstation via --ssh. Unblocked by the
  operator reviewing the host diff and choosing keep/stash/reset.

- **C4 paraphrase stability — measured, acceptance NOT met (2026-08-03).** Jaccard of
  matched-fact sets under JD paraphrase: 0.600 (hashing embedder), 0.833 (openrouter
  embedder) against the >= 0.85 acceptance. Failure mode identified and published in
  EVAL.md: paraphrase shifts which nice-to-haves the parse emits; must-have coverage
  agreed in both runs. Unblocked by: verdict-stability measurement and must-have vs
  nice-to-have stratification (`scripts/eval_paraphrase.py`), then a decision on
  whether the acceptance metric should be verdict stability rather than raw Jaccard.
  Deliberately not tuned to pass overnight.
- **F1 ATS parse-back gate**: render, parse back, fail on lost name/dates/titles/skills;
  still deferred — nothing tonight touched rendering structure.
- **Entailment threshold calibration**: RESOLVED 2026-08-03 — graded suite built and run
  (`scripts/eval_threshold.py`), curve published in EVAL.md, choice: keep 0.7
  (letter-voice faithfuls measure 0.79–0.83; a raise would false-reject honest letters).
  Two 0.7 misses published. Remaining follow-up: a letter-voice graded suite before any
  per-kind threshold.
- **Tag v0.3.2 anomaly (2026-08-03) — CLOSED**: a concurrently-running earlier session
  tagged v0.3.2 at 00579ef while this run had already deployed a build self-reporting
  0.3.2 at 82ae595. Ancestry verified 2026-08-03 (repair-loop run):
  `git merge-base --is-ancestor 00579ef 51ca391` → true, so the tagged groundwork
  refactor IS contained in production v0.4.0. The tag stays; nothing points at code
  that never shipped.
