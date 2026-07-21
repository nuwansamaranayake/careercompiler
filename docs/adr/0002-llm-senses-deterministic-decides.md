# 2. The LLM senses; deterministic code decides

Date: 2026-07-21

## Status

Accepted

## Context

The whole product category — paste resume, paste JD, receive a rewritten document — lets a language
model both perceive the candidate's history *and* decide what to claim and how strongly. That is
exactly where fabrication enters: a model given authority over substance inflates a skill grazed once
into "expert," and a team of two into "led cross-functional teams." The portfolio thesis says the
LLM is a sensor, not a judge. CareerCompiler needs an architecture that makes that split load-bearing
rather than aspirational, so that fabrication is a catchable event rather than an accepted cost.

## Decision

Draw a hard line between what the model **senses** and what deterministic code **decides and
computes**, matching the deterministic / non-deterministic split in the blueprint.

**The LLM senses (produces typed, provenance-carrying claims):**

- Fact extraction — span-anchored, atomic decomposition of a resume into typed claims.
- JD parsing — the job description turned into typed requirements under a forced schema.
- Interview question generation and follow-ups.
- Bullet and cover-letter *phrasing*, and interview-prep question drafting.

**Deterministic code decides and computes (no model in the loop):**

- Fact-graph storage, versioning, and verification state.
- Requirement-to-fact matching and transferability flags.
- Knapsack content selection under the page budget, with omission explanations.
- The claim linker: reference integrity plus the NLI entailment gate.
- docx/pdf rendering, the ATS parse-back check, and the keyword-density linter.

Every model output is a claim that carries provenance and enters the system as untrusted until
deterministic code verifies it. No number, ranking, selection, or accept/reject decision is ever
taken by the model. Phrasing is the model's only unconstrained territory, and even phrasing must pass
the entailment gate before it reaches a document.

## Consequences

- Fabrication becomes a **compile error**: a sentence stronger than its cited evidence fails the
  build, visibly, instead of shipping. This is the demoable core of the thesis.
- Decisions are auditable — the matcher and selector explain their scoring and omissions, and every
  rendered sentence links back to the fact IDs it renders.
- The cost is unfashionable machinery: an NLI cross-encoder, span-anchored provenance, and an ILP
  selector are more engineering than a thin wrapper. That cost is the moat.
- The guarantee is scoped honestly: output is faithful to the *declared* fact base. The model never
  improves a fact, only its phrasing; verifying the truth of self-attested facts is handled by the
  interview's metric-probing and the self-attested vs. document-sourced flag, not by the model.
