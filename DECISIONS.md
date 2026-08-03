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
POST /api/v1/candidates/{cid}/claims/extract   201  {"stored":22,"rejected_span_anchor":0}  8.0s
POST /api/v1/jobs/{jid}/requirements/parse     201  {"parsed":4}                            1.0s
POST /api/v1/fit                               201  {"verdict":"apply","matched":3,...}     0.1s
```

`OPENROUTER_API_KEY` is configured and the LLM path works. The 503 exists in `routes.py:41`
but does not fire in production. **There is no decision to escalate and no BLOCKED entry**,
and reporting one would have been reporting the brief back rather than the system.

---

## DECISION 003 — torch is CPU-only, pruned, and the model is baked

**Date:** 2026-08-02
**Status:** adopted and measured

Four apps in this estate once declared `sentence-transformers`, pulled CUDA wheels, and ran
5.6–5.8 GB images; removing them reclaimed roughly 20 GB. This change deliberately brings a
torch dependency back, so it carries the constraints that failure earned.

**Measured, not specified:**

| Build | Size |
|---|---|
| Baseline, no entailment gate | 610 MB |
| CPU torch + transformers + baked model | 1.99 GB |
| Same, with `torch/test` and `torch/include` removed | **1.86 GB** |

The 1.99 GB figure passed the 2 GB ceiling by 10 MB. That is not a margin — any torch or
transformers patch release crosses it — so the two build-time artifact directories are removed
after install, buying 140 MB of real headroom. Nothing with a runtime use was touched.

**The CPU wheel index is pinned in the Dockerfile and in CI, never in `pyproject.toml`.** A
plain `pip install torch` on linux resolves the CUDA build. The build asserts
`torch.version.cuda is None` and fails if a CUDA wheel ever leaks in, because the next person
to add a dependency will not remember this.

**The checkpoint is baked.** Verified by loading it with `--network none`. The gate's
availability must not depend on Hugging Face being reachable from a box that also serves
Beacon GoM's paying users.

**Stale-image warning for anyone testing locally.** The `careercompiler-service:latest` image
on this workstation was 5.8 GB and contained `torch 2.13.0+cu130` — it predated the cleanup
commit `e83080f`. Production was already clean at 608 MB. A local image is not evidence about
production; rebuild before drawing conclusions from one.

---

## DECISION 004 — tailoring is evidence selection; the renderer never sees the job

**Date:** 2026-08-03
**Status:** adopted, stated on the public page rather than hidden

**The live failure that produced it (2026-08-02):** the renderer's prompt originally said
"aim each bullet at the requirements it helps satisfy." On real drafts that instruction
produced gloss the facts did not entail — "demonstrating team leadership", "track record
of technical leadership" — which the entailment gate rejected at ~0.00. The steering was
the cause: asked to aim at requirements, the model reached beyond the evidence.

**Decision:** the job's requirements are deliberately absent from the renderer's payload.
Selection (which facts make the page, under the budget) is where tailoring happens, and it
is deterministic. The renderer restates the chosen facts faithfully; wording does not
shift per job. A reviewer who expects per-job rephrasing must not be surprised, so the
demo page says this in plain text (E8). The honest version of "tailored" is "selected."

**The cover-letter exception (2026-08-03):** a letter is addressed to a specific role, so
it may reference the job directly — but only in the deterministic frame (greeting, role
line, closing), which is template text that claims nothing about the candidate. The
model still writes only evidence sentences under the same payload separation, and every
one passes the same linker and entailment gate as a resume bullet. The exception is in
where the role may be named, never in what may be claimed. Stated in the UI beside both
documents.
