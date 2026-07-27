# Changelog

All notable changes to CareerCompiler are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- `.dockerignore` added: `COPY . .` no longer bakes `.env` (a live OpenRouter key), `.git`
  history, or local state into the image — `.gitignore` never protected the Docker build
  context (adversarial review F1; FAIL-0004).
- `GET /api/v1/fit/{id}` now requires the bearer token when `SMOKE_TEST_TOKEN` is set,
  matching the mutation endpoints; stored fit reports (including resume-derived claim
  statements) were readable anonymously via enumerable integer ids (F2).

### Fixed
- LLM calls in `claims/extract` and `requirements/parse` now run outside any DB
  session/transaction (read, close, call, then write in a fresh session), and the gateway
  client is bounded by `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` — previously the OpenAI SDK
  defaults (600s timeout, 2 retries) could pin the connection pool from inside an open
  transaction, and the `.env.example` timeout knob was read by nothing (F4).
- `POST /api/v1/fit` with `embedder=openrouter` but no key/model set returns a typed 503
  with actionable detail instead of an untyped 500 (F5).
- `scripts/check_migrations.py` fails loud when `EXPECTED_TABLE_COUNT` is unset instead of
  silently skipping the assertion while still printing `MIGRATION OK` (F7).
- contracts.md's claimed CI enforcement now exists: `tests/test_contracts.py` checks every
  implemented row against the served OpenAPI spec in both directions (F8).
- README truth pass: the entailment gate is labeled Phase 2 in "What it is" (matching the
  status banner and ROADMAP), and the quickstart starts and migrates Postgres — with the
  `.env.example` smoke token — before promising `SMOKE OK` (F9, F10).

## [0.2.0] - 2026-07-23

### Added — Phase 1 honest analyzer
- Span-anchored atomic claims on the groundwork Claim spine; failed anchors stored as
  rejected and excluded from matching. Self-attested entry path flagged distinctly.
- JD parser (schema-forced) with keyless entry path; deterministic matcher (generic tokens
  cannot carry a direct match; transferable never presented as direct); Fit Report with the
  honest do-not-apply verdict and the case against applying.
- Golden analyzer eval enforcing pre-written bounds; observed all PASS at 1.0 after the
  suite's first run caught two real matcher defects (FAIL-0002). Byte-reproducible.
- Persisted candidate/claims/jobs/fit API with bearer auth; alembic 0002 (MIGRATION OK: 8
  tables observed); CLI fit that exits nonzero on do-not-apply; container migrates and
  asserts count before serving.
- Flywheel: Seismograph contract for the extraction stage, validated against Seismograph's
  DSL; key-gated LLM eval observed recall 1.00, paraphrase jaccard 0.92 on canonical fact
  anchors (FAIL-0003: extraction model swapped to google/gemini-2.5-flash after qwen
  ignored the strict schema it advertised).

### Changed
- CI eval job is now REQUIRED ("eval (required)").
- Smoke exercises the full keyless business loop, not just health + fixture.

### Changed
- Dependency on `aignite-groundwork` switched from an editable path source to a pinned git
  dependency (`git+https://github.com/nuwansamaranayake/groundwork@v0.1.0`) so standalone clones and CI resolve
  it without a sibling checkout. PyPI publication planned at first release.
- `scripts/check_migrations.py` now uses `DATABASE_URL` with the declared psycopg v3 driver
  unmodified, fixing a clean-machine `make migrate` failure (see FAILURES.md FAIL-0002).
- README truth pass: scaffold status block, `(the design)` heading, "What exists today (verified)"
  section, scoped/dated novelty, dual-path Quickstart, em-dash sweep.
- CI: Python matrix (3.12, 3.13); eval job labeled "eval (Phase 1 pending)".

### Added
- `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1) and a SECURITY.md vulnerability-reporting policy.

## [0.1.0] - 2026-07-21
### Added
- Engineering harness scaffold: governed doc set, config guard, verification gates,
  smoke test against a real business endpoint, migration-count check, CI pipeline,
  and a synthetic dataset so the demo runs with zero external keys.
