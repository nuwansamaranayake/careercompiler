# API Contracts — CareerCompiler

Doctrine Rule 6: every frontend call maps to exactly one backend endpoint.

**Derivation rule: this table is derived from the served `/openapi.json`, never from the
router source.** Router decorators are pre-prefix declarations (`APIRouter(prefix="/api/v1")`
applies at mount), so the source file shows paths a client cannot call. Verified from outside
on 2026-08-02: `POST /api/v1/candidates/{cid}/claims/extract` → 401 unauthenticated, the same
path without the prefix → 404. `tests/test_contracts.py` enforces this table against the
schema **literally** — path parameter spellings included — in both directions, and asserts
every planned row is not yet served.

| Frontend call (Phase 2) | Method | Path | Status | Notes |
|---|---|---|---|---|
| Front page (browser) | GET | `/` | implemented (not in schema) | Self-contained HTML; deliberately `include_in_schema=False`, so no gate may enumerate it from the schema. Public by design. |
| Health/liveness probe | GET | `/health` | implemented | Returns `{status, env}`. |
| API reference (Swagger UI) | GET | `/docs` | implemented (not in schema) | Served by FastAPI. Public by decision (DECISIONS 002 in portfolio-ops). |
| OpenAPI schema | GET | `/openapi.json` | implemented (not in schema) | Served by FastAPI; this file is checked against it in CI. |
| Load demo fixture | GET | `/api/v1/demo` | implemented | Development-only; 503 outside development (Standard 3). |
| Create a candidate (optionally with resume) | POST | `/api/v1/candidates` | implemented | Stores the resume as a source document when given. Bearer auth when `SMOKE_TEST_TOKEN` set. |
| Enter claims (keyless, self-attested) | POST | `/api/v1/candidates/{cid}/claims` | implemented | Explicit data-entry path, flagged `self_attested`. |
| Extract atomic claims from the resume (LLM) | POST | `/api/v1/candidates/{cid}/claims/extract` | implemented | Key-gated (typed 503 without a key). Span-anchored; failed anchors stored as rejected and never match. |
| Create a job (optionally with requirements) | POST | `/api/v1/jobs` | implemented | Entry-path requirements accepted inline. |
| Parse the JD into requirements (LLM) | POST | `/api/v1/jobs/{jid}/requirements/parse` | implemented | Key-gated, schema-forced. |
| Run the fit | POST | `/api/v1/fit` | implemented | Deterministic matcher + persisted Fit Report with the honest apply / do-not-apply verdict. |
| Read a fit report | GET | `/api/v1/fit/{rid}` | implemented | Stored report + per-requirement match rows. Bearer auth when `SMOKE_TEST_TOKEN` set. |
| Set a claim's verification state | POST | `/api/v1/facts/{claim_id}/verify` | planned — Phase 2 | Records human verification on one atomic claim. Humans approve; the model never does. |
| Compile a resume (select → render → gate) | POST | `/api/v1/compile` | planned — Phase 2 | Selector chooses under the budget, LLM phrases, linker and entailment gate reject anything stronger than its evidence. Persists only documents that passed both gates. |
| Read a compiled document + provenance map | GET | `/api/v1/compile/{did}` | planned — Phase 2 | Bullets with cited fact ids resolved to statements, entailment scores, and every omission with its typed reason. |
| Download the compiled docx | GET | `/api/v1/compile/{did}/docx` | planned — Phase 2 | python-docx output with a provenance appendix; every sentence traces to a fact. |
| Live-check an edited bullet (the rejection moment) | POST | `/api/v1/compile/check` | planned — Phase 2 | Runs linker + entailment on one edited sentence against its cited facts; returns violations, never persists. The E2 centerpiece. |
| Open a demo session | POST | `/api/v1/demo/session` | planned — Phase 2 | Issues a scoped, short-lived, rate-limited bearer token bound to a demo tenant. Business reads stay bearer-authenticated. |
