# Changelog

All notable changes to CareerCompiler are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.1] - 2026-08-03

The gate gets a feedback path; the gate itself does not move.

### Added
- **The render repair loop (FAIL-0010).** On a numeral pre-check, linker, or entailment
  rejection, the renderer is re-prompted with the exact rejection reason — the offending
  token, the fact, and the numeral spellings the evidence licenses — for at most three
  audited rounds. The exhaustion verdict is issued by the unchanged linker and
  entailment gates; a draft the pre-check dislikes but the gates accept ships. Measured:
  1/20 seeded compiles failed before, 0/20 after; the loop's live engagement was proven
  by the demo-path gate (one repaired compile, one honestly refused letter).
- **Deterministic numeral pre-check** (`app/engine/revise.py`): the linker's own token
  arithmetic, imported — one definition — run before any gate round trip to catch the
  unsupported-number class cheaply. Honest cases (word numerals, formatted variants,
  years present in the fact) never trigger it.
- **The demo-path gate** (`scripts/demo_path_smoke.py`): walks the exact visitor
  sequence — session, upload, paste job, verdict, compile, letter, pack, downloads —
  against a live host with synthetic fixtures only; wired into the portfolio-ops estate
  smoke, so a broken demo path blocks any release. It caught FAIL-0011 before deploy.
- **Real-corpus runner** (`scripts/real_corpus_run.py`): one real resume against every
  supplied posting under a retention-swept private tenant; aggregates to EVAL.md,
  content never leaves `fixtures/private/` (gitignored).

### Fixed
- **Name-subject fact statements (FAIL-0011).** Extraction now writes bare-predicate
  statements ("Ran Kubernetes…", never "Jane Doe ran Kubernetes"), because a
  first-person letter sentence can never entail a premise about a named third party —
  measured 0.018 by the demo-path gate. Sensor fixed; gate untouched.
- **The failure UX.** "Compile again" is gone. A post-repair refusal names the sentence
  that could not be grounded, the facts it reached for, and why — the product being
  honest instead of looking broken.

## [0.4.0] - 2026-08-03

The original vision closes: upload a resume, paste any job, get the verdict, and on a
match walk out with a targeted resume, a cover letter, and an interview pack.

### Added
- **Custom job flow in the browser.** Paste any posting: create → parse → fit runs
  in-page, the verdict card renders with the requirement table, and every fit answers
  for exactly one resume (an uploaded resume becomes the working resume; verdicts are
  never reused across candidates). No internal id is ever shown.
- **Cover letters, gated (`POST /api/v1/cover-letter`).** Same select → render → link →
  entailment pipeline as the resume, letter voice, one gated sentence per fact. The
  job-referential frame (greeting, role line, closing) is deterministic template text
  that claims nothing about the candidate. Letter docx ships the provenance map.
  Planted overstatement rejected at 0.0003 in the local E2E against the real gate.
- **Interview preparation pack (`POST /api/v1/interview-pack`).** Built from
  gate-survivors only: the story is the cited fact statements verbatim with provenance,
  the metrics are the numbers those statements carry, the gaps and the case against come
  from the stored fit report. The model's only authority is the skeptical questions.
  Stateless; docx download.
- **Legible rejections.** The extract response carries each rejected claim with the
  quote the model offered and why it will never match; the demo renders them as the
  anchor check working, not an error.
- `kind` on `compiled_documents` (migration 0004, column add — table count stays 11).

### Fixed
- **The 35/138 span-anchor rejection rate, at its root.** Measured in production:
  PDF extraction hard-wraps sentences at layout line breaks and doubles spaces, so the
  model's faithfully-spaced quote fails the verbatim find. Uploaded text is now
  normalized (spaces collapsed, layout wraps joined, paragraph boundaries kept) before
  it becomes the anchoring source. The anchor check stays byte-verbatim: the gate is
  untouched, the source stopped lying about the document.
- Tenant scoping prefixes no longer leak into documents (observed live: a letter
  opening with "the demo-…-Platform Engineer role").

### Stated
- The tailoring position, in the product: the job chooses which facts make the page and
  never rewords them; the cover letter's fixed frame is the one place the role may be
  named. DECISION 004 gains the letter exception.

## [0.3.0] - 2026-08-03

Public surface: demo sessions and the frontend. Minor bump.

### Added
- **Demo access (Part B).** `POST /api/v1/demo/session` issues a scoped, budgeted,
  expiring bearer bound to a `demo-<stamp>Z-<hex>-` tenant. Cross-tenant 403, budget 429,
  expiry 401 — each proven by a test. Seeded synthetic tenant shows both verdicts,
  including the planted do-not-apply. Estate invariant unchanged: no token is 401
  everywhere.
- **The frontend (Part E).** Next.js static export served by FastAPI from the same
  container (no node runtime in production). Landing with the EVAL.md limits block
  verbatim; the demo page with fit verdicts, compile, provenance per bullet, docx
  download, PDF/docx upload, and the rejection moment: challenge a bullet, overstate it,
  watch the gate reject it with the cited facts beside it. Verified in a real browser:
  linker rejection (invented number), entailment rejection at 0.0007, faithful pass at
  0.9951.
- **`POST /api/v1/candidates/upload`**: PDF/docx multipart; text extracted server-side;
  span anchoring works against exactly that text.

### Measured
- Image size **1.87 GB** with the frontend baked (assertion fires at 1.9, ceiling 2.0).
- Container RSS with NLI weights resident: **530 MiB** after a real compile;
  production limit set to 1500m / 2 cpus and verified under load at deploy.
- Entailment on real weights in the browser: faithful 0.9951, inflated verb 0.0007,
  threshold 0.7 (uncalibrated between extremes — published on the page).

### Fixed
- Extract, parse and compile ran the key gate before the tenancy guard, answering 503
  where a cross-tenant request deserved 403. Guards now run first.
- The served `openapi.json` announced FastAPI's default `0.1.0` while the front page showed
  the deployed tag. Both now read `frontpage.build_version()`.

### Added — the engine underneath (built 2026-08-02, first released here)
- **Knapsack content selector** (`app/engine/selector.py`). CP-SAT maximizes requirement
  coverage, evidence strength, recency and quantified impact under a hard line budget.
  Every omitted fact carries one of four typed reasons, because a fact nobody asked for is a
  different answer than a fact that competed and lost.
- **Reference-integrity linker** (`app/engine/linker.py`). Deterministic, microseconds, runs
  before the model loads. Rejects a bullet citing nothing, an unknown fact id, a rejected span
  anchor, a fact the selector left off the page, and any number appearing in no cited fact.
- **NLI entailment gate** (`app/engine/entailment.py`). Pinned by revision digest. No fallback
  path: model unavailable raises `EntailmentUnavailable` and the build fails.

### Measured — engine
- **Image size: 1.86 GB**, against the 2.00 GB ceiling. Baseline without the gate is 610 MB.
  torch reports `2.13.0+cpu` and `torch.version.cuda is None`, asserted during the build.
  `torch/test` (83 MB) and `torch/include` (62 MB) are removed after install: build-time
  artifacts with no runtime use. A first attempt without that pruning measured **1.99 GB** —
  a near-miss inside measurement noise, not a pass. CI now asserts the size at **1.9 GB**
  (`scripts/assert_image_size.py`, run against the compose-built image on every push), so
  the next torch or transformers bump that creeps past the line gets a red CI run and a
  pointer to what is prunable, instead of discovering the 2.0 GB wall during a deploy.
- **The gate discriminates on real weights**, verified with `--network none` to prove the
  checkpoint is baked and never fetched at request time. Against the cited fact "Led a team of
  4 engineers at Acme Corp from 2019 to 2022":

  | Sentence | Entailment |
  |---|---|
  | "Led a team of 4 engineers at Acme Corp." | 0.992 |
  | "Directed engineering across the entire company." | 0.027 |
  | "Led a team of 4 engineers at Initech." | 0.001 |

- **The LLM path works in production** (2026-08-02): extraction 22 claims in 8.0s with 0
  rejected span anchors, JD parse 4 requirements in 1.0s, fit `verdict=apply`. The brief's
  premise that a reviewer meets a 503 does not hold.


## [0.2.3] - 2026-07-27

### Added
- `GET /` serves a self-contained static HTML page: the app thesis, what it measures in plain
  language, the EVAL.md limits sentence verbatim, the endpoint list, and a build stamp
  (version, commit, build time) injected from Docker build args. No framework, no CDN, no
  JavaScript. Public by design; every API endpoint behind it still requires a bearer token.
- `scripts/gate.py` asserts the root route returns 200 `text/html` carrying the app name and
  the EVAL.md limits sentence verbatim, and fails on placeholder text. The estate gate sends a
  browser-shaped request to every hostname it reads out of `API_CONTRACT.md`.

### Fixed
- Every published hostname 404ed at `/` because no gate asserted what a browser receives
  (FAILURES FAIL-0007).


## [0.2.2] - 2026-07-27

### Eval
- matcher accuracy 1.0 (>= 0.90), verdict correctness 1.0, transferable violations 0,
  paraphrase invariance 1.0, match-set stability 1.0. Byte-reproducible.

### Changed
- Unused `sentence-transformers` (CUDA torch) dropped; image 5.8 GB -> 608 MB.
- `scripts/gate.py` enumerates routes and fails on any unguarded non-public route.
- Eval report no longer embeds an environment-dependent line, so it is byte-identical with
  or without an ambient API key.

No contract change: this repo's reads were already bearer-gated in v0.2.1.

## [0.2.1] - 2026-07-23

### Removed
- Unused `sentence-transformers` dependency (and the CUDA torch stack it pulled). No Phase 1
  code imports it; production images drop from ~5.7 GB toward the ~0.5 GB baseline
  (FAILURES FAIL-0006).

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
