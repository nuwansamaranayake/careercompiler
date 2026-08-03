# NEXT — single objective for the next pass

**Requirement-type-aware matching: close the two published matcher misses.**

The per-embedder floors (v0.4.1) fixed every measured false verdict except two that
sit inside the true-positive band (EVAL.md): React-Native reads direct off a React
fact at 0.859 (lexical containment) and ICU-experience reads direct off software
incident-response at 0.793 (semantic gravity). Similarity alone cannot separate them.

Do, in order:
1. Type the requirement at parse time (jd.py already emits `kind`): certification,
   license, years-of, named-technology, general. For certification/license/years-of
   must-haves, a DIRECT match additionally requires the specific token (the cert name,
   the license, the number of years) to appear in the cited fact — similarity may only
   ever produce PARTIAL for those types.
2. Extend the labeled suite: the 35 corpus rows + a near-neighbor set (React vs React
   Native, AWS vs Azure, RN license vs PE license). Publish the curve and the misses,
   as EVAL.md now does for floors and thresholds.
3. Machine-checkable pass: the two published misses become partial-or-gap, all six
   corpus verdicts stay correct, golden eval stays 1.0 across its bounds.

Guardrails unchanged: compile gates untouched; matcher changes only ever tighten;
production stays at v0.4.1 unless the full ritual passes (snapshot current, estate
exit 0 including the demo-path gate, CI-green SHA, stats, Beacon GoM untouched).
