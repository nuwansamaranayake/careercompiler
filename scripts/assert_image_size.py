"""Fail the pipeline when the image outgrows its budget — at 1.9 GB, not at the 2.0 ceiling.

The first torch build measured 1.99 GB against a 2.0 GB limit. That is a pass by 10 MB,
which is measurement noise, not headroom: any torch or transformers patch release crosses
it, and the discovery would happen during a deploy to the box that serves a paying product.
Asserting at 1.9 turns the next size creep into a red CI run instead of a wall.

Usage: python scripts/assert_image_size.py IMAGE [--max-gb 1.9]
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--max-gb", type=float, default=1.9)
    args = ap.parse_args()

    out = subprocess.run(
        ["docker", "image", "inspect", args.image, "--format", "{{.Size}}"],
        capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        print(f"cannot inspect {args.image}: {out.stderr.strip()[:200]}", file=sys.stderr)
        return 2

    gb = int(out.stdout.strip()) / 1e9
    print(f"{args.image}: {gb:.2f} GB (assertion fires above {args.max_gb:.1f} GB; "
          f"hard ceiling 2.0 GB per DECISIONS.md 003)")
    if gb > args.max_gb:
        print(f"IMAGE SIZE ASSERTION FAILED: {gb:.2f} GB > {args.max_gb:.1f} GB. "
              "See DECISIONS.md 003 for what is prunable and why the margin exists.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
