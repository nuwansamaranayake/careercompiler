# Truth layer addendum — the workspace UI and the visual guide (2026-11-09)

Extends `2026-08-03-frontend-truth-layer.md`. That document stays canonical. This addendum
covers the copy added by the guided workspace (`/workspace/`), the redesigned landing page,
and the visual guide (`/guide/`). Rule unchanged: no sentence on a public page that the
tests or evals do not support.

## Diagnosis

Clear and provable: two inputs in, three documents out, every sentence cited and gated.
What the August page got stale on: its "Not for" line still says "not a cover-letter
writer" and "not an interview coach". Cover letters shipped in v0.4.0 and the interview
pack in v0.4.0. A page that denies a shipped capability is as wrong as one that invents
one. Risk to watch in the new copy: "resume builder" language. The product selects and
restates evidence. It does not invent achievements, and the copy must never suggest it
improves what the resume says.

## Truth layer (new canonical facts, with evidence)

| Fact | Evidence |
|---|---|
| The workspace needs two inputs only: a resume (PDF, docx, or pasted text) and a job description (pasted text) | `POST /api/v1/candidates/upload`, `POST /api/v1/candidates` with `resume_text`, `POST /api/v1/jobs`; e2e `tests/e2e/test_workspace_flow.py` |
| Career match returns apply or do-not-apply, with every requirement marked matched, partial, or gap and the evidence named | `POST /api/v1/fit`, `GET /api/v1/fit/{rid}`; golden eval 1.0 on 4 synthetic cases (EVAL.md) |
| The tailored resume is compiled from extracted facts; the job chooses which facts make the page, wording does not shift per job | DECISIONS 004; `tests/test_selector.py` |
| A cover letter is compiled through the same two gates; greeting, role line, and closing are fixed template text | `tests/test_cover_letter.py` |
| Editing a line re-runs both gates. An edit that passes is saved and ships in the PDF and docx; an edit that claims more than the cited facts support is rejected and nothing changes | `PUT /api/v1/compile/{did}/bullets/{position}`; `tests/test_edit_bullet.py` |
| Resume length is a budget the user picks (half page 14 lines, one page 28 lines); the solver decides what fits | `CompileIn.budget_lines`; `tests/test_selector.py` |
| Downloads are PDF and docx, each carrying its provenance appendix | `tests/test_pdf.py`, v0.5.0 production read-back |
| A workspace session is a scoped, budgeted token that expires in 30 minutes; resume data sits in that session's tenant and the retention sweep deletes it once older than 7 days | `tests/test_demo.py`; portfolio-ops retention sweep |
| Guide screenshots show the real interface running on synthetic data with a scripted stand-in for the language model | `tests/e2e/`, `scripts/e2e_server.py`; labelled on the guide page |

## Claims / evidence map (new copy)

| Claim on the page | Proof | Gap | Rewrite if gap |
|---|---|---|---|
| "Two inputs. Three documents. Every sentence cited." | endpoints above | none | — |
| "It will tell you not to apply." | fit verdict, golden eval | measured on synthetic cases only | keep, and keep the limits block beside it |
| "Edit any line. The gate checks your edit." | edit endpoint tests | none | — |
| "About 30 seconds to compile" | measured local and production runs (Aug 2026) | timing varies by model load | say "about 30 seconds in our measured runs" |
| "Your resume is deleted after 7 days" | retention sweep row counts | sweep runs on the production host only | say "deleted by a retention sweep once it is older than 7 days" |

## AI-washing risk register (additions)

- "AI resume builder / writer" → "compiles a resume from facts found in your own document"
- "optimizes your resume for the job" → "selects which of your facts fit this job; it never rewords them to match the posting"
- "ATS-friendly / beats the ATS" → forbidden. ATS parse-back is not measured (BLOCKED.md F1).
- "career matching score" as a percentage → forbidden. The product reports a verdict and per-requirement status, never an invented percent.
- "writes your cover letter" → "compiles a cover letter from your facts; fixed template frame, gated evidence sentences"
- Guide screenshots must carry the synthetic label. A screenshot of invented data shown as a real user result is a fabricated testimonial.

## Human memory layer

- Wedge stays: **"A resume compiler with compile errors."**
- New supporting line for the workspace: **"Two inputs. Three documents. Every sentence cited."**
- Proof moment to stage in the guide: the rejected edit, with the score and the evidence beside it.

## Not for (corrected)

Not an ATS keyword stuffer. Not a writer that invents achievements. Not a percent-match
scorer. It will tell you not to apply when a must-have requirement has no evidence.
(Removed: "not a cover-letter writer", "not an interview coach". Both capabilities ship.)

## Agent surface plan

1. Landing page: keep the EVAL.md limits block verbatim (deploy gate asserts it). Add the
   three outcomes as plain headings an agent can lift: Career match, Tailored resume,
   Cover letter.
2. `/guide/`: one section per task with a stable heading and a numbered step list, so a
   summarizer returns the steps and not the adjectives.
3. Page titles and meta descriptions name the mechanism (facts, gates), never "AI-powered".

## Technical deliverables backlog (ranked)

1. Workspace page with the two-input flow (high impact, medium effort) — this run.
2. Gated edit endpoint (high, low) — this run.
3. Visual guide with labelled real screenshots (high, low) — this run.
4. `llms.txt` describing the three tasks and the limits (medium, low) — deferred, logged in NEXT.md.
