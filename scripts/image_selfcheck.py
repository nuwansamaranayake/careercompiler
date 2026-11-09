"""Run INSIDE the built image, with no network: is this image what the release claims?

    docker run --rm --network none --entrypoint python IMAGE scripts/image_selfcheck.py

Checks, each of which has failed or could fail silently in this project's history:
  * git is gone (it is a build tool here, removed in the layer that used it)
  * torch is the CPU build
  * the pinned entailment checkpoint loads offline and separates a faithful sentence
    from an overstated one
  * the built frontend is in the image and every page and guide picture is served
  * the landing page carries the EVAL.md limits sentence verbatim
  * a business read without a token is still 401

No database, no Redis, no key: none of these checks needs one. Exit 0 only if all pass.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SMOKE_TEST_TOKEN", "selfcheck-token")

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not ok:
        failures.append(name)


def main() -> int:
    check("git is not in the image", shutil.which("git") is None)

    import torch
    check("torch is the CPU build", torch.version.cuda is None, torch.__version__)

    from app.config import settings
    from app.engine import entailment
    score = entailment.load_scorer(settings.nli_model, settings.nli_model_revision)
    fact = "Led a team of 4 engineers at Acme Corp from 2019 to 2022."
    faithful = score(fact, "Led a team of 4 engineers at Acme Corp.")
    inflated = score(fact, "Directed the entire engineering organisation. " + fact)
    check("entailment model loads offline and separates faithful from overstated",
          faithful >= settings.nli_entail_threshold > inflated,
          f"faithful {faithful:.4f}, overstated {inflated:.4f}, "
          f"threshold {settings.nli_entail_threshold}")
    over = score(fact, " ".join(["Led a team of 4 engineers."] * 200))
    check("a sentence longer than the model's window scores zero", over == 0.0, f"{over}")

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    for page in ("/", "/workspace/", "/demo/", "/guide/"):
        r = client.get(page)
        check(f"page {page}", r.status_code == 200 and "<!DOCTYPE html>" in r.text[:40],
              f"HTTP {r.status_code}")

    guide = client.get("/guide/").text
    shots = sorted(set(re.findall(r"/assets/guide/[\w.-]+\.webp", guide)))
    got = {s: client.get(s) for s in shots}
    missing = [s for s, r in got.items() if r.status_code != 200]
    check("guide pictures are served", len(shots) == 15 and not missing,
          f"{len(shots)} referenced, {len(missing)} missing")
    # The slim base image ships no system MIME table, so Python guesses nothing for
    # .webp and the first production deploy served the pictures as octet-stream.
    types = sorted({r.headers.get("content-type", "") for r in got.values()})
    check("guide pictures are served as image/webp", types == ["image/webp"], str(types))
    web = Path(os.environ.get("WEB_DIR", "/srv/web"))
    fonts = sorted(p.relative_to(web).as_posix() for p in web.rglob("*.woff2"))
    font_types = sorted({client.get("/" + f).headers.get("content-type", "") for f in fonts[:5]})
    check("fonts are served as font/woff2", bool(fonts) and font_types == ["font/woff2"],
          f"{len(fonts)} shipped, types {font_types}")

    limits = re.search(r"<!-- LIMITS -->\s*(.+?)\s*<!-- /LIMITS -->",
                       (ROOT / "EVAL.md").read_text(encoding="utf-8"), re.S)
    on_page = bool(limits) and " ".join(limits.group(1).split()) in " ".join(
        client.get("/").text.split())
    check("landing page carries the EVAL.md limits sentence verbatim", on_page)

    check("a business read without a token is 401",
          client.get("/api/v1/fit/1").status_code == 401)
    check("health", client.get("/health").json().get("status") == "ok")

    print(f"\nIMAGE SELFCHECK: {'PASS' if not failures else 'FAIL ' + str(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
