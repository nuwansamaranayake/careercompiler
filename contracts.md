# API Contracts — CareerCompiler

Doctrine Rule 6: every frontend call maps to exactly one backend endpoint, and this file is checked
in CI against the OpenAPI spec that FastAPI serves at `/openapi.json` (human-readable docs at
`/docs`). The frontend is deferred to Phase 2 (Next.js); the "Frontend call (Phase 2)" column names
the UI action that will call each endpoint, so the contract is written before the code that consumes
it.

| Frontend call (Phase 2) | Method | Path | Status | Notes |
|---|---|---|---|---|
| Health/liveness probe | GET | `/health` | implemented | Returns `{status, env}`. |
| Load demo Career Fact Graph | GET | `/api/v1/demo` | implemented | Returns `{items:[...]}` from `data/synthetic/`. Development-only; returns 503 outside development (Doctrine Standard 3). |
| API reference (Swagger UI) | GET | `/docs` | implemented | Served by FastAPI. |
| OpenAPI schema | GET | `/openapi.json` | implemented | Served by FastAPI; CI diffs this file against it. |
| Upload existing resume as a source document | POST | `/api/v1/candidates/{id}/sources` | planned — Phase 1 | Stores the raw source for span-anchored extraction. |
| Extract atomic claims from a source | POST | `/api/v1/fact-graph/extract` | planned — Phase 1 | LLM decomposes bullets into typed, span-anchored claims with provenance. |
| View the Career Fact Graph | GET | `/api/v1/candidates/{id}/facts` | planned — Phase 1 | Lists atomic claims with confidence and verification state. |
| Parse a job description into requirements | POST | `/api/v1/job-postings/parse` | planned — Phase 1 | Schema-forced parse into typed requirements. |
| Generate the Fit Report | POST | `/api/v1/fit-report` | planned — Phase 1 | Deterministic matcher scores requirements: matched / transferable / gap, plus apply-or-not. |
| Set a claim's verification state | POST | `/api/v1/facts/{id}/verify` | planned — Phase 1 | Records user verification; unverified claims cannot reach a rendered document. |
