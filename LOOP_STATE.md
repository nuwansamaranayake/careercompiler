# LOOP_STATE — CareerCompiler overnight run 2026-08-02/03

Resuming: read NEXT.md first, then this file. Prior phase history: git log of this file.

## Environment facts established (do not re-derive)

- **Local test loop:** `docker run --rm -e WEB_DIR=/nonexistent -v "E:/AiGNITE/AiPortifolio/careercompiler:/src" -w /src cc-test python -m pytest tests/ -q`
  The `WEB_DIR=/nonexistent` matters: the image bakes /srv/web, which otherwise serves the
  static landing page at `/` and breaks the groundwork version assertions (the static page
  carries no version markup; the test suite runs against source-checkout semantics, as
  app/main.py documents). cc-test = careercompiler-service:latest + pytest + ruff; rebuild
  both after dependency or engine changes (scratchpad/cc-test.Dockerfile).
- **Estate smoke runs from THIS machine:** `python portfolio-ops/scripts/estate_smoke.py --ssh beacon-gom`
  (host has no pip; in-container runs lack docker CLI for the log probes).
- **Prod deploy:** on beacon-gom, `/opt/aignite-portfolio/careercompiler`, compose file
  `compose.prod.yml`, build args APP_VERSION/GIT_SHA/BUILD_TIME passed on the CLI.
  Rollback image tagged `careercompiler-service:rollback-v031` on the host.
- **Local stack:** port 8890, local .env OpenRouter key WORKS (full LLM path testable).
- **Concurrent-session hazard (observed tonight):** an earlier session ("AiPortifolio",
  same tree) auto-pushed 00579ef and created tag v0.3.2@00579ef at 21:32 CDT while this
  run was live; it went idle 21:46 CDT. Check `git ls-remote` before tags/pushes and
  `list_sessions` for isRunning before trusting the working tree.

## Production state

- **Deploy 1 (done):** v0.3.2 build (SHA 82ae595) live at careercompiler.aigniteconsulting.ai.
  Snapshot 107426401 success 02:35:50Z BEFORE deploy. MIGRATION OK 11 tables. Estate
  smoke exit 0 before and after. Obj 1 pass condition proven in a production browser:
  evidence/2026-08-03-obj1-production-walkthrough.txt. Beacon GoM untouched (5w uptime,
  mem flat). NOTE: tag v0.3.2 points at 00579ef (the other session's act); production
  self-reports 0.3.2@82ae595. Cosmetic; Deploy 2 ships as v0.4.0.
- **Deploy 2 (pending CI):** SHA a6acee4 = cover letters (gated, migration 0004 kind
  column, count stays 11) + interview pack + rejection legibility + normalization root
  fix + tailoring position. All local gates green (ruff, 89 tests, web build). Local E2E
  with real NLI: letter entails 0.79–0.97, planted overstatement rejected at 0.0003.

## Run ledger

- PASS 1 GOAL: Obj 1 custom job flow shipped and proven in production.
  OUTCOME: achieved — evidence/2026-08-03-obj1-production-walkthrough.txt.
- PASS 2 GOAL: Obj 2 legible rejections + root cause; Obj 3 letters; Obj 4 pack; Obj 5
  position. OUTCOME (code): achieved locally, gates green, awaiting Deploy 2.
  Obj 2 root cause MEASURED: candidate 31 source stores "AI-native\nsystems" (pypdf
  layout wrap) while the model quotes with a space; fix normalizes stored text; gate
  untouched. Format-rate measurement runs post-Deploy-2 (candidate-31 replay + PDF/docx
  pair).

## Run complete — 2026-08-03 ~03:45 UTC

- PASS 3 GOAL: Deploy 2 (v0.4.0) + production proofs + measurements.
  OUTCOME: achieved. v0.4.0 (51ca391) live and tagged on the CI-green SHA. Letter
  planted-overstatement rejected in production (unsupported_number). Pack live. Obj 2
  rates measured in production: 25.4% → 0.0% on the failing document; PDF/docx pair
  0%/0%. Estate smoke exit 0 pre and post. Beacon GoM untouched. Threshold calibration
  resolved (keep 0.7, misses published). C4 measured and published as FAIL — see
  BLOCKED.md, next objective in NEXT.md.
- Full report: SESSION_REPORT.md. Resume from NEXT.md.
- CI note: one failure mid-run (DuplicateColumn on fresh DBs, 0004 vs 0003 live-metadata
  create_all) fixed with an existence guard, both migration paths proven on a throwaway
  postgres before re-push.
