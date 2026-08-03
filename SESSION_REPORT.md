# Run report — 2026-08-03, repair loop + real-corpus proof

Production ends at **v0.4.1 (SHA 4720c19, tagged, CI run 30793954540 green on that
exact SHA)**. No rollback occurred; the one mid-deploy failure was caught by the new
release gate, forward-fixed under a bounded budget, and re-verified. Beacon GoM
untouched all night (5–6 week uptimes, memory flat, 8 GB host headroom). Snapshot
107469778 taken before the first cutover. Nothing private is committed — proven with
`git check-ignore` and a clean `git status` at every commit.

## The definition of done, item by item

- **Twenty consecutive seeded compiles without a visible gate failure:** 20/20 in
  production (0% fail), `scratchpad/prod_20.jsonl`; before/after for the fix that got
  us here: 1/20 → 0/20 locally (EVAL.md). The demo "Compile again" dead-end is gone —
  the flow repairs itself and a post-repair refusal names the sentence, the facts it
  reached for, and why.
- **Real resume against every posting:** 6/6 pairings compile end to end (resume,
  cover letter, interview pack) with the repair loop engaging one audited round per
  pairing; verdicts 6/6 correct after the matcher calibration (two hard-mismatch
  postings correctly refuse; production corpus record in fixtures/private/, aggregates
  in EVAL.md).
- **The gate no more permissive, proven:** planted inflated sentence and planted
  invented number both REJECTED in production during the release gate (estate G2);
  the adversarial review's gate-integrity lens returned zero findings; the planted-
  negative test suites run unmodified.
- **Nothing private committed:** fixtures/private/ gitignored before anything was
  copied; the corpus runner prints aggregates only.

## What was diagnosed and fixed (each with its FAILURES.md entry)

- **FAIL-0010** — the reported `40` failure: `40%` licenses only `40%`, the renderer
  re-drafted blind at temperature 0, and the UI handed the retry to the user. Fixed by
  the repair loop (rejection reasons fed back, cap 3, fully audited, gates issue every
  verdict) + a deterministic numeral pre-check reusing the linker's own arithmetic.
- **FAIL-0011** — name-subject facts made honest first-person letters unentailable
  (0.018): extraction now writes bare predicates. Caught by the new gate, pre-deploy.
- **FAIL-0012** — the keyless embedder default over-matched must-haves (WCAG "matched"
  a C# fact at 0.49): embedder `auto` (resolved name never silent) + category-noun
  guard + per-embedder floors calibrated from a 35-row labeled curve and verified by
  re-fit (nurse and design-systems postings flip to do-not-apply; all true applies
  hold). Two published misses remain inside the TP band (EVAL.md); requirement-type-
  aware matching is the named follow-up.
- **FAIL-0013** — verbless fact statements ("Kubernetes in production") support no
  sentence: caught by the release gate ON the first v0.4.1 cutover, blocked the
  release, forward-fixed (verb-initial statements), re-verified twice locally and by
  the estate gate in production.
- Plus nine confirmed findings from a 26-agent adversarial review (index-keyed
  revisions, honest attempt counts, typed 503s, provenance steps in the gate, estate
  subprocess hardening, corpus checkpointing) — all fixed same night.

## The demo-path release gate (Part 6)

`scripts/demo_path_smoke.py` walks the exact visitor sequence with synthetic fixtures
against production and is wired into the portfolio-ops estate smoke: it BLOCKED one
release tonight (FAIL-0013) and then passed exit-0 as the last thing run after the
final deploy. It consumes a demo session per run — more than 5 estate runs/hour from
one IP will 429 (operator decision logged in BLOCKED.md).

## Blocked / operator decisions (BLOCKED.md has full detail)

- Requirement-type-aware matching for the two published matcher misses.
- Estate runs vs the 10/hour demo-session limit.
- beacon-gom's portfolio-ops checkout diverges locally (+191/−53) — pull aborts;
  discarding host edits is forbidden; estate runs from the workstation meanwhile.

## Version anomaly follow-through (Part 8)

`00579ef` (tagged v0.3.2) IS an ancestor of production — verified with
`git merge-base --is-ancestor`; the tag stays. README status block now names v0.4.x.
