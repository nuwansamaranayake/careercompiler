# Failure Gallery — CareerCompiler

An honest record of things that broke, why, and what changed. A curated gallery beats a buried
changelog: it is where the doctrine earns its keep. Every entry names the *reported* symptom and
the *diagnosed* root cause separately (Standard 5).

> The entry below is a seeded template. Replace it with the first real failure you diagnose.

## FAIL-0001 (template) — Demo showed no data

- **Date**: 2026-07-21
- **Surface**: `GET /api/v1/demo`
- **Reported symptom**: The demo view rendered "no data".
- **Diagnosed cause**: `data/synthetic/demo.json` existed but was an empty array. The endpoint
  correctly raised HTTP 500 (`"synthetic fixture is empty"`) instead of silently returning `[]`.
- **Root cause**: Fixture authored empty during scaffold.
- **Fix**: Populated the fixture with a non-empty synthetic dataset. The smoke test asserts
  `items` is non-empty, so this cannot regress silently.
- **Doctrine link**: Standard 3 (no silent mock/fallback) and Standard 2 (smoke asserts non-empty).

## FAIL-0002 — `make migrate` failed on a clean machine (check_migrations driver)

- **Date**: 2026-07-21
- **Surface**: `scripts/check_migrations.py` (`make migrate`)
- **Reported symptom**: The migration-count check errored immediately after a successful
  `alembic upgrade`.
- **Diagnosed cause**: The script did `DATABASE_URL.replace("+psycopg", "")`, turning
  `postgresql+psycopg://...` into a bare `postgresql://...`. SQLAlchemy routes the bare URL to the
  **psycopg2** driver, which is not a declared dependency (the apps pin `psycopg` v3). `alembic`
  itself succeeded because it kept the `+psycopg` URL, so the failure surfaced only at the check step.
- **Root cause**: Driver mismatch between the migration step (psycopg v3) and the check step (psycopg2).
- **Fix**: Use `DATABASE_URL` unmodified so the check reuses the declared psycopg v3 driver. Proven
  against a real Postgres: `MIGRATION OK: 1 tables` at `EXPECTED_TABLE_COUNT=1`, and
  `MIGRATION CHECK FAILED: expected 2 tables, found 1` (rc=1) at `EXPECTED_TABLE_COUNT=2`.
- **Doctrine link**: Standard 4 (assert the table count) and Standard 1 (fix the root cause — the
  driver — not the symptom).

## FAIL-0003 — First public CI run: smoke job died before the stack started

- **Date**: 2026-07-23
- **Surface**: GitHub Actions `smoke` job (`docker compose up -d --build`)
- **Reported symptom**: CI run red on the first push; compose exited immediately.
- **Diagnosed cause (from the run log)**: `env file ... .env not found`. `docker-compose.yml`
  declares `env_file: .env`, and `.env` is gitignored by design, so it does not exist in a CI
  checkout. A second, deterministic failure sat behind it: the Dockerfile's `pip install .` now
  resolves `aignite-groundwork` from a `git+https` URL, and `python:3.12-slim` ships no git.
- **Root cause**: The CI environment was never given the dev-shaped inputs the compose file
  assumes (env file present, git available in the build image).
- **Fix**: CI smoke job copies the committed `.env.example` to `.env` before compose (the same
  step the README gives a stranger); Dockerfile installs git before `pip install`.
- **Doctrine link**: Standard 1 (root cause from the real log, not a retry) and Standard 2 (the
  smoke gate exists to catch exactly this before anyone calls the estate "green").

## FAIL-0002 — The golden eval's first run failed 4 of 5 bounds and found two real matcher defects

- **Date**: 2026-07-23
- **Surface**: `scripts/eval.py` (golden analyzer suite), first run
- **Reported symptom**: matcher accuracy 0.82, verdict correctness 0.75 (a planted
  disqualifying gap produced an "apply" verdict), paraphrase invariance 0.875, match-set
  stability 0.67.
- **Diagnosed causes**: (1) generic tokens created false direct matches — "development" in
  claim_key `people_development` directly satisfied a Go-microservices requirement; (2) at
  embedding dim=256 the hashing embedder's token collisions fabricated similarity between
  unrelated requirement/claim pairs, flipping rows between runs of different wordings.
- **Fix**: key-overlap now ignores generic tokens (a specific token must carry a direct
  match); hashing dim raised to 4096 so collisions cannot fabricate similarity. All bounds
  now pass at 1.0 with the thresholds unchanged.
- **Doctrine link**: the eval gate exists to say no, and did — before any of this reached a
  user-facing verdict (Standard 1: causes named from the failing rows, not guessed).

## FAIL-0003 — Extraction model advertised structured outputs but ignored the schema

- **Date**: 2026-07-23
- **Surface**: `scripts/eval_llm.py` first real run (gateway extraction)
- **Reported symptom**: `AttributeError`/`KeyError` — the model returned a top-level array,
  then `{"atomic_claims": ["...strings..."]}`, neither matching the strict object schema.
- **Diagnosed cause**: qwen3.6-flash's OpenRouter listing claims structured-output support,
  but observed behavior is loose JSON mode: the advertised capability flag and the actual
  enforcement disagree. Observed behavior wins over catalog claims.
- **Fix**: extraction model swapped to google/gemini-2.5-flash (schema enforced; 14 clean
  atomic claims, planted-fact recall 1.00). A one-line envelope adapter remains for
  top-level-array responses; items still validate strictly.
- **Second catch, same run**: raw claim_key jaccard across paraphrases was 0.12 with
  identical facts — model-invented names vary. The contract now compares canonicalized
  fact anchors (jaccard 0.92 observed), the Seismograph canonicalize-then-compare pattern.
- **Doctrine link**: Standard 1 (evidence over advertisement) and the portfolio thesis —
  perception is unreliable; canonicalize before you measure.

## FAIL-0004 — Adversarial review wave caught 8 defects before release, worst: live key baked into images

- **Date**: 2026-07-27
- **Surface**: whole repo (Dockerfile, `app/routes.py`, `scripts/check_migrations.py`, docs)
- **Reported symptom**: none — every gate was green. An adversarial code review of the released
  v0.2.0 tree confirmed 8 findings (1 critical, 2 major, 5 minor); 2 further claims were refuted
  on evidence.
- **Worst findings**: (1) `COPY . .` with no `.dockerignore` baked the developer's real `.env` —
  a live OpenRouter key — and the full `.git` history into every locally built image;
  `.gitignore` never protected the Docker build context, and CI escaped only because it copies
  the placeholder `.env.example`. (2) `GET /api/v1/fit/{id}` skipped bearer auth entirely, so
  stored fit reports with resume-derived claim statements were readable anonymously via
  enumerable ids. (3) The extract/parse endpoints ran LLM network calls inside open DB
  transactions with the OpenAI SDK's 600s default timeout — a slow model could pin the whole
  connection pool — while the `LLM_TIMEOUT_SECONDS` knob in `.env.example` was read by nothing.
- **Fix**: `.dockerignore`; auth on the read endpoint; read-close-call-write restructure plus a
  bounded client (`LLM_TIMEOUT_SECONDS`/`LLM_MAX_RETRIES` now real); typed 503 for the keyless
  openrouter embedder; `check_migrations.py` fails loud when `EXPECTED_TABLE_COUNT` is unset;
  contracts.md enforcement made real (`tests/test_contracts.py`); README phase/quickstart truth
  pass. Each behavior change carries a test that would have caught the original defect.
- **Doctrine link**: Standard 5 (reported vs. actual, in writing) and the review habit itself —
  green gates measure what they measure; an adversary reads what they do not.

## FAIL-0005 — Eval report embedded an environment-dependent line, breaking byte-reproducibility across environments

- **Date**: 2026-07-23
- **Surface**: `scripts/eval.py` report writer (central post-fix verification sweep)
- **Reported symptom**: the committed eval_report.md differed by one trailer line when the
  gate ran in a shell with a different OPENROUTER_API_KEY state.
- **Diagnosed cause**: the key-gated-section status note (present/absent by ambient env) was
  written into the report file, so "byte-reproducible" only held within one environment.
- **Fix**: the note now goes to stdout only; the report file is purely deterministic. Verified
  by running the eval with and without a key and comparing byte-for-byte.
- **Doctrine link**: reproducibility bounds must be environment-independent, or they are
  theater in every environment except the author's.

## FAIL-0006 — Undeclared-but-installed CUDA torch: a 5 GB dependency nothing imports

- **Date**: 2026-07-27
- **Surface**: `pyproject.toml` dependency list; production image build on beacon-gom
- **Reported symptom**: image builds took many minutes and pip installed the full
  nvidia-cu13 / triton / torch stack on a CPU-only VPS.
- **Diagnosed cause**: `sentence-transformers` was declared from the original scaffold, but
  no Phase 1 code imports it (verified by grep across `app/` and `scripts/`): embeddings go
  through `app/engine/embedding.py`, which is a deterministic hashing embedder plus an
  HTTP OpenRouter embedder. The declaration alone pulled CUDA torch into every image.
- **Measured impact**: images carrying it were 5.6-5.8 GB; the two apps without it were
  496-773 MB. Roughly 5 GB of unused, CVE-bearing surface per image.
- **Fix**: dependency removed, with a comment recording why and when to re-add it (the
  phase that actually imports a local cross-encoder). Tests unchanged and still green.
- **Doctrine link**: a dependency you do not import is a claim you cannot back. It also
  slowed every deploy, which is how it was noticed while shipping a security fix.

## FAIL-0007 — Every published hostname 404ed at the root URL

- **Date**: 2026-07-27
- **Surface**: `GET /` on `https://careercompiler.aigniteconsulting.ai`
- **Reported symptom**: none from any gate. A browser visiting the hostname received
  `404 {"detail":"Not Found"}` as `application/json`, measured in production.
- **Root cause, named correctly**: The front door 404ed on every published hostname because the estate gate asserted /health and the business loop and never asserted what a browser receives at the root URL, and a gate that tests only the paths its author remembers will pass forever while the front door is broken.
- **Not the cause**: a missing decorator on six apps. That is the instance. The class is an
  unswept assertion gap, the same shape as the 2026-07-27 unauthenticated-reads incident,
  where a defect found in two repos was fixed in those two and never swept across the estate.
- **Fix**: `GET /` serves a self-contained static page on every app, and the gap is closed as
  a class in two places. Each `scripts/gate.py` asserts the root route returns 200 `text/html`
  carrying the app name and the EVAL.md limits sentence verbatim. `estate_smoke.py` sends a
  browser-shaped request (`Accept: text/html`) to every hostname it finds **by parsing
  API_CONTRACT.md**, not from a literal list, so a seventh app is covered without editing the
  gate, and it fails on placeholder text.
- **Doctrine link**: rule 9, sweep the class not the instance. Also rule 10: the hostname
  enumeration fails loudly when it finds no hostnames, rather than passing over an empty set.


## FAIL-0008 — The local test image measured an environment that did not exist

- **Date**: 2026-08-02, found during the Phase 2 build.
- **Observed**: `careercompiler-service:latest` on the build workstation was **5.8 GB and
  carried `torch 2.13.0+cu130`** — a stale image predating the `e83080f` cleanup — while
  production ran clean at 608 MB with no torch at all. The Phase 2 selector and gate suites
  were first run inside that stale image, so early green results measured a dependency
  environment that existed nowhere but this machine.
- **Class**: the test environment diverges from the system under test. Third instance in
  this estate, after the noiseless golden fixtures that produced vacuous eval passes
  (Almanac 130/130/130, Parallax drift 0.0000) and the sqlite retention tests that passed
  while the real foreign-key graph left 11 rows behind (portfolio-ops FAIL-0004).
- **Remediation**: rebuilt from the current Dockerfile (610 MB, matching production), rebuilt
  the test image `FROM` that, and re-ran the full suite on it — 57 tests pass on the
  production-shaped environment. `LOOP_STATE.md` now instructs every session to rebuild the
  test image from the Dockerfile rather than trust whatever `:latest` is lying around, and
  `DECISIONS.md` 003 records the stale-image warning.
- **Rule this reinforces**: a local image is not evidence about production. Evidence comes
  from the artifact the Dockerfile builds today, or from production itself.
