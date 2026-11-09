# Workspace UI Implementation Plan

> **For agentic workers:** executed natively in one session (autonomous run, operator
> standing rules). Steps use checkbox syntax for tracking.

**Goal:** A two-input web workspace over the existing API, a gated line-edit endpoint, a
96% quality gate, a browser e2e suite, and a visual guide.

**Architecture:** FastAPI serves the Next.js static export. Frontend logic in `web/lib/`
(vitest), thin components proven by Playwright against the real app with three named
doubles (sqlite, fakeredis, scripted LLM).

**Tech Stack:** Python 3.12+, FastAPI, pytest + pytest-cov, Next.js 15, React 19,
TypeScript strict, vitest, eslint, Playwright (Python).

**Spec:** `docs/superpowers/specs/2026-11-09-workspace-ui-design.md`

## Global Constraints

- Coverage floor 96 (line and branch) for `app/`, 96 for `web/lib/`.
- No migration. `EXPECTED_TABLE_COUNT` unchanged.
- Landing keeps the EVAL.md limits sentence verbatim.
- `contracts.md` and `CHANGELOG.md` updated in the same commit as any endpoint change.
- No real LLM calls (paid key is Tier 0). No deploy (Tier 2).
- Copy obeys `docs/agent-legibility/2026-11-09-workspace-truth-layer.md`.

## Review Focus

1. An edit to a cover-letter sentence saves and the letter PDF carries it.
2. A session that expires mid-flow ends in the restart panel, not a stuck spinner.
3. A pasted resume with Windows line endings anchors (normalization path).
4. A second analysis in the same session does not reuse the first verdict.
5. Editing position N never changes position M.

---

### Task 1: Gated bullet edit endpoint

**Files:** Modify `app/routes.py`, `contracts.md`, `CHANGELOG.md`. Test `tests/test_edit_bullet.py`.

**Interfaces:** Produces `PUT /api/v1/compile/{did}/bullets/{position}` body `{"text": str}`.
200 → `{"document_id", "position", "text", "cites", "entailment", "saved": true}`.
422 → `{"detail": {"error": "edit_rejected", "reference_integrity": {...}, "entailment": {...}}}`.
404 unknown document or position. 503 entailment unavailable. Tenancy via `_guard`.

- [ ] Tests: pass saves and GET shows new text and score; numeral not in cited facts → 422 and text unchanged; entailment below threshold → 422 unchanged; unknown position → 404; other tenant → 403; entailment unavailable → 503 unchanged; editing position 0 leaves position 1 untouched; letter document edit shows in letter PDF bytes.
- [ ] Implement by extracting the gate run shared with `check_bullet` into `_gate_sentence`.
- [ ] Contracts table row, changelog entry.

### Task 2: Static pages served generically

**Files:** Modify `app/main.py`. Test `tests/test_frontdoor.py`.

- [ ] `WEB_DIR` with `index.html`, `workspace/index.html`, `guide/index.html`, `demo/index.html`, `assets/x.png` → each served with and without trailing slash; unknown page → 404; path traversal → 404.

### Task 3: Backend coverage to 96

**Files:** tests only, plus `pyproject.toml` (`fail_under = 96`, branch on).

- [ ] Cover `cli.py`, `schemas.py`, `renderer.py`, `revise.py`, `embedding.py`, `entailment.py`, `pdf_out.py`, `docx_out.py`, `interview.py`, `main.py`, remaining `routes.py` branches with fakes already used in `tests/test_compile.py`.

### Task 4: Frontend foundation

**Files:** `web/lib/{types,api,format,pipeline}.ts`, `web/lib/*.test.ts`, `web/vitest.config.ts`, `web/eslint.config.mjs`, `web/package.json`.

**Interfaces:** `api<T>(token, path, init)`, `openSession()`, `runIntake(io, input, onStep)` returning `{candidateId, jobId, fit}`, `refusalFrom`, `plainDetail`, `friendly`, `verdictLabel`, `statusTone`.

- [ ] Unit tests at 96% over `web/lib/`.

### Task 5: Screens

**Files:** `web/app/{layout,page}.tsx`, `web/app/globals.css`, `web/app/workspace/page.tsx`, `web/app/demo/page.tsx`, `web/app/guide/page.tsx`, `web/components/*.tsx`.

- [ ] `npm run build`, `tsc --noEmit`, `eslint` clean.

### Task 6: E2E harness and suite

**Files:** `scripts/e2e_server.py`, `tests/e2e/{conftest,test_workspace_flow}.py`.

- [ ] Flows: paste resume + job → verdict → compile resume → rejected edit → accepted edit → PDF download → cover letter → download; sample path with the do-not-apply job; expired session panel.

### Task 7: Quality gate

**Files:** `scripts/quality_gate.py`, `Makefile` (`quality`), CI job.

- [ ] One command prints the score table and exits nonzero under 96 or on any failed check.

### Task 8: Visual guide

**Files:** `scripts/capture_guide.py`, `web/public/assets/guide/*.png`, `web/app/guide/page.tsx`, `docs/guide/CareerCompiler-Visual-Guide.pdf`.

- [ ] Screenshots from the e2e harness, labelled synthetic. PDF printed from `/guide/`.

### Task 9: Close

- [ ] README, CHANGELOG 0.6.0, NEXT.md, BLOCKED.md (deploy command, real-key smoke). Commit, push.
