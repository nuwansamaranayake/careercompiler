"""Capture the visual guide's screenshots, and print the guide to PDF.

    python scripts/capture_guide.py            # screenshots -> web/public/assets/guide/
    python scripts/capture_guide.py --pdf      # also docs/guide/CareerCompiler-Visual-Guide.pdf

Drives the built frontend in Chromium against scripts/e2e_server.py, so every picture is
the real interface with the real gates, on the synthetic inputs in tests/e2e/samples.py.
The guide page says so beside the pictures. Rebuild the frontend after capturing: the
static export copies web/public into web/out.

The PDF is printed from the guide page itself, so the two can never drift apart.
"""
from __future__ import annotations

import argparse
import io
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
from PIL import Image
from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.e2e import samples  # noqa: E402

SHOTS = ROOT / "web" / "public" / "assets" / "guide"
PDF = ROOT / "docs" / "guide" / "CareerCompiler-Visual-Guide.pdf"
PAD = 20


def _serve() -> tuple[subprocess.Popen, str]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "e2e_server.py"), "--port", str(port),
         "--db", str(ROOT / "data" / "local" / "guide-capture.sqlite")], cwd=ROOT)
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 90
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit("e2e server exited before becoming healthy")
        try:
            if httpx.get(f"{url}/health", timeout=2).status_code == 200:
                return proc, url
        except httpx.HTTPError:
            time.sleep(0.5)
    proc.kill()
    raise SystemExit("e2e server did not become healthy in 90s")


def _shoot(page: Page, name: str, *selectors: str) -> None:
    """One picture of the union of the given elements (or the main column), padded so
    the desk shows around the paper. WebP keeps fifteen pictures under a megabyte."""
    box = page.evaluate(
        """(sels) => {
             const els = sels.length ? sels.map((s) => document.querySelector(s)) : [document.querySelector('main')];
             const rs = els.filter(Boolean).map((e) => e.getBoundingClientRect());
             const l = Math.min(...rs.map((r) => r.left)), t = Math.min(...rs.map((r) => r.top));
             const r = Math.max(...rs.map((r) => r.right)), b = Math.max(...rs.map((r) => r.bottom));
             return {x: l + scrollX, y: t + scrollY, width: r - l, height: b - t};
           }""", list(selectors))
    clip = {"x": max(0, box["x"] - PAD), "y": max(0, box["y"] - PAD),
            "width": box["width"] + 2 * PAD, "height": box["height"] + 2 * PAD}
    png = page.screenshot(full_page=True, clip=clip, animations="disabled")
    out = SHOTS / f"{name}.webp"
    Image.open(io.BytesIO(png)).save(out, "WEBP", quality=84, method=6)
    print(f"  {out.name:34s} {out.stat().st_size // 1024:4d} KB")


def _tid(test_id: str) -> str:
    return f'[data-testid="{test_id}"]'


def _fill(page: Page, job: str) -> None:
    page.goto("/workspace/")
    page.get_by_test_id("resume-paste-tab").click()
    page.get_by_test_id("resume-text").fill(samples.RESUME)
    page.get_by_test_id("job-title").fill(samples.JOB_TITLE)
    page.get_by_test_id("job-text").fill(job)
    # fill() leaves a textarea scrolled to its end; the picture should show the start.
    page.evaluate("document.querySelectorAll('textarea').forEach((t) => { t.scrollTop = 0; })")
    page.mouse.move(0, 0)


def capture(page: Page) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)

    page.goto("/workspace/")
    _shoot(page, "01-intake-empty")
    _fill(page, samples.JOB)
    _shoot(page, "02-intake-filled")

    # Hold the last request so the build log can be photographed mid-run: five steps
    # done, the sixth running. Nothing is faked; the request is released right after.
    held = []
    page.route("**/api/v1/fit", lambda route: held.append(route))
    page.get_by_test_id("analyze").click()
    expect(page.locator('li[data-step="match"]')).to_have_attribute("data-state", "running")
    _shoot(page, "03-build-log")
    held[0].continue_()
    page.unroute("**/api/v1/fit")

    expect(page.get_by_test_id("verdict-stamp")).to_have_attribute("data-verdict", "apply")
    expect(page.get_by_test_id("fit-table")).to_be_visible()
    _shoot(page, "04-verdict-apply", _tid("verdict"))
    _shoot(page, "05-match-table", ".tabs", "#panel-match")

    page.get_by_test_id("tab-resume").click()
    _shoot(page, "07-resume-start", ".tabs", "#panel-resume")
    page.get_by_test_id("compile-resume").click()
    expect(page.get_by_test_id("resume-sheet")).to_be_visible()
    _shoot(page, "08-resume-sheet", "#panel-resume")
    page.get_by_test_id("resume-line-0").click()
    expect(page.get_by_test_id("line-editor")).to_be_visible()
    _shoot(page, "09-line-evidence", "#panel-resume")
    page.get_by_test_id("overstate").click()
    expect(page.get_by_test_id("gate-verdict")).to_have_attribute("data-ok", "false")
    _shoot(page, "10-edit-rejected", "#panel-resume")
    page.get_by_test_id("edit-text").fill(samples.HONEST_EDIT)
    page.get_by_test_id("save-edit").click()
    expect(page.get_by_test_id("edit-saved")).to_be_visible()
    _shoot(page, "11-edit-saved", "#panel-resume")
    _shoot(page, "12-resume-download", "#panel-resume .rail .card")

    page.get_by_test_id("tab-letter").click()
    _shoot(page, "13-letter-start", ".tabs", "#panel-letter")
    page.get_by_test_id("compile-letter").click()
    expect(page.get_by_test_id("letter-sheet")).to_be_visible()
    _shoot(page, "14-letter-sheet", "#panel-letter")
    _shoot(page, "15-letter-download", "#panel-letter .rail .card")

    _fill(page, samples.JOB_WITH_CLEARANCE)
    page.get_by_test_id("analyze").click()
    expect(page.get_by_test_id("verdict-stamp")).to_have_attribute("data-verdict", "do_not_apply")
    expect(page.get_by_test_id("case-against")).to_be_visible()
    _shoot(page, "06-verdict-do-not-apply", _tid("verdict"), _tid("case-against"))


def print_pdf(page: Page) -> None:
    page.goto("/guide/")
    missing = page.evaluate(
        """async () => {
             const imgs = [...document.querySelectorAll('img')];
             imgs.forEach((i) => { i.loading = 'eager'; });
             await Promise.all(imgs.map((i) => i.decode().catch(() => null)));
             return imgs.filter((i) => !i.naturalWidth).map((i) => i.getAttribute('src'));
           }""")
    if missing:
        raise SystemExit(f"guide images missing from the build (rebuild web/ first): {missing}")
    PDF.parent.mkdir(parents=True, exist_ok=True)
    page.pdf(path=str(PDF), format="Letter", print_background=True,
             margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"})
    print(f"  {PDF.relative_to(ROOT)}  {PDF.stat().st_size // 1024} KB")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pdf", action="store_true", help="print /guide/ to PDF (needs a rebuilt web/out)")
    ap.add_argument("--pdf-only", action="store_true", help="skip the screenshots")
    args = ap.parse_args()

    proc, url = _serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(base_url=url, viewport={"width": 1240, "height": 860},
                                      device_scale_factor=2, color_scheme="light")
            ctx.set_default_timeout(120_000)
            expect.set_options(timeout=120_000)
            page = ctx.new_page()
            if not args.pdf_only:
                print("screenshots:")
                capture(page)
            if args.pdf or args.pdf_only:
                print("pdf:")
                print_pdf(page)
            browser.close()
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
