# API Contracts — CareerCompiler

Doctrine Rule 6: every frontend call maps to exactly one backend endpoint, and this file is checked
against the OpenAPI spec that FastAPI serves at `/openapi.json` (human-readable docs at `/docs`) by
`tests/test_contracts.py`, which CI runs with the rest of the suite. The frontend is deferred to
Phase 2 (Next.js); the "Frontend call (Phase 2)" column names
the UI action that will call each endpoint, so the contract is written before the code that consumes
it.

| Frontend call (Phase 2) | Method | Path | Status | Notes |
|---|---|---|---|---|
| Front page (browser) | GET | `/` | none | Self-contained HTML: thesis, what it measures, the EVAL.md limits sentence, the endpoint list, build stamp. Public by design. |
| Health/liveness probe | GET | `/health` | implemented | Returns `{status, env}`. |
| Load demo Career Fact Graph | GET | `/api/v1/demo` | implemented | Returns `{items:[...]}` from `data/synthetic/`. Development-only; returns 503 outside development (Doctrine Standard 3). |
| API reference (Swagger UI) | GET | `/docs` | implemented | Served by FastAPI. |
| OpenAPI schema | GET | `/openapi.json` | implemented | Served by FastAPI; `tests/test_contracts.py` checks this file against it in CI. |
| Create a candidate (optionally with resume) | POST | `/api/v1/candidates` | implemented | Creates the candidate; stores the resume as a source document when given. Bearer auth when `SMOKE_TEST_TOKEN` set. |
| Enter claims (keyless, self-attested) | POST | `/api/v1/candidates/{id}/claims` | implemented | Explicit data-entry path, flagged self_attested — distinct from document_sourced. |
| Extract atomic claims from the resume (LLM) | POST | `/api/v1/candidates/{id}/claims/extract` | implemented | Key-gated (typed 503 without a key). Span-anchored; failed anchors stored as rejected and never match. |
| Create a job (optionally with requirements) | POST | `/api/v1/jobs` | implemented | Entry-path requirements accepted inline. |
| Parse the JD into requirements (LLM) | POST | `/api/v1/jobs/{id}/requirements/parse` | implemented | Key-gated, schema-forced. |
| Run the fit | POST | `/api/v1/fit` | implemented | Deterministic matcher + persisted Fit Report with the honest apply / do-not-apply verdict. |
| Read a fit report | GET | `/api/v1/fit/{id}` | implemented | Stored report + per-requirement match rows. Bearer auth when `SMOKE_TEST_TOKEN` set. |
| Set a claim's verification state | POST | `/api/v1/facts/{id}/verify` | planned — Phase 2 | Records user verification; unverified claims cannot reach a rendered document (generation era). |
