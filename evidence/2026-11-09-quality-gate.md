# Quality gate

Run 2026-11-09 09:39 UTC at commit `41d77e6` plus uncommitted changes.

**Quality score: 99.75%** (floor 96%). **Verdict: PASS.**

| Coverage | Measured | Floor | |
|---|---|---|---|
| Backend, `app/` line and branch | 99.75% | 96% | pass |
| Frontend, `web/lib/` lowest metric | 100.00% | 96% | pass |

| Check | Result | Detail | Time |
|---|---|---|---|
| backend lint (ruff) | pass | exit 0 | 3s |
| backend tests (pytest) | pass | 232 passed, 0 failed | 99s |
| frontend types (tsc --strict) | pass | exit 0 | 3s |
| frontend lint (eslint) | pass | exit 0 | 5s |
| frontend tests (vitest) | pass | lowest of lines, statements, functions, branches | 3s |
| frontend build (next export) | pass | 4 of 4 pages exported | 25s |
| browser e2e (Chromium, real gates) | pass | 11 passed, 0 failed, 0 skipped | 81s |

The score is the lowest coverage, not an average. Every check must pass and a check that did not run counts as a failure. Logs: `data/local/gate/`.
