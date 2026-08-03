# LOOP_STATE — repair-loop + real-corpus run, 2026-08-03 (second night)

Resuming: NEXT.md, then this file. Environment facts: git history of this file (the
2026-08-02 overnight entry) — WEB_DIR=/nonexistent for tests, estate smoke from this
machine via --ssh, compose.prod.yml with CLI build args, cwd discipline: background
Bash inherits the LAST foreground cwd — use absolute paths (bit twice tonight).

## This run so far

- FAIL-0010 diagnosed with evidence (40% vs 40 token classes + no-feedback re-draft)
  and fixed: repair loop (cap 3, audited, gates issue every verdict) + numeral
  pre-check. Before/after on 20 seeded compiles: 1/20 -> 0/20 (EVAL.md).
- FAIL-0011 (name-subject facts vs first-person letters, 0.018) caught by the NEW
  demo-path gate pre-deploy; extraction now demands bare predicates.
- FAIL-0012 (hashing embedder over-matching: WCAG "matched" a C# fact at 0.49) caught
  by the real-corpus run; embedder `auto` default, resolved name never silent.
- Adversarial review (26 agents): gate lens CLEAN; 9 confirmed findings all fixed
  (index-keyed revisions + regression test, honest attempt counts, typed 503 details,
  provenance steps in the gate, estate subprocess hardening, corpus checkpointing).
- Estate pre-deploy: 5/6 PASS; careercompiler FAILS on the new demo-path gate against
  v0.4.0 production — the disease being cured; post-deploy run must exit 0.
- Snapshot 107469778 success 06:15:45Z. CI green b0cb7bb; final SHA 3286509 in CI now.
  portfolio-ops b366c7c pushed. Host careercompiler at b0cb7bb (needs final pull).

## Next

1. Battery green (local demo-path + corpus on auto embedder) + CI green on 3286509.
2. Host: pull 3286509, build v0.4.1 args, up. 3. Post-deploy: estate exit 0 (incl.
demo-path), 20-compile production run, production corpus record, docker stats, tag
v0.4.1@3286509. 4. EVAL.md corpus aggregates + SESSION_REPORT + NEXT.
