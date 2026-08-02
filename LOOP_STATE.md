# LOOP_STATE — CareerCompiler Phase 2 and Phase 3

Run started 2026-08-02. Plan: `docs/superpowers/plans/2026-08-02-careercompiler-phase-2-3.md`.
Resume by reading the plan, then this file, then continuing at the first `todo` row.

Phase 1 closed 2026-07-23 (GATES_PASSED) and shipped as v0.2.3. Its milestone list lives in
the git history of this file; its design decisions that still bind are carried forward below.

## Environment facts established (do not re-derive)

- **Local test loop:** `docker run --rm -v "E:/AiGNITE/AiPortifolio/careercompiler:/src" -w /src cc-test python -m pytest tests/ -q`
  where `cc-test` is `careercompiler-service:latest` plus pytest and ruff. The runtime image
  ships no pytest, by design.
- **Production probe:** `docker run --rm --network host -v /opt/aignite-portfolio:/work <script>`
  on `beacon-gom` using the `careercompiler-service` image. The host has no venv and no pip,
  and building one on a live revenue box is not worth the risk.
- **Bearer token for production probes:** `/opt/aignite-portfolio/careercompiler/.smoke_token`.
- **Deployed:** tag `v0.2.3`, SHA `981e05e`, `APP_VERSION=0.2.3`, up 5 days.
- **Models configured in production:** extraction `google/gemini-2.5-flash`, reasoning
  `anthropic/claude-sonnet-5`, judge `openai/gpt-5.1`, embedding
  `openai/text-embedding-3-small`, NLI `cross-encoder/nli-deberta-v3-base` — D3 must still
  verify that one against a current source and pin a revision digest.

## Measured, not assumed (2026-08-02)

- The LLM path **works in production**. Extract: 22 claims in 8.0s, 0 rejected span anchors.
  JD parse: 4 requirements in 1.0s. Fit: `verdict=apply, matched=3, partial=1, gaps=0`.
  **The brief's A2 premise — that a reviewer hits a 503 — does not hold.**
- Real endpoint paths differ from the brief: extraction is
  `POST /api/v1/candidates/{cid}/claims/extract`; JD parse is
  `POST /api/v1/jobs/{jid}/requirements/parse`.
- The manager's supplied OpenRouter key verifies: 200 from `chat/completions`, `is_byok: true`.
- Only two GET routes exist under `/api/v1`: `/fit/{rid}` (401 without a token) and `/demo`
  (503 outside development). Everything else is POST, so a probe expecting GET 401 on them
  gets 405 — the probe is wrong, not the app.

## Design decisions carried forward from Phase 1

- **Zero-key entry paths are a product feature, not a fallback.** Claims and requirements
  accept explicit data entry (self-attested facts, hand-typed requirements), so the
  deterministic matcher and fit loop smoke without a key. The LLM endpoints refuse loudly
  without one. There is no silent path between the two, and there must never be.
- **Claim atom = `groundwork.Claim`** (type `skill_evidence`, `evidence_ref.span` into the
  source document) extended with app fields. The portfolio spine is reused, not reinvented.

## Progress

| Task | Status | Evidence |
|---|---|---|
| A1 single version source | **done** | commit `841ff52`; two tests, incl. one proving the helper reads `APP_VERSION` |
| A2 record measured truth | **done** | `DECISIONS.md` 002. Premise did not hold; no escalation |
| A3 contracts vs live schema | todo | routes for B/D/F still to be added to `contracts.md` **before** their code |
| B1–B5 demo access | todo | |
| C1–C4 selector | **C1–C3 done** | commit `3b0dac3`; 10 tests, mutation-checked. **C4 (paraphrase Jaccard ≥ 0.85) not written** |
| D2 linker | **done** | commit `82effa4` |
| D3/D5 entailment gate | **done** | commit `82effa4`; pinned digest, no fallback, 3 tests hold that line |
| D4 torch discipline | **done** | commit `74b05b6`; **1.86 GB** measured, `--network none` load verified |
| D6/D7 planted violations, red team | **done** | commit `82effa4`; 19 tests |
| D1 renderer | **todo** | the LLM drafting step. Gates exist and are proven; nothing calls them yet |
| D8 docx + provenance map | todo | |
| E1–E7 frontend | todo | not started |
| F1 ATS parse-back | todo | |
| G1–G6 prove it | todo | |
| H1–H6 release and deploy | **todo — nothing pushed, nothing deployed** | |

## Next action on resume

`D1` — the renderer, in `app/engine/renderer.py`. Everything it needs exists: `select()`
returns the fact ids allowed on the page, `linker.check()` enforces that the model used only
those, and `entailment.gate()` catches what survives. The renderer's only job is to phrase
selected facts into bullets that cite their ids. Then wire `POST /api/v1/compile` to run
select → render → link → gate in that order, failing on the first gate that objects.

**Verified environment for the next session:** build the test image with
`docker build -t cc-nli2 .` then `FROM cc-nli2` plus `pip install pytest ruff`. Do **not**
reuse a pre-existing `careercompiler-service:latest` on this workstation — the one found here
was a stale 5.8 GB CUDA build and is not representative.

## BLOCKED
(none yet — see `BLOCKED.md`)
