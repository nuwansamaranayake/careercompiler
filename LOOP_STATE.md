# LOOP_STATE — repair-loop + real-corpus run CLOSED, 2026-08-03

Production: **v0.4.1, SHA 4720c19, tag pushed with CI run URL 30793954540.** Estate
smoke exit 0 including the demo-path release gate; 20/20 production compiles; corpus
verdicts 6/6 correct. SESSION_REPORT.md is the authoritative record of this run;
NEXT.md carries the single next objective (requirement-type-aware matching).

## Environment facts (carry forward)

- Tests: `docker run --rm -e WEB_DIR=/nonexistent -v "E:/AiGNITE/AiPortifolio/careercompiler:/src" -w /src cc-test python -m pytest tests/ -q`
  (rebuild cc-test from careercompiler-service:latest + pytest/ruff after engine deps change).
- Estate gate: `python portfolio-ops/scripts/estate_smoke.py --ssh beacon-gom` from this
  machine. Now INCLUDES the careercompiler demo-path walk (~2 min, one demo session).
- Deploy: host pull → `docker compose -f compose.prod.yml build --build-arg APP_VERSION=…
  --build-arg GIT_SHA=… service` → `up -d service`. Entrypoint migrates + asserts 11 tables.
- Background Bash inherits the LAST foreground cwd — ALWAYS absolute paths (bit three
  times on 2026-08-03: a battery ran against portfolio-ops, a push never ran, a docker
  build found no Dockerfile).
- Demo-session rate limit: 10/hour/IP; each estate run consumes 2 (BLOCKED.md).
- fixtures/private/ is gitignored and holds the real corpus + per-pairing records;
  corpus tenants use the smoke- prefix so retention sweeps them at 7 days.
- Extraction phrasing is model-nondeterministic: the demo-path gate is the recurrence
  detector for FAIL-0011/0013-class regressions — it runs on every estate invocation.

## Open items (full detail in BLOCKED.md / NEXT.md)

1. Requirement-type-aware matching (NEXT.md) — the two published matcher misses.
2. Estate-vs-rate-limit operator decision. 3. Host portfolio-ops checkout divergence.
4. F1 ATS parse-back gate (long-deferred). 5. Letter-voice graded entailment suite.
