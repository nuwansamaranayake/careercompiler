# CareerCompiler workspace UI — design (2026-11-09)

Operator goal: complete development and testing with a modern web interface. A user enters
a resume and a job description only, then chooses career matching, resume generation or
modification, or a cover letter. Code quality over 96%. A visual guide to the three tasks.

The operator opted out of design questions (autonomous run). Every choice below is the
builder's call, logged as a DECISION.

## Intent

The backend is complete at v0.5.0. The interface is not: it is a developer demo that leads
with seeded data and hides the real flow three clicks deep. The product needs a front door
where a job seeker brings two things and leaves with a verdict and two documents.

## Goals

1. `/workspace/`: resume in (PDF, docx, or pasted text), job description in (pasted text),
   one button. Then three tabs: Career match, Resume, Cover letter. Interview prep stays as
   a fourth tab because it already ships.
2. Resume modification is real: edit any line, both gates re-check, a passing edit is saved
   and ships in the downloads. Length is a choice (half page or one page).
3. A sample path with synthetic data for visitors who bring nothing (`/demo/`).
4. A measurable quality gate at 96%, run by one command.
5. A visual guide at `/guide/` plus a PDF copy in `docs/guide/`.

## Non-goals

No accounts, no saved history across sessions, no payment, no ATS scoring, no percent-match
number, no new LLM prompts, no schema migration.

## Anti-goals

- Copy that suggests the product improves or invents resume content.
- A mock fallback when the API fails. Errors show as errors.
- A UI path that skips a gate.

## DECISIONS

- D1 Stack: keep Next.js 15 static export served by FastAPI. No node in production.
- D2 Session: the workspace uses the existing scoped demo session token. No new auth.
- D3 Quality score: the lowest of (a) backend line and branch coverage over `app/`,
  (b) frontend coverage over `web/lib/`. All of ruff, tsc strict, eslint, next build, and
  the browser e2e suite must also pass. The gate fails below 96.
- D4 Frontend logic lives in `web/lib/` (pure, unit tested). Components stay thin and are
  proven by the browser e2e suite against the real API.
- D5 E2E harness: the real FastAPI app, the real matcher, selector, linker, entailment
  model, PDF and docx writers. Three doubles only, named and development-only: sqlite for
  Postgres, fakeredis for Redis, a scripted stand-in for the language model. Reason: real
  model calls spend against a paid key, which is a Tier 0 action.
- D6 New endpoint `PUT /api/v1/compile/{did}/bullets/{position}`. Same gates as
  `/compile/check`, then persists text and entailment score. Cites cannot change.
- D7 Deploy tier 2 (uploaded resumes are personal data, host shared with a paying
  product). Build, gate, commit, push. The deploy command goes to BLOCKED.md.
- D8 Aesthetic: "proof sheet". Warm paper, ink type, compiler annotations in mono, a
  rubber-stamp verdict. Fraunces for display, Hanken Grotesk for body, JetBrains Mono for
  annotations, all self-hosted. Brand green, gold, and red carry meaning only: pass,
  caution, reject. Dark mode is an ink-black desk with the same paper sheets.

## Screens

**Landing `/`.** Headline wedge, the three outcomes, how it works in three steps, the
EVAL.md limits block verbatim, corrected "Not for". Primary action: open the workspace.

**Workspace `/workspace/`.**
1. Intake. Two cards side by side. Resume: drop zone for PDF or docx, or a paste tab. Job:
   optional title, textarea. One primary button. A link loads the synthetic sample.
2. Build log. Steps tick as they run: session, resume stored, facts extracted (with counts
   and rejected anchors), posting parsed, evidence matched.
3. Results. A verdict stamp, counts, then tabs.
   - Career match: requirement table, status, evidence, the case against.
   - Resume: length choice, compile, a paper sheet preview. Click a line for its cited
     facts. Edit a line, the gate answers, a pass saves. Omissions listed with reasons.
     PDF and docx downloads.
   - Cover letter: compile, letter sheet, same line editing, downloads.
   - Interview prep: built from the compiled resume.

**Sample `/demo/`.** The workspace with the seeded synthetic candidate and two seeded jobs.

**Guide `/guide/`.** Three task sections with numbered steps and labelled screenshots.

## Errors and edges

- Session expired or budget spent: one panel, one button, state cleared.
- Upload over 2 MB, wrong type, scanned PDF: the API's typed detail shown as is.
- Zero requirements parsed, zero facts extracted: stop the pipeline, say why, keep inputs.
- Compile refusal after repair: the refusal panel (sentence, cited facts, reason).
- LLM or entailment unavailable: typed 503 text shown. Never a fallback.

## Left to the builder

Component boundaries, CSS details, test names.
