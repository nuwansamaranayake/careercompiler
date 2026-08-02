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
| A1 version source | done | `841ff52` |
| A2 measured truth | done | DECISIONS 002 |
| A3 contracts from served schema | **done** | `142db1d`; literal enforcement + planned-not-served test |
| Review corrections (paths/1.9GB/FAIL-0008) | **done** | `142db1d` |
| C1–C3 selector | done | `3b0dac3`, mutation-checked |
| D1 renderer | **done** | `60de159`; per-fact form, code assigns citations |
| D2–D7 gates | done | `82effa4`; D4 1.86 GB `74b05b6` |
| D8 docx + provenance | **done** | `60de159`; provenance ships inside the docx |
| Local E2E real weights | **done** | `evidence/2026-08-02-local-e2e.txt`, 2 consecutive 11/11 runs |
| C4 paraphrase Jaccard ≥0.85 | todo | eval script extension |
| B1–B5 demo access | todo | contracts row planned; design in plan file |
| E1–E7 frontend | todo | `web/` not started; invoke agent-legibility-truth-layer first |
| E7 cost per compile | todo | measure via OpenRouter usage on one compile |
| F1 ATS parse-back | todo | cut F2–F4 first if short |
| G1–G6 estate proof | todo | extend portfolio-ops estate_smoke careercompiler loop |
| H release+deploy | todo | **nothing pushed, nothing deployed** |

## Renderer design decisions (do not regress; each earned by a live failure)

1. Model speaks aliases F1..Fn, never 16-hex ids (models mangle hex → unknown_fact_id).
2. Output is a per-fact FORM ({id, text}); code assigns citations (models shuffle assembled
   cites → true sentences at ~0.00 entailment against the wrong premise).
3. Charter is faithful restatement ONLY; requirements deliberately absent from the payload
   (requirement-steering produced gloss like "demonstrating leadership" → gate rejects).

## Deploy checklist additions (proven locally, will bite in production)

- The production env file on beacon-gom sets `NLI_MODEL=cross-encoder/nli-deberta-v3-base`
  with NO revision. env_file overrides image ENV → mixed config → gate 503s. At deploy, set
  the pinned pair (MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli @ 6f5cf0a2b59cab...) in the
  prod env or delete both lines so image ENV applies. `.env.example` already corrected.
- Run `python scripts/assert_image_size.py careercompiler-service` on the box after build
  (fires at 1.9 GB).
- After deploy smoke: compile must 201 AND a planted inflated sentence must 422 (G3).

## Local stack (left up deliberately)

compose project `careercompiler` on this workstation: DB_HOST_PORT=5544, API_PORT=8890
(5432 is cosmic-postgres, 8000 is the local Vedic Astro Engine — not ours, do not touch).
`.env` is gitignored and carries the manager's OpenRouter key. Test image: `cc-test2`
(rebuild: `docker build -t cc-nli2 .` then FROM cc-nli2 + pytest/ruff).

## Next action on resume

Part B (demo sessions: B1 token endpoint with TTL+budget in redis, B2 three tests, B3 seed
with planted disqualifying gap, B4 retention via portfolio-ops sweep of `demo-` prefixes,
B5 estate probe 401 assertion). Then E frontend (Next.js, truth-layer skill first), F1, G,
H in plan order. Plan: docs/superpowers/plans/2026-08-02-careercompiler-phase-2-3.md.
