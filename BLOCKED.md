# BLOCKED / deferred — needs a decision or scheduled work, with what unblocks it

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
- **Tag v0.3.2 anomaly (2026-08-03)**: a concurrently-running earlier session tagged
  v0.3.2 at 00579ef while this run had already deployed a build self-reporting 0.3.2
  at 82ae595. Superseded by v0.4.0 (51ca391) the same night. Record only — do not move
  published tags.
