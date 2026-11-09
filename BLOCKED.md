# BLOCKED / deferred — needs a decision or scheduled work, with what unblocks it

- **v0.6.0 IS LIVE (2026-11-09, `9395178`). RESOLVED.** First attempt rolled back on a
  revoked OpenRouter key (FAIL-0014). The operator issued a new key; it was copied from
  a local file to the host `.env` without being displayed, and OpenRouter accepted it.
  Second attempt: backup `20261109T172121Z`, build 1.83 GB, self-check pass, healthy in 9
  seconds, public smoke pass, demo-path gate pass on the real model in 90 seconds, estate
  gate exit 0. Rollback remains `docker tag careercompiler-service:pre-0.6.0 careercompiler-service:latest`
  then `docker compose -f compose.prod.yml up -d --no-build service`.
  Still on the host: image tags `pre-0.6.0` (v0.5.0) and `v0.6.0-failed-smoke`, and the
  backups in `/opt/aignite-portfolio/backups`, including two copies of the old `.env`
  that hold only the revoked key.
- **Retention only runs when somebody runs the estate smoke (found 2026-11-09).** At
  deploy time production held 25 session tenants older than 7 days, the oldest from
  2026-09-08, while the site says such data is deleted once older than 7 days. Nothing
  on the host schedules the sweep. The estate run at the end of this deploy cleared all
  25 (148 rows; zero aged tenants remain). It will drift again. Unblocked by scheduling
  `estate_smoke.py --ssh beacon-gom --app careercompiler` or the sweep alone, daily. That
  is a standing job on the operator's machine or the host, so it needs the operator's yes.
- **The estate smoke is fragile from this workstation (2026-11-09).** It opens one SSH
  connection per SQL statement. With many aged tenants to sweep, one connection failed
  with an empty error (`probe command failed:`) and the run then stalled until killed.
  A rerun with fewer tenants left passed. Likely sshd connection throttling; not proven.
  Fix belongs in portfolio-ops: one SSH session per run.
- **The full estate smoke hung for more than 25 minutes (2026-11-09).** Run without
  `--app`, it printed its namespace line and nothing else until it was killed. With
  `--app careercompiler` it finishes in under a minute. Not diagnosed: it is in another
  app's loop, most likely one waiting on the same revoked key, and those apps were out of
  scope. Its output is block-buffered, so run it with `python -u` to see where it stops.
  The alert it tried to send on failure also failed: `RESEND_API_KEY is not set`.
- **Image size margin — RESOLVED 2026-11-09.** A rebuild had drifted to 1.93 GB, over
  the 1.9 GB assertion, almost all of it dependency and base-image drift. `git` now
  lives and dies in one build layer: 1.84 GB, 60 MB under the assertion. Verified by a
  local build, `scripts/assert_image_size.py`, and `scripts/image_selfcheck.py` run
  inside the image with `--network none` (12 of 12 checks). The unpinned dependencies
  in `pyproject.toml` will keep drifting; the assertion is the alarm for that.
- **`boto3` is an unused dependency (noticed 2026-11-09, not removed).** No code imports
  it, and with botocore it costs about 35 MB of image. The compose MinIO service it was
  scaffolded for is gone. Left in place because removing a declared dependency was not
  part of this run. Unblocked by the operator agreeing it can go; then delete it from
  `pyproject.toml` and the `S3_*` block from `.env.example`.
- **`llms.txt` for the three tasks and the published limits** (truth layer addendum,
  2026-11-09, backlog item 4). Deferred: not asked for in this run.

- **Matcher floors — RESOLVED same night for the measured classes (FAIL-0012,
  2026-08-03):** per-embedder floors landed (openrouter 0.75 direct / 0.55
  transferable), chosen from the 35-row labeled corpus curve and verified by re-fit:
  both hard-mismatch postings flipped to do-not-apply, all four true applies held
  (EVAL.md). REMAINS OPEN: the two published misses inside the true-positive band —
  React-Native↔React 0.859 (lexical containment) and ICU-experience↔incident-response
  0.793 (semantic gravity). Unblocked by requirement-type-aware matching
  (certification/license/years-of must-haves demand a specific token, not similarity),
  with a labeled near-neighbor suite as its gate.

- **Estate runs consume 2 of the 10/hour per-IP demo sessions (review finding,
  2026-08-03):** loop_careercompiler's B5 check opens one demo session and the
  demo-path gate opens another, so more than 5 estate runs from one IP in an hour
  false-fails careercompiler with 429. Tonight's cadence never exceeds 3. Unblocked
  by an operator decision: reuse one session across both checks, or let the estate
  bearer mint sessions exempt from the per-IP limit. Not band-aided overnight.
- **beacon-gom's portfolio-ops checkout has local modifications (2026-08-03):**
  `scripts/estate_smoke.py` diverges from origin by +191/−53 (an old hot-patch), plus
  untracked `scripts/retention.py` / `scripts/retention_drill.py` (content-identical to
  what origin now tracks) and an `evidence/` directory. `git pull` on the host aborts.
  Discarding host modifications is a forbidden operation, and nothing requires the
  host copy: the estate gate runs from the workstation via --ssh. Unblocked by the
  operator reviewing the host diff and choosing keep/stash/reset.

- **C4 paraphrase stability — measured, acceptance NOT met (2026-08-03).** Jaccard of
  matched-fact sets under JD paraphrase: 0.600 (hashing embedder), 0.833 (openrouter
  embedder) against the >= 0.85 acceptance. Failure mode identified and published in
  EVAL.md: paraphrase shifts which nice-to-haves the parse emits; must-have coverage
  agreed in both runs. Unblocked by: verdict-stability measurement and must-have vs
  nice-to-have stratification (`scripts/eval_paraphrase.py`), then a decision on
  whether the acceptance metric should be verdict stability rather than raw Jaccard.
  Deliberately not tuned to pass overnight.
- **F1 ATS parse-back gate**: render, parse back, fail on lost name/dates/titles/skills;
  still deferred — nothing tonight touched rendering structure.
- **Entailment threshold calibration**: RESOLVED 2026-08-03 — graded suite built and run
  (`scripts/eval_threshold.py`), curve published in EVAL.md, choice: keep 0.7
  (letter-voice faithfuls measure 0.79–0.83; a raise would false-reject honest letters).
  Two 0.7 misses published. Remaining follow-up: a letter-voice graded suite before any
  per-kind threshold.
- **Tag v0.3.2 anomaly (2026-08-03) — CLOSED**: a concurrently-running earlier session
  tagged v0.3.2 at 00579ef while this run had already deployed a build self-reporting
  0.3.2 at 82ae595. Ancestry verified 2026-08-03 (repair-loop run):
  `git merge-base --is-ancestor 00579ef 51ca391` → true, so the tagged groundwork
  refactor IS contained in production v0.4.0. The tag stays; nothing points at code
  that never shipped.
- **Image margin is thin again (2026-08-10):** v0.5.0 measures 1.89 GB against the 1.9
  assertion — reportlab cost ~20 MB and the coin-flip margin DECISION 003 warned about is
  back. Next size wave should prune before any further dependency (candidates: reportlab
  docs/tests dirs, transformers unused model classes) or the next patch release goes red.
