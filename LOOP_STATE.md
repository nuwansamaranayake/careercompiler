# LOOP_STATE — CareerCompiler Phase 1

Branch: `phase-1`. Ledger cell: CareerCompiler Phase 1. BLUEPRINT L450-454: **fact extraction,
JD parser, matcher, Fit Report. No generation** — the honest analyzer ships first. Exit also
requires: real eval meeting EVAL.md bounds, smoke hits real business endpoints with real
processing, alembic migrations with table count updated, CI eval flips to required, and the
flywheel duty (a Seismograph contract ships with the LLM stage).

## Milestones (commit each; gate.py after each)

- [x] M1  EVAL.md numeric thresholds first; LOOP_STATE; branch
- [x] M2  engine/facts: span-anchored AtomicClaim model on groundwork.Claim; LLM fact
         extractor via gateway (strict JSON schema); self_attested vs document_sourced flags;
         data-entry path for claims (no LLM needed) (+tests, stub gateway)
- [x] M3  engine/jd: JD parser (LLM, schema-forced) -> typed Requirements (must_have /
         nice_to_have; skill|experience|education|other); data-entry path (+tests)
- [x] M4  engine/matcher: deterministic requirement<->claim scoring — direct + transferable
         (never presented as direct), embedding similarity + token rules, explainable
         per-requirement evidence (+tests)
- [x] M5  engine/fit: Fit Report — matched/partial/gap rows, disqualifying-gap logic, honest
         apply / do-not-apply verdict with the case against applying (+tests)
- [x] M6  scripts/eval.py: deterministic golden suite (synthetic fact graphs + labeled JDs,
         planted gaps, pre-authored JD paraphrases) meeting EVAL.md bounds; byte-reproducible
- [x] M7  schema + alembic (candidates, source_documents, atomic_claims, job_postings,
         requirements, match_scores, fit_reports) EXPECTED_TABLE_COUNT=8; API: candidates,
         claims (entry + key-gated extract), jobs (entry + key-gated parse), fit; CLI
         `python -m app.cli fit`; smoke = real deterministic loop keyless; Dockerfile
         migrate-on-start
- [x] M8  flywheel: contracts/extraction-stability.yaml (Seismograph DSL, versioned here);
         key-gated extraction paraphrase-invariance check; one REAL extraction observed
- [x] M9  CI eval -> required; README/contracts.md/CHANGELOG truth pass; full gate + compose
         smoke + prod-guard

## DECISION log
- Zero-key smoke path: claims and requirements accept explicit data entry (a real product
  feature — self-attested facts, manually typed requirements), so the deterministic
  matcher+fit loop smokes keyless. LLM extract/parse endpoints refuse loudly without a key
  (Standard 3: no silent fallback between paths).
- Flywheel scope: the Seismograph contract YAML ships here (contracts live in the target
  repo, per blueprint); the paraphrase-invariance check runs key-gated inside this repo's
  eval. Wiring gate.py to execute it via Seismograph's own runner needs Seismograph Phase 2's
  HTTP SUT adapter (Phase 1 Seismograph only samples in-process demo SUTs) — deferred there,
  recorded here.
- Claim atom = groundwork.Claim (type skill_evidence, evidence_ref.span into the source
  document) extended with app fields (claim_key, kind, magnitude, recency, provenance flag).
  The portfolio spine is reused, not reinvented.

## BLOCKED
(none)

## Next task
Phase 1 gates: full gate + compose smoke + prod-guard, then GATES_PASSED and stop (release only on explicit go).
