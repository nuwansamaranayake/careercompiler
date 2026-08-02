# BLOCKED / deferred — needs a decision or scheduled work, with what unblocks it

- **C4 paraphrase stability** (Jaccard >= 0.85 of matched-requirement sets under JD
  paraphrase): deferred by the 2026-08-03 ship order; unblocked by an eval-script
  extension, no product change.
- **Entailment threshold calibration**: 0.7 sits uncalibrated between measured extremes
  (faithful 0.9976 / inflated 0.0015); needs a labelled borderline set. Stated on the
  landing page and in EVAL.md until done.
- **F1 ATS parse-back gate**: render, parse back, fail on lost name/dates/titles/skills;
  deferred unless the frontend lands green with time to spare (it did not need the spare).
