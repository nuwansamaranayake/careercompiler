# SECURITY — CareerCompiler

The baseline is the **OWASP Top 10 for LLM Applications (2025)** and the **NIST AI Risk Management
Framework: Generative AI Profile (NIST AI 600-1)**. CareerCompiler handles a resume — among the most
personal data a person owns — so its trust boundaries are a design input, not an afterthought: every
external input (source resume, job description, writing samples, retrieved documents) is untrusted
data, never instructions.

## OWASP LLM Top 10 (2025) — controls

| ID | Risk | Control in CareerCompiler |
|---|---|---|
| LLM01 | Prompt Injection | Source resume, JD, and writing samples are treated as untrusted data on a separate channel from system instructions; the model never executes text found inside them. Red-team injection cases ship in the eval suite. |
| LLM02 | Sensitive Information Disclosure | Resume PII is deterministically redacted before any external model call; a **local-model mode** runs the whole pipeline offline; explicit deletion is supported; no protected-characteristic inference and no employability scoring. |
| LLM04 | Data and Model Poisoning | Every fact carries a self-attested vs. document-sourced flag, so an unverified or planted claim is visibly untrusted rather than silently authoritative; model IDs are pinned per call. |
| LLM05 | Improper Output Handling | Every generated sentence passes the claim linker — reference integrity plus an NLI entailment check — before it can reach a document; rendering to docx/pdf is deterministic and output is never executed. |
| LLM06 | Excessive Agency | The tool has no autonomous write authority; it improves phrasing, never facts, and anything consequential requires human approval. There is no agent that edits the fact base on its own. |
| LLM09 | Misinformation | The core control: the entailment gate makes an unsupported claim a build failure, the Fit Report will say "do not apply," and a deterministic keyword-density linter caps machine-written density. |
| LLM10 | Unbounded Consumption | Hard budgets on tokens, tool calls, and loop depth per pipeline run; a runaway extraction or interview loop is treated as a security incident, not a quirk. |

## NIST AI RMF — Generative AI Profile

We use the NIST GenAI Profile's functions as an operating discipline. **Govern:** the doctrine and
this baseline are published per repo and reviewed in the same PR flow as code. **Map:** the trust
boundaries above name each untrusted input and each consequential output. **Measure:** the eval
harness (EVAL.md) treats fabrication, confabulation, and injection resistance as measured acceptance
gates, not vibes. **Manage:** captured failures live in FAILURES.md with their traces and the gate
that caught them.

## Secrets

No provider keys are needed for the synthetic demo. Real keys (`OPENROUTER_API_KEY` and datastore
credentials) live only in `.env`, which is git-ignored; `.env.example` ships with blank values.
Secrets are never logged — LLM traces record model, version, prompt hash, temperature, latency, and
cost, never raw credentials.

## Reporting a vulnerability

Report suspected vulnerabilities privately to **nuwans@hotmail.com**. Do not open a public issue.
You will receive an acknowledgment within 72 hours. Please allow time to investigate and ship a fix
before any public disclosure; a coordinated disclosure timeline will be agreed with you.
