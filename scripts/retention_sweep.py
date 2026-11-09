"""The daily retention sweep, runnable on its own on the production host.

    python3 scripts/retention_sweep.py --retention-module /opt/aignite-portfolio/portfolio-ops/scripts/retention.py

The site tells people their session data is deleted once it is older than 7 days. Until
2026-11-09 that deletion only happened inside the estate smoke, which a person had to
run, and production was found holding tenants two months old. This script is the sweep
with nothing else attached: no HTTP, no model call, no SSH. It talks to the database
container on the same machine and is meant for cron.

The rules are not restated here. They live in portfolio-ops `retention.py` (delete by
namespace prefix, child rows first, raise when aged namespaces exist and nothing was
deleted), and this script loads that file and calls `run_retention`. One implementation,
two callers.

Every run appends one line to the log, pass or fail. Exit 0 = swept or nothing to sweep;
1 = the sweep refused or broke (the line says why); 2 = it could not start.
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = "careercompiler"


def load_retention(path: Path):
    spec = importlib.util.spec_from_file_location("retention", path)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(f"cannot load the retention rules from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def psql(container: str, db: str, user: str, statement: str, run=subprocess.run) -> str:
    out = run(["docker", "exec", container, "psql", "-U", user, "-d", db, "-tAc", statement],
              capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(f"psql failed: {out.stderr.strip()[:200]}")
    return out.stdout.strip()


def deleted_rows(output: str) -> int:
    """psql answers a delete with 'DELETE n'. Anything else deleted nothing we can count."""
    return int(output.rsplit(" ", 1)[-1]) if output.startswith("DELETE") else 0


def sweep(retention, query, now: datetime | None = None) -> dict:
    return retention.run_retention(APP, query, lambda s: deleted_rows(query(s)), now=now)


def main(argv: list[str] | None = None, run=subprocess.run) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--retention-module", required=True, type=Path)
    ap.add_argument("--container", default="careercompiler-db-1")
    ap.add_argument("--db", default="career_compiler")
    ap.add_argument("--user", default="aignite")
    ap.add_argument("--log", type=Path, default=None, help="append one line per run here")
    args = ap.parse_args(argv)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        retention = load_retention(args.retention_module)
    except Exception as e:
        line, code = f"{stamp} {APP} CANNOT START: {type(e).__name__}: {e}", 2
    else:
        try:
            result = sweep(retention, lambda s: psql(args.container, args.db, args.user, s, run))
            line, code = (f"{stamp} {APP} OK aged_namespaces={result['aged_namespaces']} "
                          f"deleted={result['deleted']} remaining={result['remaining']}"), 0
        except Exception as e:
            line, code = f"{stamp} {APP} FAILED: {type(e).__name__}: {str(e)[:300]}", 1

    print(line)
    if args.log:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        with args.log.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
