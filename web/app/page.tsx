/* The landing page. Every sentence here traces to docs/agent-legibility/
   2026-08-03-frontend-truth-layer.md; the limits block is verbatim from EVAL.md and the
   deploy gate asserts it stays that way. */
import Link from "next/link";

const LIMITS =
  "On a golden suite of 4 labelled job cases against a 6-fact synthetic career graph, " +
  "the analyzer places every requirement in the right bucket (matcher accuracy 1.0), " +
  "returns the correct apply or do-not-apply verdict on every case including planted " +
  "disqualifying gaps (1.0), never presents transferable evidence as direct (0 " +
  "violations), and holds its verdict across pre-authored paraphrases of the job " +
  "description (1.0); the suite is synthetic and small, so it does not measure " +
  "performance on real resumes or real postings. The Phase 2 compiler rejects a " +
  "sentence that claims more than its cited evidence supports: on the pinned entailment " +
  "model a faithful sentence scored 0.9976 and an inflated verb 0.0015, but the 0.7 " +
  "threshold is not yet calibrated between those extremes, so a borderline honest " +
  "paraphrase can be rejected; compile-time rejection is measured, fabrication recall " +
  "in the wild is not.";

export default function Landing() {
  return (
    <>
      <p className="dim mono small">CareerCompiler · an AiGNITE portfolio build</p>
      <h1>A resume compiler with compile errors.</h1>
      <p>
        Your resume is compiled from a graph of career facts, each carrying its provenance
        and its span into the source document. Every rendered
        sentence cites the facts that license it. A sentence that cites nothing, carries a
        number found in no cited fact, or claims more than its evidence supports{" "}
        <strong>fails the build</strong> — scored against the cited facts by a pinned
        entailment model, with the score shown.
      </p>

      <div className="panel">
        <p style={{ margin: 0 }}>
          <Link href="/demo/">
            <button>Open the live demo</button>
          </Link>
          <span className="dim" style={{ marginLeft: "0.8rem" }}>
            No sign-up. Synthetic data, labelled as such. Sessions expire on their own.
          </span>
        </p>
      </div>

      <h2>What it actually does</h2>
      <p>
        <strong>It gives honest verdicts.</strong> When a job posting carries a must-have
        requirement your fact graph cannot evidence, the verdict is do-not-apply, with the
        case against stated plainly.
      </p>
      <p>
        <strong>Tailoring is evidence selection, not rephrasing.</strong> A solver chooses
        which facts make the page under a hard budget, and every omitted fact carries a
        typed reason. The language model that phrases the bullets never sees the job
        posting and restates facts faithfully — wording does not shift per job. That is a
        deliberate design decision, made after watching requirement-steered phrasing
        produce claims the evidence could not support.
      </p>
      <p>
        <strong>The gate has no fallback.</strong> If the entailment model cannot run, the
        compile fails with a typed error. It never degrades to a keyword check, and no
        configuration can turn it off.
      </p>

      <h2>Published limits</h2>
      <div className="panel limits">
        <p style={{ margin: 0 }}>{LIMITS}</p>
      </div>

      <h2>Not for</h2>
      <p className="dim">
        Not a cover-letter writer, not a keyword stuffer, not an interview coach. It will
        tell you not to apply.
      </p>

      <p className="small dim" style={{ marginTop: "3rem" }}>
        <a href="/docs">API reference</a> ·{" "}
        <a href="https://github.com/nuwansamaranayake/careercompiler">source</a> · the LLM
        senses, deterministic code decides, humans approve.
      </p>
    </>
  );
}
