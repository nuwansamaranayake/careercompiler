# Risk Register — CareerCompiler

A living register. Each risk has an owner, a concrete tripwire (an observable signal that says the
risk is materializing), and a status. Seeded from the failure modes in the portfolio blueprint;
grows as the system does.

| Risk | Owner | Tripwire | Status |
|---|---|---|---|
| NLI false rejections frustrate users — the entailment gate rejects sentences that are in fact supported by the cited evidence, so the compile-error UX feels arbitrary and users stop trusting the gate. | eng lead | False-rejection rate on the held-out labeled entailment set exceeds the tuned threshold (target ceiling 5%), OR the same user re-submits an unchanged rejected sentence 3+ times in one session (a rejection they read as wrong). | open |
| Users paste a fabricated source resume and read the guarantee as "true" rather than "faithful to the declared fact base" — the tool then compiles polished output from a soft or invented claim. | eng lead | A claim flagged self-attested (no document span) is used to satisfy a must-have JD requirement in a Fit Report without a metric-probing interview follow-up having been generated for it. | open |
