/* The published limits, verbatim from EVAL.md (the block between the LIMITS markers).
   tests/test_frontend_copy.py asserts this string equals that block, and the deploy gate
   asserts it is on the live page. Change EVAL.md first, then this, never the reverse. */
export const LIMITS =
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
