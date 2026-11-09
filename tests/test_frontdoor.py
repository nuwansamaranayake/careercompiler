"""The built frontend is served file by file, enumerated at startup.

No request path ever reaches the filesystem: the routes are registered from a directory
listing taken once, so a path that is not a built file is a 404 by construction, and
traversal has nothing to traverse.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import mount_frontend


def _site(tmp_path):
    (tmp_path / "_next" / "static").mkdir(parents=True)
    (tmp_path / "_next" / "static" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "assets" / "guide").mkdir(parents=True)
    (tmp_path / "assets" / "guide" / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "index.html").write_text("<h1>landing</h1>", encoding="utf-8")
    (tmp_path / "index.txt").write_text("rsc-root", encoding="utf-8")
    (tmp_path / "404.html").write_text("<h1>missing</h1>", encoding="utf-8")
    (tmp_path / "icon.svg").write_text("<svg/>", encoding="utf-8")
    for page in ("workspace", "guide", "demo"):
        (tmp_path / page).mkdir()
        (tmp_path / page / "index.html").write_text(f"<h1>{page}</h1>", encoding="utf-8")
        (tmp_path / page / "index.txt").write_text(f"rsc-{page}", encoding="utf-8")
    return tmp_path


def _client(web) -> TestClient:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    assert mount_frontend(app, web) is True
    return TestClient(app)


def test_every_built_page_is_served_with_and_without_the_trailing_slash(tmp_path):
    c = _client(_site(tmp_path))
    assert "landing" in c.get("/").text
    for page in ("workspace", "guide", "demo"):
        for url in (f"/{page}", f"/{page}/"):
            r = c.get(url)
            assert r.status_code == 200, url
            assert f"<h1>{page}</h1>" in r.text
            assert r.headers["content-type"] == "text/html; charset=utf-8"


def test_build_assets_images_and_root_files_are_served(tmp_path):
    c = _client(_site(tmp_path))
    assert c.get("/_next/static/app.js").text == "console.log(1)"
    shot = c.get("/assets/guide/shot.png")
    assert shot.status_code == 200 and shot.headers["content-type"] == "image/png"
    assert c.get("/icon.svg").headers["content-type"].startswith("image/svg+xml")
    assert c.get("/workspace/index.txt").text == "rsc-workspace"
    assert c.get("/index.txt").text == "rsc-root"


def test_unbuilt_pages_and_traversal_are_404(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("never served", encoding="utf-8")
    web = tmp_path / "site"
    web.mkdir()
    c = _client(_site(web))
    assert c.get("/nope").status_code == 404
    assert c.get("/nope/").status_code == 404
    assert c.get("/workspace/../../secret.txt").status_code == 404
    assert c.get("/%2e%2e/secret.txt").status_code == 404
    assert c.get("/assets/../../secret.txt").status_code == 404


def test_the_frontend_never_shadows_an_api_route(tmp_path):
    web = _site(tmp_path)
    (web / "health").mkdir()
    (web / "health" / "index.html").write_text("<h1>shadow</h1>", encoding="utf-8")
    c = _client(web)
    assert c.get("/health").json() == {"status": "ok"}


def test_without_a_build_nothing_is_mounted(tmp_path):
    app = FastAPI()
    assert mount_frontend(app, tmp_path) is False
    assert TestClient(app).get("/").status_code == 404
