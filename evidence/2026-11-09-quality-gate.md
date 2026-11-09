# Quality gate

Run 2026-11-09 10:13 UTC at commit `6abe30e`.

**Quality score: 99.75%** (floor 96%). **Verdict: PASS.**

| Coverage | Measured | Floor | |
|---|---|---|---|
| Backend, `app/` line and branch | 99.75% | 96% | pass |
| Frontend, `web/lib/` lowest metric | 100.00% | 96% | pass |

| Check | Result | Detail | Time |
|---|---|---|---|
| backend lint (ruff) | pass | exit 0 | 3s |
| backend tests (pytest) | pass | 253 passed, 0 failed | 121s |
| frontend types (tsc --strict) | pass | exit 0 | 3s |
| frontend lint (eslint) | pass | exit 0 | 5s |
| frontend tests (vitest) | pass | lowest of lines, statements, functions, branches | 2s |
| frontend build (next export) | pass | 4 of 4 pages exported | 26s |
| browser e2e (Chromium, real gates) | pass | 12 passed, 0 failed, 0 skipped | 118s |

The score is the lowest coverage, not an average. Every check must pass and a check that did not run counts as a failure. Logs: `data/local/gate/`.

Backend code not covered: `app/engine/facts.py`: branches 79->exit; `app/engine/jd.py`: branches 57->exit; `app/engine/selector.py`: lines 168, branches 167->168; `app/routes.py`: branches 588->620.
