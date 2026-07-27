# CareerCompiler golden analyzer eval report

case platform-role: verdict=apply (expected apply), matched=['ci_cd', 'kubernetes', 'postgres', 'python']
case gap-disqualifier: verdict=do_not_apply (expected do_not_apply), matched=['kubernetes']
case transferable: verdict=apply (expected apply), matched=['kubernetes']
case mixed: verdict=apply (expected apply), matched=['cost_optimization', 'kubernetes']

| metric | value | bound | pass |
|---|---|---|---|
| matcher_accuracy | 1.0 | >= 0.9 | PASS |
| verdict_correctness | 1.0 | >= 1.0 | PASS |
| transferable_violations | 0 | <= 0 | PASS |
| paraphrase_invariance | 1.0 | >= 1.0 | PASS |
| match_set_stability_min | 1.0 | >= 0.85 | PASS |
