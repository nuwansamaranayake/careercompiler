# Quality gate

Run 2026-11-09 16:49 UTC at commit `59215a4` plus uncommitted changes.

**Quality score: 99.75%** (floor 96%). **Verdict: PASS.**

| Coverage | Measured | Floor | |
|---|---|---|---|
| Backend, `app/` line and branch | 99.75% | 96% | pass |
| Frontend, `web/lib/` lowest metric | 100.00% | 96% | pass |

| Check | Result | Detail | Time |
|---|---|---|---|
| backend lint (ruff) | pass | exit 0 | 2s |
| backend tests (pytest) | pass | 254 passed, 0 failed | 180s |
| frontend types (tsc --strict) | pass | exit 0 | 9s |
| frontend lint (eslint) | pass | exit 0 | 10s |
| frontend tests (vitest) | pass | lowest of lines, statements, functions, branches | 3s |
| frontend build (next export) | pass | 4 of 4 pages exported | 36s |
| browser e2e (Chromium, real gates) | pass | 12 passed, 0 failed, 0 skipped | 91s |

The score is the lowest coverage, not an average. Every check must pass and a check that did not run counts as a failure. Logs: `data/local/gate/`.

Backend code not covered: `app/engine/facts.py`: branches 79->exit; `app/engine/jd.py`: branches 57->exit; `app/engine/selector.py`: lines 168, branches 167->168; `app/routes.py`: branches 588->620.
