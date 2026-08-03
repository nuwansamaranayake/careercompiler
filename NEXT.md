# NEXT — single objective for the next pass

**C4 follow-up: decide the paraphrase-stability acceptance on evidence.**

Tonight's measurement (EVAL.md, BLOCKED.md): matched-fact Jaccard under JD paraphrase
is 0.600 (hashing) / 0.833 (openrouter) against the ≥0.85 acceptance, and the drift is
entirely in nice-to-haves; must-have coverage agreed across paraphrases.

Do, in order:
1. Extend `scripts/eval_paraphrase.py`: N=5 paraphrase pairs (not 1), report per-pair
   (a) verdict agreement (apply / do-not-apply), (b) Jaccard over must-have matches
   only, (c) Jaccard over all matches, for both embedders.
2. Machine-checkable pass condition: verdict agreement 5/5 and must-have Jaccard ≥ 0.85
   on the openrouter embedder, measured output committed to EVAL.md.
3. If (2) holds, propose (do not silently apply) re-scoping C4's acceptance to verdict
   stability + must-have Jaccard, with the nice-to-have drift published as a known
   characteristic. If (2) fails, the matcher has a real stability defect: write the
   failing pairs to EVAL.md and stop there for review.

Guardrails unchanged: no gate weakening, no matcher loosening, production stays at
v0.4.0 unless a separate deploy passes the full ritual (snapshot current, estate smoke,
CI-green SHA, docker stats, Beacon GoM untouched).
