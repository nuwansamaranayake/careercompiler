# PRD — CareerCompiler

## Users

- **The student / new graduate.** Has thin, scattered evidence and no budget for a subscription
  tool. Needs help surfacing what actually counts as achievement.
- **The career changer.** Has real experience whose relevance to a new field is non-obvious. Needs
  transferable matches marked honestly, not inflated into direct claims.
- **The privacy-sensitive job seeker.** Treats their resume as among their most personal data and
  will not paste it into a hosted product. Needs a local-model mode where nothing leaves the machine.
- **The high-volume applicant.** Wants to compile many tailored applications from one durable fact
  base rather than rewriting from scratch each time.

## Jobs to be done

1. Turn an existing resume plus a structured interview into a durable, typed Career Fact Graph.
2. Score a specific job description against that graph and get an honest verdict — including "do not
   apply" when a gap is disqualifying.
3. Compile a resume and cover letter where every sentence links back to a verified fact, and
   fabrication fails the build rather than shipping silently.
4. Get an interview-prep pack — each bullet with its underlying story, metrics, and the questions a
   skeptical interviewer would ask — for free, from the same provenance.

## Non-goals

- **We do not score employability or infer protected characteristics.** The tool assesses fit to a
  posting, never the worth of a person.
- **We do not improve facts, only phrasing.** The fabrication gate applies to the tool itself; the
  system never invents a stronger number, verb, employer, or tool.
- **The LLM does not decide content or compute numbers.** Selection is a deterministic knapsack;
  matching, entailment checks, keyword-density limits, and rendering are all deterministic. The model
  senses (extraction, JD parsing, phrasing); code decides.
- **We are not a keyword stuffer.** Optimizing for detector-defeating keyword density is the failure
  mode this tool exists to reject.
- **No employment guarantees, no application-volume optimization.** An open-source tool has no funnel
  to protect, so it can afford to tell you not to apply.

## Success metrics (targets)

Phrased as targets for the Phase-1 eval harness (see EVAL.md), not achieved measurements:

- **Zero unsupported claims survive the entailment gate**, proven by planting violations the gate
  must catch.
- **Fit Report is paraphrase-invariant** — the verdict does not swing when the JD is reworded.
- **Selection stability under JD paraphrase** — the same evidence wins slots across equivalent JDs.
- **100% ATS parse-back survival** — name, dates, titles, and skills survive an open-source parser.
- **Blind human preference** against a leading commercial tool on identical inputs.
