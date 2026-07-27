# CareerCompiler

> **Status: Phase 1 honest analyzer built (v0.1, branch `phase-1`).** Span-anchored fact
> extraction, JD parsing, the deterministic matcher, and the Fit Report with its honest
> do-not-apply verdict are real, tested, and eval-gated. Generation (and with it the claim
> linker and NLI gate) is Phase 2, as designed: the analyzer ships first.
> [ROADMAP.md](ROADMAP.md) shows what exists today versus what is next.

**A compiler, not a ghostwriter.** Your verified career facts are the source code, the job
description is the target platform, and the resume is a compiled artifact in which every sentence
links back to evidence. Fabrication is not discouraged. It is structurally impossible.

## What it is

CareerCompiler produces a resume and cover letter tailored to a specific job description, built from
an existing resume plus a structured interview, designed so fabrication is a build failure: every
generated sentence must cite fact IDs and pass an entailment gate (Phase 1), proven by evals that
plant violations the gate must catch. It gives an honest fit assessment that will say "do not apply,"
and it emits an interview-prep pack from the same evidence.

Every mainstream tool in this category works the same way: paste resume, paste JD, receive a
rewritten document optimized for keyword coverage (the tools we reviewed as of July 2026). Two
failure modes follow. The model inflates: a skill grazed once becomes "expert," a team of two
becomes "led cross-functional teams," and keyword stuffing reads machine-written exactly when
recruiters are deploying detectors to catch it. As open source, this tool serves the people who most
need it and can least afford subscriptions: students, career changers, and job seekers anywhere,
with a local-model mode so the most personal document a person owns never has to leave their machine.

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

Then, in another shell:

```bash
export API_PORT=8000 SMOKE_TEST_TOKEN=dev && python scripts/smoke_test.py   # POSIX -> SMOKE OK
set API_PORT=8000 && set SMOKE_TEST_TOKEN=dev && python scripts/smoke_test.py  # Windows
```

The `/api/v1/demo` endpoint serves the synthetic dataset in `data/synthetic/`: no OpenRouter key, Postgres, or Redis is needed to see the app respond. Those are required only for Phase 1 features (real extraction, persistence, migrations).

## Demo

A screenshot and GIF of the provenance map and the live compile-error moment (the linker rejecting
"led a cross-functional team of 12" against `scope_4_engineers`) land in Phase 2 alongside the
Next.js frontend. Until then, the synthetic `/api/v1/demo` payload is the fastest way to see the
shape of a Career Fact Graph record.

## Doctrine

This repo follows the AiGNITE operational doctrine: fail loud, no silent fallbacks, smoke-test real
endpoints. See [DOCTRINE.md](DOCTRINE.md).
