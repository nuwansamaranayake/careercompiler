"""Browser e2e: the built frontend against scripts/e2e_server.py, in real Chromium.

Opt-in with CC_E2E=1, because it needs things a plain `pytest` does not have: the built
frontend (web/out), the pinned entailment weights on disk (HF_HOME), and a browser.
scripts/quality_gate.py sets the flag and treats a skip as a failure, so the gate can
never pass on a suite that did not run.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
ENABLED = os.environ.get("CC_E2E") == "1"


def pytest_collection_modifyitems(config, items):
    if ENABLED:
        return
    skip = pytest.mark.skip(reason="browser e2e is opt-in: CC_E2E=1 (see tests/e2e/conftest.py)")
    for item in items:
        if "e2e" in Path(str(item.fspath)).parts:
            item.add_marker(skip)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url(tmp_path_factory) -> str:
    if not (ROOT / "web" / "out" / "workspace" / "index.html").exists():
        pytest.fail("web/out is not built: run `npm run build` in web/ first")
    port = _free_port()
    db = tmp_path_factory.mktemp("e2e") / "e2e.sqlite"
    log = (tmp_path_factory.mktemp("e2e-log") / "server.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "e2e_server.py"),
         "--port", str(port), "--db", str(db)],
        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 90
        while True:
            if proc.poll() is not None:
                pytest.fail(f"e2e server exited early; see {log.name}")
            try:
                if httpx.get(f"{url}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.time() > deadline:
                pytest.fail(f"e2e server did not become healthy in 90s; see {log.name}")
            time.sleep(0.5)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import expect, sync_playwright
    # Assertions wait as long as actions do: the first compile loads the entailment model.
    expect.set_options(timeout=120_000)
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture()
def page(browser, base_url):
    ctx = browser.new_context(base_url=base_url, viewport={"width": 1280, "height": 900},
                              accept_downloads=True)
    # The first compile loads the entailment model (about 30 s on a laptop CPU).
    ctx.set_default_timeout(120_000)
    pg = ctx.new_page()
    problems: list[str] = []
    pg.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    pg.on("console", lambda m: problems.append(f"console.{m.type}: {m.text}")
          if m.type == "error" else None)
    pg.problems = problems
    yield pg
    ctx.close()
