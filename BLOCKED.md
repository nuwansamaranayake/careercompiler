# BLOCKED / deferred — needs a decision or scheduled work, with what unblocks it

- **PRODUCTION HAS NO WORKING OPENROUTER KEY, and has not since 2026-08-10. This blocks
  the v0.6.0 deploy and breaks v0.5.0 today.** The shared key (fingerprint `7E1A03D4`)
  was revoked on 2026-08-10; `KEY_ROTATION_BLOCKED.md` at the portfolio root lists
  CareerCompiler among seven apps down on it. Measured 2026-11-09 from the production
  host, through the app's own embedder, in BOTH the v0.5.0 and the v0.6.0 image:
  `embeddings endpoint answered 401`. Effect on the live site, either version: a seeded
  sample verdict loads, and everything that calls a model fails (fact extraction, posting
  parse, fit with real embeddings, compile, cover letter, interview pack).
  **Unblocked by the operator only:** issue a new OpenRouter key for CareerCompiler
  (with a spend cap) and get it into `/opt/aignite-portfolio/careercompiler/.env` on
  beacon-gom as `OPENROUTER_API_KEY`. Never paste it into a chat: that is how the last
  one leaked. Then say "deploy CareerCompiler v0.6.0" again.
- **v0.6.0 was deployed and rolled back on 2026-11-09. Production is v0.5.0 (`3f954ba`).**
  The operator said "Deploy v0.6.0". What happened, in order:
  1. Backup at `20261109T160407Z`: running image tagged `careercompiler-service:pre-0.6.0`;
     `pg_dump` at `/opt/aignite-portfolio/backups/careercompiler-pre-0.6.0-20261109T160407Z.sql.gz`
     (11 tables, ends cleanly); `compose.prod.yml` and `.env` copied beside it.
  2. Built `59215a4` on the host in 3 minutes: 1.83 GB, self-check 12 of 12 with no network.
  3. Swapped. Healthy in 9 seconds, `MIGRATION OK: 11 tables`, Beacon GoM untouched.
  4. Public smoke from outside passed: `/`, `/workspace/`, `/demo/`, `/guide/` 200 with real
     content, version 0.6.0, three no-token calls 401, TLS verify 0, 15 of 15 guide
     pictures rendering in a real browser.
  5. **Estate gate failed**: `POST /api/v1/fit expected 201, got 503`. Cause: the dead key
     above, not the release.
  6. Rolled back per the rule: `pre-0.6.0` retagged `latest`, `up -d`, healthy in 12
     seconds, version 0.5.0 confirmed from outside. Total time on v0.6.0: about 27 minutes (16:08Z to 16:35Z).
  The same gate fails on v0.5.0 for the same reason, so no version can be released
  through it until the key exists. v0.5.0 was left in place as the known state rather
  than shipping a release whose gate did not pass.
  **To redeploy once the key is in place** (about 5 minutes; the backup above still stands,
  and no schema changed):
  `ssh beacon-gom`, `cd /opt/aignite-portfolio/careercompiler`, `git fetch origin main`,
  `git checkout --detach origin/main`,
  `docker compose -f compose.prod.yml build --build-arg APP_VERSION=0.6.0 --build-arg GIT_SHA=<sha> --build-arg BUILD_TIME=<utc> service`,
  `docker run --rm --network none --entrypoint python careercompiler-service:latest scripts/image_selfcheck.py`,
  `docker compose -f compose.prod.yml up -d --no-build service`. Then from the workstation
  `python portfolio-ops/scripts/estate_smoke.py --ssh beacon-gom --app careercompiler`
  must exit 0. Roll back with `docker tag careercompiler-service:pre-0.6.0 careercompiler-service:latest`
  and `up -d --no-build service`. Tag `v0.6.0` only after the gate passes.
  Left on the host: image tag `careercompiler-service:v0.6.0-failed-smoke` (the `59215a4`
  build; sound, but it predates the media-type fix, so rebuild rather than reuse it).
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
