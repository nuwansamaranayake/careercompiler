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

## Progress — SHIPPED 2026-08-03

**Live: https://careercompiler.aigniteconsulting.ai — v0.3.1 (SHA 54745de), estate gate
exit 0, G6 walkthrough green.** Tags: careercompiler v0.3.0 + v0.3.1, portfolio-ops v0.3.0.

| Part | Status | Evidence |
|---|---|---|
| 0.1 prod NLI env | done | pinned pair set on host, backup kept |
| 0.2 host audit | done | `evidence/2026-08-03-host-audit-predeploy.txt` (8.6 GB available) |
| 0.3 limits | done | 1500m/2cpu applied; observed peak 687.6 MiB under real compile |
| B1–B5 | done | `tests/test_demo.py` (403/429/401); estate probe asserts 401x3 + cross-tenant 403 |
| B4 retention | done | `evidence/2026-08-03-b4-retention-drill.txt` — by row count, on production |
| E frontend + E2 | done | `evidence/2026-08-03-production-walkthrough.txt` |
| E9 truth audit | done | 30-agent adversarial audit; all confirmed findings fixed in v0.3.1 |
| G1–G5 | done | `evidence/2026-08-03-postdeploy-smoke.txt` exit 0; TLS chain verify 0 (ok); 11 tables |
| G6 | done | production walkthrough evidence above |
| H1–H5, H7, H8 | done | CI-green tags; README/EVAL/DECISIONS/FAILURES current |
| H6 1-hour watch | **in progress** | sampler on host writes /tmp/cc-stats-watch.log every 60s; peak so far 687.6/1500 MiB; final check due ~00:55Z |
| FAIL-0009 | recorded | 3-min 502 from stale EXPECTED_TABLE_COUNT; guard worked, checklist gap fixed |

Deferred (BLOCKED.md): C4 paraphrase stability, threshold calibration, F1 ATS parse-back.
