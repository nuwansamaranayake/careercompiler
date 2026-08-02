# CareerCompiler Phase 2 and Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A technical reviewer opens `https://careercompiler.aigniteconsulting.ai`, enters a demo without credentials, sees an honest fit verdict including a do-not-apply on a planted gap, compiles a resume, watches the claim linker reject an inflated sentence with the cited evidence beside it, and downloads a docx whose every sentence traces to a fact.

**Architecture:** The LLM phrases; it never selects content and never computes a number. Content selection is an OR-Tools knapsack over the fact graph under a hard page budget. Every rendered sentence cites fact ids. Two deterministic gates stand between the model and the document: a reference-integrity linker (cheap, catches most failures) and an NLI entailment gate (a sentence stronger than its evidence is a compile error). Both fail loud; neither has a fallback path.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Postgres 16 + pgvector, Redis, OR-Tools CP-SAT, HuggingFace cross-encoder NLI on CPU torch, python-docx, Next.js 15 + TypeScript, Docker Compose, Traefik.

---

## Audit findings that change the brief

Observation ran before planning, per the standing rule. Four of the brief's premises are wrong and the plan below reflects what is actually true, not what was reported.

| Brief says | Actually true (measured 2026-08-02) | Consequence |
|---|---|---|
| Extraction and JD parsing "return a typed 503 without a key" and a reviewer will hit that 503 | **The LLM path works in production today.** `OPENROUTER_API_KEY` is configured. Extract stored **22 claims in 8.0s**, 0 rejected span anchors; JD parse produced **4 requirements in 1.0s**; fit returned `verdict=apply, matched=3, partial=1`. | **A2 has no cost decision to escalate.** No BLOCKED entry. The 503 exists in code (`routes.py:41`) but does not fire in production. |
| Extraction is `POST /api/v1/candidates/{id}/extract` | `POST /api/v1/candidates/{cid}/claims/extract` | Any client written to the brief's path would 404. |
| JD parse is at a `/parse` path | `POST /api/v1/jobs/{jid}/requirements/parse` | Same. |
| `contracts.md` lists `POST /api/v1/facts/{id}/verify` as planned | Confirm against live schema in Task A3 before anything consumes it | A3 gates every later contract addition. |

**A1 root cause (confirmed, not guessed):** `app/main.py:9` is `FastAPI(title="CareerCompiler")` with no `version` argument, so FastAPI supplies its default `0.1.0`. The root page reads `os.getenv("APP_VERSION", "unreleased")` (`app/frontpage.py:26`), fed by `ARG APP_VERSION` in the Dockerfile, which the deploy sets to `0.2.3`. Two independent sources. The fix is one source.

**Already configured in production** (read from the running container, values masked): `LLM_MODEL_EXTRACTION=google/gemini-2.5-flash`, `LLM_MODEL_REASONING=anthropic/claude-sonnet-5`, `LLM_MODEL_JUDGE=openai/gpt-5.1`, `EMBEDDING_MODEL=openai/text-embedding-3-small`, `NLI_MODEL=cross-encoder/nli-deberta-v3-base`. The NLI value is a starting point only — Task D3 must verify it against a current source, check the license, and pin a revision digest, or replace it.

---

## Global Constraints

Copied verbatim from the brief. Every task's requirements implicitly include this section.

- **No git worktrees, ever.**
- **Forbidden on 82.197.95.191, no exception.** Beacon GoM is a live revenue product on that box. No `docker volume prune`, no `docker system prune --volumes`, no `docker volume rm`, no `rm -rf` under `/var/lib/docker`, no `docker compose down`, and nothing that stops, restarts, or removes a Beacon GoM container, image, volume, or network. Snapshot before anything destructive.
- **No push inside a loop.** Push only at the explicit push step. Tag only on a commit with observed green CI, and confirm the run URL for the exact SHA before the tag command.
- **Verify, do not recall.** Every model id, library version, and package name gets checked against a current source and pinned. Applies hardest to Part D. If it cannot be verified, log it and stop that step rather than guessing.
- **No silent mock fallback outside development.** Fail loud with a typed error.
- **After every migration, assert the expected table count.**
- **Escape hatch:** blocked by a credential, a permission gate, or a product decision that is the manager's → append to `BLOCKED.md` with step id, what is needed, who unblocks it, then continue the rest of the plan. Never stall.
- **Loop cap:** 25 verify-fix iterations per gate, then escalate to `BLOCKED.md`. Write `LOOP_STATE.md` for resume.
- **The OpenRouter key supplied by the manager never enters git.** It goes to the deploy host env and local `.env` only. `.env` stays git-ignored; verify with `git check-ignore` before any commit.
- **Torch is CPU-only.** `--extra-index-url https://download.pytorch.org/whl/cpu` in the Dockerfile and the CI install step, **never** in `pyproject.toml`. Image over 2 GB → stop and log to `BLOCKED.md` before deploying.
- **Every business read stays bearer-authenticated.** Zero unauthenticated business reads, provable by the estate probe.

---

## File Structure

**Backend, new:**
- `app/engine/selector.py` — OR-Tools knapsack content selection, returns selections **and** typed omission reasons
- `app/engine/renderer.py` — LLM drafts bullets, each citing fact ids; phrasing only
- `app/engine/linker.py` — deterministic reference integrity; runs before the NLI model is loaded
- `app/engine/entailment.py` — NLI gate, pinned model + revision, fails loud when unavailable
- `app/engine/docx_out.py` — docx writer plus the provenance map
- `app/engine/ats.py` — Part F1 parse-back gate
- `app/demo.py` — demo session tokens, scoped/expiring/rate-limited, and the synthetic seed
- `app/retention.py` — thin adapter over `portfolio-ops/scripts/retention.py`

**Backend, modified:**
- `app/main.py:9` — single version source
- `app/routes.py` — compile, demo, provenance, docx routes
- `app/config.py` — NLI pin, page budget, demo TTL and request budget
- `Dockerfile` — CPU torch index, baked model, memory/CPU limits
- `contracts.md`, `EVAL.md`, `CHANGELOG.md`, `DECISIONS.md`, `BLOCKED.md`

**Frontend, new:** `web/` — Next.js 15 app; landing, demo, compile view with the rejection moment, provenance map, upload.

**Estate, modified:** `portfolio-ops/scripts/estate_smoke.py` — full CareerCompiler loop, namespaced.

---

## Task list

Ordered by reviewer value. Part F is cut first if the schedule slips; Part D is never cut.

### Part A — fix what is already wrong

- [ ] **A1** Single version source. `app/main.py:9` → `FastAPI(title="CareerCompiler", version=os.getenv("APP_VERSION", "unreleased"))`. Test asserts `openapi.json` `info.version` equals the version string the root page renders, parsed from the same HTML the browser gets. Verify: `pytest tests/test_api.py -k version -v`.
- [ ] **A2** Record the measured truth in `BLOCKED.md` and `EVAL.md`: no 503 in production, LLM loop timings above. **No cost escalation** — the premise did not hold. Set the manager's supplied key on the deploy host env; never in git.
- [ ] **A3** Re-read `contracts.md` against the live schema. Add every route Parts B–F introduce **before** the code that consumes it. Verify: `pytest tests/test_contracts.py -v`.

### Part B — demo access without breaking the estate invariant

- [ ] **B1** `POST /api/v1/demo/session` issues a scoped, short-lived, rate-limited bearer token bound to a demo tenant. Browser holds it. Every server-side read stays bearer-authenticated.
- [ ] **B2** Three tests, not intent: cross-tenant read returns 403; request past budget returns 429; expired token returns 401.
- [ ] **B3** Seed a synthetic fact graph and two JDs — one clear fit, one with a planted disqualifying gap producing `do_not_apply`. UI labels seeded data synthetic.
- [ ] **B4** Retention window for demo-tenant rows, reusing `portfolio-ops/scripts/retention.py` rather than a second implementation. Prove the delete by row count.
- [ ] **B5** Extend the estate probe: every business read without a token still returns 401.

### Part C — the selector

- [ ] **C1** OR-Tools CP-SAT knapsack maximizing requirement coverage, evidence strength, recency, quantified impact, under a hard page budget.
- [ ] **C2** Every omission carries a typed reason.
- [ ] **C3** Degeneracy gate. Assert a nonzero sample, assert the selector actually rejected something, assert a budget too small to fit everything yields omissions with reasons. **A selector that passes by selecting everything has measured nothing.**
- [ ] **C4** Selection stability under JD paraphrase: Jaccard of matched-requirement sets ≥ 0.85.

### Part D — the renderer and the entailment gate (never cut)

- [ ] **D1** Renderer: LLM drafts bullets, each citing the fact ids it renders. No content choice, no arithmetic.
- [ ] **D2** Claim linker: a cited fact id that does not exist, or a sentence citing nothing, fails the build **before the model is consulted**.
- [ ] **D3** NLI gate. **Verify the model against a current source**, confirm the license permits this use, pin exact id **and revision digest**, record both in `DECISIONS.md` with date and source URL.
- [ ] **D4** Torch discipline: CPU wheel index in Dockerfile and CI only; hard memory/CPU limits verified by `docker stats` under load; model baked into the image; image size in `CHANGELOG.md`; over 2 GB → stop and log.
- [ ] **D5** Fails loud or not at all. Model unavailable → typed error. No weaker check, no keyword heuristic, no pass.
- [ ] **D6** Plant violations, assert every one is caught: stronger verb, invented number, employer never worked for, shifted date. The eval proves the gate **fails builds**, not that it passes clean ones.
- [ ] **D7** Red-team: resume and JD carrying instructions are untrusted data, never instruction. Ship the cases.
- [ ] **D8** docx output plus the provenance map.

### Part E — the frontend

- [ ] **E1** Next.js on the shared portfolio design system, dark and light.
- [ ] **E2** The compile-error moment: inflate a sentence, watch the linker reject it on screen with the cited fact beside it, reachable in under a minute from the landing page. **Invoke `agent-legibility-truth-layer` before writing this copy** (CLAUDE.md mandatory trigger for public-facing surfaces); save output to `docs/agent-legibility/`.
- [ ] **E3** Provenance map UI: click a bullet, see its facts.
- [ ] **E4** Honest empty states. No fabricated numbers, no placeholder metrics, no lorem. Unknown says unknown.
- [ ] **E5** Upload accepts PDF and docx. Span-anchored extraction; a failed anchor is stored rejected and never matches.
- [ ] **E6** Every frontend call maps to exactly one endpoint in `contracts.md`, verified before deploy.
- [ ] **E7** Record measured LLM cost per full compile run.

### Part F — Phase 3 (cut first)

- [ ] **F1** ATS parse-back gate: render, parse back, fail the build if name, dates, titles, or skills do not survive. **Build this one.**
- [ ] **F2** Interview-prep pack from verified facts only.
- [ ] **F3** Evidence-mining interview, resumable, gap-prioritized.
- [ ] **F4** Cover letters and style matching. **Cut first.**

### Part G — prove it

- [ ] **G1** Extend `estate_smoke.py` to the full loop: candidate, extract, job, parse, fit, select, render, gate, docx. Namespace every row; let the existing retention sweep it.
- [ ] **G2** Browser journey against real production endpoints. No localhost, no `-k`.
- [ ] **G3** Assert the negative case **in production**: a planted inflated sentence must fail the compile there, not only in CI.
- [ ] **G4** `openssl s_client -connect careercompiler.aigniteconsulting.ai:443 -servername careercompiler.aigniteconsulting.ai` — full chain, not leaf-only.
- [ ] **G5** After every migration, assert the expected table count.
- [ ] **G6** `EVAL.md` carries measured Phase 2 and 3 numbers **including the misses**; the root-page limits sentence and the `EVAL.md` block must not drift.

### Part H — release and deploy

- [ ] **H1** `groundwork` first if changed, then `careercompiler`, then `portfolio-ops`.
- [ ] **H2** Minor bump in 0.x (Parts B and E add public surface). Breaking → `BREAKING` at the top with a one-line migration note.
- [ ] **H3** Changelog carries the eval numbers and the D4 image size.
- [ ] **H4** Confirm the CI run URL for the exact SHA **before** the tag command.
- [ ] **H5** Deploy, run G1–G5 against production, file output to `evidence/`.
- [ ] **H6** Watch `docker stats` for one hour after deploy. Near cap under normal load → roll back and log. **A portfolio piece does not get to starve a paying product.**

---

## Self-review

**Spec coverage:** every lettered item A1–H6 has a task. A2 is answered rather than escalated, because the measurement contradicted the premise.

**Type consistency:** `selector.select() -> Selection(selected: list[FactRef], omitted: list[Omission])`; `renderer.draft() -> list[Bullet]` where `Bullet.cites: list[str]`; `linker.check(bullets, graph) -> LinkReport`; `entailment.gate(bullets, graph) -> GateReport`. Consumed in that order by the compile route.

**Riskiest task:** D4. Four apps in this estate previously shipped 5.6–5.8 GB images from CUDA wheels; removing them reclaimed ~20 GB. The 2 GB ceiling is a hard stop, not a target.
