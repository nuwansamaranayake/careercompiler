# Decisions

Choices made deliberately, with the reasoning, so a reviewer can disagree with the judgement
rather than guess at the intent. A default nobody examined is not a decision.

---

## DECISION 001 — the NLI entailment model, pinned by revision digest

**Date:** 2026-08-02
**Status:** adopted
**Source:** the Hugging Face model API, queried directly on the date above. Not recalled.

The gate that decides whether a sentence outran its evidence cannot rest on a remembered
model name or a floating tag. Five candidates were checked for existence, license, current
revision digest, and weight size. All five exist and are permissively licensed:

| Model | License | Revision digest | Weights |
|---|---|---|---|
| `cross-encoder/nli-deberta-v3-base` | apache-2.0 | `6c749ce3425cd33b46d187e45b92bbf96ee12ec7` | 738 MB |
| **`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`** | **mit** | **`6f5cf0a2b59cabb106aca4c287eed12e357e90eb`** | **369 MB** |
| `MoritzLaurer/deberta-v3-large-zeroshot-v2.0` | mit | `cf44676c28ba7312e5c5f8f8d2c22b3e0c9cdae2` | large |
| `microsoft/deberta-large-mnli` | mit | `7296194b9009373def4f7c5dad292651e4b5cf4e` | large |
| `facebook/bart-large-mnli` | mit | `d7645e127eaf1aefc7862fd59a17a5aa8558b8ce` | ~1.6 GB |

**Decision: `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`, pinned at revision
`6f5cf0a2b59cabb106aca4c287eed12e357e90eb`.**

Rationale:

- **It is trained on the task this gate actually performs.** MNLI + FEVER + ANLI. FEVER is
  fact verification against evidence and ANLI is adversarially mined — a sentence that is
  *almost* supported by its evidence is precisely the adversarial case, and precisely the
  failure this application exists to prevent.
- **369 MB against 738 MB for the value currently in the production environment**, at the
  same DeBERTa-v3-base architecture. Half the weight matters because the image ships on a box
  running a live revenue product, and D4 sets a hard 2 GB ceiling.
- **MIT permits this use**, including commercial, with attribution.
- The large variants were rejected on size alone. `bart-large-mnli` at ~1.6 GB would consume
  the entire image budget before torch is installed.

**The digest is the pin, not the tag.** `main` moves. A gate whose verdict can change because
somebody pushed to a model repository is not a gate. `NLI_MODEL_REVISION` is required at
startup; the container refuses to boot without it rather than silently resolving `main`.

**Supersedes** the `NLI_MODEL=cross-encoder/nli-deberta-v3-base` value found in the production
environment on 2026-08-02, which was set without a recorded rationale and with no revision pin.

---

## DECISION 002 — A2 needed no cost escalation, because the premise did not hold

**Date:** 2026-08-02
**Status:** recorded

The brief instructed that if no LLM key were configured in production, the resulting 503 on
extraction and JD parsing was a cost decision for the manager, to be escalated with a measured
per-run token cost.

**Measured against production before acting**, per the audit-first rule:

```
POST /candidates/{cid}/claims/extract   201  {"stored":22,"rejected_span_anchor":0}   8.0s
POST /jobs/{jid}/requirements/parse     201  {"parsed":4}                             1.0s
POST /fit                               201  {"verdict":"apply","matched":3,...}      0.1s
```

`OPENROUTER_API_KEY` is configured and the LLM path works. The 503 exists in `routes.py:41`
but does not fire in production. **There is no decision to escalate and no BLOCKED entry**,
and reporting one would have been reporting the brief back rather than the system.
