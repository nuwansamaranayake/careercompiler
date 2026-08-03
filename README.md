# CareerCompiler

**Live demo: <https://careercompiler.aigniteconsulting.ai>** — open it, start a demo
session (no sign-up), overstate a bullet, and watch the compile fail with the cited
evidence beside it.

> **Status: Phase 2 compiler deployed (v0.3.0).** The Phase 1 honest analyzer
> (span-anchored extraction, deterministic matcher, do-not-apply verdicts) plus the
> generation half: a knapsack content selector with typed omission reasons, an LLM renderer
> that phrases but never chooses content or computes a number, a deterministic
> reference-integrity linker, and an NLI entailment gate pinned by revision digest.
> [ROADMAP.md](ROADMAP.md) shows what exists versus what is next.

**A compiler, not a ghostwriter.** Your span-anchored career facts are the source code, the job
description is the target platform, and the resume is a compiled artifact in which every sentence
links back to evidence. A sentence that cites nothing, cites a fact that does not exist, or carries a number found in no cited fact fails the build deterministically; a sentence that claims more than its cited evidence supports is rejected by an entailment model whose threshold (0.7) sits between a measured 0.9976 for a faithful sentence and 0.0015 for an inflated one — and is not yet calibrated between those extremes. The compile error is the product.

## What it is

CareerCompiler compiles a resume tailored to a specific job description from a graph of
span-anchored career facts, designed so fabrication is a build failure: every generated
sentence must cite fact IDs and pass an entailment gate, proven by evals that plant
violations the gate must catch. It gives an honest fit assessment that will say "do not
apply." Cover letters and an interview-prep pack are roadmap items, deliberately cut from
this release ([BLOCKED.md](BLOCKED.md)).

The common shape in this category — paste resume, paste JD, receive a rewritten document
optimized for keyword coverage — invites two failure modes: the model inflates (a skill
grazed once becomes "expert," a team of two becomes "led cross-functional teams"), and the
inflated result is exactly what reads machine-written. This tool inverts the design:
tailoring is evidence *selection* under a page budget, the renderer never sees the job
posting, and a sentence stronger than its cited evidence does not compile. Open source, so
the people who can least afford subscriptions can run it.

## How it works (the design)

Separate the fact base from the rendering, and put a deterministic linker between them.

1. **The Career Fact Graph.** An extractor and a resumable interview mine the user's history into
   atomic, typed claims. "Led migration of 42 services to Kubernetes, cutting deploy time 38%"
   decomposes into `led_migration`, `scope_42_services`, `platform_kubernetes`,
   `outcome_deploy_time_down`, `magnitude_38_pct`, each with its own evidence reference, confidence,
   and user-verification state.
2. **Deterministic selection.** Which facts make the page is a knapsack problem, not vibes: maximize
   requirement coverage, evidence strength, recency, and quantified impact under a hard page budget.
   The solver explains its omissions.
3. **The claim linker.** Generation is unconstrained in phrasing, fully constrained in substance.
   Every generated sentence declares the fact IDs it renders; a self-hosted NLI cross-encoder
   confirms entailment. A stronger verb than the evidence supports is a compile error.
4. **The Fit Report** decomposes the JD into typed requirements and scores each against the graph:
   matched, transferable, or unmatched, and will tell you honestly not to apply.

## What exists today (verified)

This scaffold's doctrine is already enforced, not promised. Three checks you can run in five minutes:

1. `python scripts/smoke_test.py` against a running instance: hits real endpoints and asserts
   non-empty, schema-valid data. Passes.
2. Set `APP_ENV=production` and call `/api/v1/demo`: returns 503, because fixture data outside
   development is forbidden by code, not by convention.
3. `python scripts/eval.py`: the golden analyzer suite. Every EVAL.md bound passes at 1.0
   and the report is byte-reproducible; its first run caught two real matcher defects
   (FAILURES.md). A missed bound fails CI: the eval job is required.
4. `python -m app.cli fit --facts data/synthetic/golden/golden.json --case gap-disqualifier`:
   an honest DO-NOT-APPLY verdict with the case against applying, no server or key needed.

## The unique bet

The category leaders compete on templates, match scores, and one-click speed. No tool we reviewed (July 2026) compiles documents from a verified fact base through an optimizer and an entailment gate. That combination is the bet: fabrication as a build failure, honesty as a feature with teeth, interview prep as a by-product of provenance.

The full scoped novelty statement, with the field surveyed, is in [PRD.md](PRD.md).

## Quickstart (local, zero external keys)

### Standalone clone

```bash
python -m venv .venv
source .venv/bin/activate         # POSIX     (.venv\Scripts\activate on Windows)
pip install -e .[dev]             # groundwork resolves from GitHub automatically
cp .env.example .env              # POSIX     (copy .env.example .env on Windows)
uvicorn app.main:app --reload
```

### Developing the whole portfolio (sibling checkout, editable)

```bash
git clone https://github.com/nuwansamaranayake/groundwork ../groundwork
pip install -e ../groundwork
pip install -e .[dev]
```

The smoke test exercises the persisted fit loop, so it needs Postgres up and migrated first
(its docstring says so: "Requires the database to be up"). In another shell:

```bash
docker compose up -d db           # Postgres 16 (pgvector) on localhost:5432
alembic upgrade head              # apply migrations to the fresh database
export API_PORT=8000 SMOKE_TEST_TOKEN=dev-smoke-token && python scripts/smoke_test.py   # POSIX -> SMOKE OK
set API_PORT=8000 && set SMOKE_TEST_TOKEN=dev-smoke-token && python scripts/smoke_test.py  # Windows
```

(The token matches `SMOKE_TEST_TOKEN` in `.env.example`, which the server read when you copied it
to `.env`.)

Only the `/api/v1/demo` endpoint is key- and database-free: it serves the synthetic dataset in
`data/synthetic/` with no OpenRouter key, Postgres, or Redis. Those are required for the Phase 1
features (real extraction, persistence, migrations) and therefore for the smoke test above.

## Demo

Open <https://careercompiler.aigniteconsulting.ai/demo/>, start a session (no sign-up),
compile the seeded candidate, then challenge a bullet and overstate it: the linker rejects
an invented number deterministically, and the entailment gate rejects an inflated verb with
the score and the cited facts shown beside the sentence.

## Doctrine

This repo follows the AiGNITE operational doctrine: fail loud, no silent fallbacks, smoke-test real
endpoints. See [DOCTRINE.md](DOCTRINE.md).
