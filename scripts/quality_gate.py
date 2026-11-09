"""The quality gate: one command, one number, no partial credit.

    python scripts/quality_gate.py                 # everything, browser suite included
    python scripts/quality_gate.py --report evidence/quality-gate.md

The quality score is the LOWEST of two measured coverages:
  * backend:  line and branch coverage of app/ under the full pytest suite
  * frontend: the lowest of statement, branch, function and line coverage of web/lib/
The score must be at least 96. It is a floor, not an average: a strong backend cannot
buy back a weak frontend.

A score alone proves little, so the gate also requires every check below to pass:
ruff, the pytest suite, tsc --strict, eslint, the vitest suite, the production build of
the frontend, and the browser e2e suite (real Chromium against the real app and gates).
A check that did not run is a failure. A browser suite that skipped is a failure. The
gate cannot be passed by not looking.

Exit 0 only when every check passed and the score is at least 96.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
OUT = ROOT / "data" / "local" / "gate"
FLOOR = 96.0
PY = sys.executable
NPX = shutil.which("npx") or "npx"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    seconds: float


def _run(name: str, cmd: list[str], cwd: Path, timeout: int,
         env: dict[str, str] | None = None) -> tuple[bool, str, float]:
    """Run one check with a hard timeout. Output goes to a log file, never the terminal:
    the gate prints verdicts, and the log is there when a verdict needs explaining."""
    log = OUT / f"{name}.log"
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})},
                              capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace")
        log.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
        return proc.returncode == 0, f"exit {proc.returncode}", time.time() - t0
    except subprocess.TimeoutExpired as e:
        log.write_text(f"TIMEOUT after {timeout}s\n{e.stdout or ''}\n{e.stderr or ''}",
                       encoding="utf-8")
        return False, f"timed out after {timeout}s", time.time() - t0
    except FileNotFoundError as e:
        log.write_text(str(e), encoding="utf-8")
        return False, f"could not start: {e}", time.time() - t0


def _junit(path: Path) -> tuple[int, int, int]:
    """(passed, failed, skipped) from a junit file. A missing file counts as nothing run."""
    if not path.exists():
        return 0, 0, 0
    passed = failed = skipped = 0
    for case in ET.parse(path).getroot().iter("testcase"):
        if case.find("skipped") is not None:
            skipped += 1
        elif case.find("failure") is not None or case.find("error") is not None:
            failed += 1
        else:
            passed += 1
    return passed, failed, skipped


def backend() -> tuple[list[Check], float | None]:
    checks = []
    ok, detail, s = _run("ruff", [PY, "-m", "ruff", "check", "."], ROOT, 120)
    checks.append(Check("backend lint (ruff)", ok, detail, s))

    cov, junit = OUT / "coverage.json", OUT / "pytest.xml"
    for stale in (cov, junit):
        stale.unlink(missing_ok=True)
    ok, detail, s = _run(
        "pytest",
        [PY, "-m", "pytest", "-p", "no:cacheprovider", "--cov=app", "--cov-branch",
         f"--cov-report=json:{cov}", "--cov-fail-under=0", f"--junitxml={junit}"],
        ROOT, 900, env={"WEB_DIR": "/nonexistent", "CC_E2E": "0"})
    passed, failed, _ = _junit(junit)
    checks.append(Check("backend tests (pytest)", ok and failed == 0 and passed > 0,
                        f"{passed} passed, {failed} failed", s))
    pct = None
    if cov.exists():
        pct = float(json.loads(cov.read_text(encoding="utf-8"))["totals"]["percent_covered"])
    return checks, pct


def frontend() -> tuple[list[Check], float | None]:
    checks = []
    for name, label, args, timeout in (
        ("tsc", "frontend types (tsc --strict)", ["tsc", "--noEmit"], 300),
        ("eslint", "frontend lint (eslint)", ["eslint", ".", "--max-warnings", "0"], 300),
    ):
        ok, detail, s = _run(name, [NPX, *args], WEB, timeout)
        checks.append(Check(label, ok, detail, s))

    summary = WEB / "coverage" / "coverage-summary.json"
    summary.unlink(missing_ok=True)
    ok, detail, s = _run("vitest", [NPX, "vitest", "run", "--coverage"], WEB, 300)
    pct = None
    if summary.exists():
        total = json.loads(summary.read_text(encoding="utf-8"))["total"]
        pct = min(float(total[k]["pct"]) for k in ("lines", "statements", "functions", "branches"))
        detail = "lowest of lines, statements, functions, branches"
    checks.append(Check("frontend tests (vitest)", ok, detail, s))

    ok, detail, s = _run("build", [NPX, "next", "build"], WEB, 600)
    pages = [p for p in ("index.html", "workspace/index.html", "demo/index.html",
                         "guide/index.html") if (WEB / "out" / p).exists()]
    checks.append(Check("frontend build (next export)", ok and len(pages) == 4,
                        f"{len(pages)} of 4 pages exported", s))
    return checks, pct


def browser() -> Check:
    junit = OUT / "e2e.xml"
    junit.unlink(missing_ok=True)
    ok, detail, s = _run(
        "e2e", [PY, "-m", "pytest", "tests/e2e", "-p", "no:cacheprovider", "--no-cov",
                f"--junitxml={junit}"],
        ROOT, 1500, env={"CC_E2E": "1"})
    passed, failed, skipped = _junit(junit)
    ran = passed > 0 and failed == 0 and skipped == 0
    return Check("browser e2e (Chromium, real gates)", ok and ran,
                 f"{passed} passed, {failed} failed, {skipped} skipped", s)


def render(checks: list[Check], be: float | None, fe: float | None) -> tuple[str, bool]:
    def pct(v: float | None) -> str:
        return "not measured" if v is None else f"{v:.2f}%"

    measured = be is not None and fe is not None
    score = min(be, fe) if measured else None
    passed = measured and score >= FLOOR and all(c.ok for c in checks)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip() or "unknown"
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip())
    lines = [
        "# Quality gate",
        "",
        f"Run {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} at commit "
        f"`{sha}`{' plus uncommitted changes' if dirty else ''}.",
        "",
        f"**Quality score: {pct(score)}** (floor {FLOOR:.0f}%). "
        f"**Verdict: {'PASS' if passed else 'FAIL'}.**",
        "",
        "| Coverage | Measured | Floor | |",
        "|---|---|---|---|",
        f"| Backend, `app/` line and branch | {pct(be)} | {FLOOR:.0f}% | "
        f"{'pass' if be is not None and be >= FLOOR else 'FAIL'} |",
        f"| Frontend, `web/lib/` lowest metric | {pct(fe)} | {FLOOR:.0f}% | "
        f"{'pass' if fe is not None and fe >= FLOOR else 'FAIL'} |",
        "",
        "| Check | Result | Detail | Time |",
        "|---|---|---|---|",
        *[f"| {c.name} | {'pass' if c.ok else 'FAIL'} | {c.detail} | {c.seconds:.0f}s |"
          for c in checks],
        "",
        "The score is the lowest coverage, not an average. Every check must pass and a "
        "check that did not run counts as a failure. Logs: `data/local/gate/`.",
    ]
    return "\n".join(lines) + "\n", passed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--report", help="also write the table to this markdown file")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    b_checks, be = backend()
    f_checks, fe = frontend()
    # The browser suite needs the build the frontend step just produced.
    built = f_checks[-1].ok
    e2e = browser() if built else Check("browser e2e (Chromium, real gates)", False,
                                        "not run: the frontend build failed", 0.0)
    text, passed = render([*b_checks, *f_checks, e2e], be, fe)
    print(text)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(text, encoding="utf-8", newline="\n")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
