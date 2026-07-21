# Roadmap — CareerCompiler

Three phases, following the MVP build path in the portfolio blueprint. Scope discipline is a
deliverable here: Phase 1 ships an honest analyzer before any generation exists, because the
analyzer alone is useful and demoable. Each phase mirrors a GitHub milestone; the public project
board tracks the issues under it.

## Phase 1 — The honest analyzer (no generation)

*Mirrors GitHub milestone `phase-1-analyzer`.*

The clearest way to prove the thesis is to ship value before any sentence is generated.

- **Fact extraction** — span-anchored, atomic decomposition of an existing resume into typed claims
  with provenance and a self-attested vs. document-sourced flag.
- **JD parser** — LLM parses a job description into typed requirements under a forced schema.
- **Deterministic matcher** — scores each requirement against the fact graph: matched with evidence,
  partially matched via an adjacent transferable fact (marked transferable, never direct), unmatched.
- **Fit Report** — matched / partial / gaps, and an explicit apply-or-not verdict.
- Real persistence (Postgres), migrations, and the `make eval` harness (currently `NotImplementedError`).

## Phase 2 — The compiler and the frontend

*Mirrors GitHub milestone `phase-2-compiler`.*

- **Knapsack content selector** — OR-Tools maximizes coverage, evidence strength, recency, and
  quantified impact under a hard page budget, and explains every omission.
- **Renderer** — LLM drafts bullets, each citing the fact IDs it renders.
- **Claim linker + NLI gate** — reference integrity plus a self-hosted cross-encoder entailment
  check; a sentence stronger than its evidence is a compile error that fails the build.
- **docx output** and the **provenance map**.
- **Next.js frontend** — the shared portfolio design system, the provenance-map UI, and the live
  compile-error moment where the linker rejects an inflated sentence on screen.

## Phase 3 — Interview, voice, and prep

*Mirrors GitHub milestone `phase-3-interview-and-prep`.*

- **Evidence-mining interview** — resumable, structured, prioritized to ask first about gaps blocking
  the highest-value JD requirements.
- **ATS parse-back gate** — the rendered document round-trips through an open-source parser; if name,
  dates, titles, and skills do not survive, the build fails.
- **Cover letters + style matching** — measured against the user's own writing samples.
- **Interview-prep pack** — each bullet with its story, metrics, and the questions a skeptical
  interviewer would ask, generated only from verified facts.
