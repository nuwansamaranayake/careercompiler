# CareerCompiler

**A compiler, not a ghostwriter.** Your verified career facts are the source code, the job
description is the target platform, and the resume is a compiled artifact in which every sentence
links back to evidence. Fabrication is not discouraged. It is structurally impossible.

## What it is

CareerCompiler produces a resume and cover letter tailored to a specific job description, built from
an existing resume plus a structured interview, with a provable zero-fabrication guarantee. It gives
an honest fit assessment that will say "do not apply," and it emits an interview-prep pack from the
same evidence.

Every mainstream tool in this category works the same way: paste resume, paste JD, receive a
rewritten document optimized for keyword coverage. Two failure modes follow. The model inflates — a
skill grazed once becomes "expert," a team of two becomes "led cross-functional teams" — and keyword
stuffing reads machine-written exactly when recruiters are deploying detectors to catch it. As open
source, this tool serves the people who most need it and can least afford subscriptions: students,
career changers, and job seekers anywhere, with a local-model mode so the most personal document a
person owns never has to leave their machine.

## How it works

Separate the fact base from the rendering, and put a deterministic linker between them.

1. **The Career Fact Graph.** An extractor and a resumable interview mine the user's history into
   atomic, typed claims. "Led migration of 42 services to Kubernetes, cutting deploy time 38%"
   decomposes into `led_migration`, `scope_42_services`, `platform_kubernetes`,
   `outcome_deploy_time_down`, `magnitude_38_pct` — each with its own evidence reference, confidence,
   and user-verification state.
2. **Deterministic selection.** Which facts make the page is a knapsack problem, not vibes: maximize
   requirement coverage, evidence strength, recency, and quantified impact under a hard page budget.
   The solver explains its omissions.
3. **The claim linker.** Generation is unconstrained in phrasing, fully constrained in substance.
   Every generated sentence declares the fact IDs it renders; a self-hosted NLI cross-encoder
   confirms entailment. A stronger verb than the evidence supports is a compile error.
4. **The Fit Report** decomposes the JD into typed requirements and scores each against the graph —
   matched, transferable, or unmatched — and will tell you honestly not to apply.

## The unique bet

The category leaders compete on templates, match scores, and one-click speed. Our bet is different:
the only open resume tool that compiles documents from a verified fact base, through an optimization
layer and an entailment gate, making fabrication a build failure, honesty a feature with teeth, and
interview prep a free by-product of provenance.

## Quickstart (local, zero external keys)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on POSIX)
pip install -e ../groundwork      # sibling shared library (uv users: uv sync)
pip install -e .[dev]
copy .env.example .env            # leave keys blank; the demo runs on synthetic data
uvicorn app.main:app --reload
```

In another shell:

```bash
set API_PORT=8000 && set SMOKE_TEST_TOKEN=dev && python scripts/smoke_test.py   # -> SMOKE OK
```

The `/api/v1/demo` endpoint serves the synthetic dataset in `data/synthetic/` — no OpenRouter
key, Postgres, or Redis needed to see the app respond. Those are required only for Phase 1
features (real extraction, persistence, migrations).

## Demo

A screenshot and GIF of the provenance map and the live compile-error moment (the linker rejecting
"led a cross-functional team of 12" against `scope_4_engineers`) land in Phase 2 alongside the
Next.js frontend. Until then, the synthetic `/api/v1/demo` payload is the fastest way to see the
shape of a Career Fact Graph record.

## Doctrine

This repo follows the AiGNITE operational doctrine: fail loud, no silent fallbacks, smoke-test real
endpoints. See [DOCTRINE.md](DOCTRINE.md).
