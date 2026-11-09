import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from groundwork import Env
from .config import settings
from .fixtures import load_synthetic_fixture
from .frontpage import build_version, render as render_front_page
from .routes import router

app = FastAPI(title="CareerCompiler", version=build_version())
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.app_env.value}


@app.get("/api/v1/demo")
def demo():
    # Fixture data is allowed only in development. Standard 3: fail loud elsewhere.
    if settings.app_env is not Env.development:
        raise HTTPException(status_code=503, detail="demo fixture disabled outside development")
    items = load_synthetic_fixture()
    if not items:
        raise HTTPException(status_code=500, detail="synthetic fixture is empty")
    return {"items": items}

# The front door. Public by design: a browser must get a page, not a 404. When the built
# frontend is present (the image bakes it at /srv/web) it IS the front door; without it —
# a source checkout, the test suite — the legacy single-file page serves. Both carry the
# EVAL.md limits block verbatim, and the deploy gate asserts that against whatever is live.
_WEB = Path(os.getenv("WEB_DIR", "/srv/web"))
_MOUNTED_DIRS = ("_next", "assets")
_HTML = "text/html; charset=utf-8"


def mount_frontend(app: FastAPI, web: Path) -> bool:
    """Serve the static export file by file. Returns False when there is no build.

    The routes come from one directory listing taken at startup, so no request path is
    ever joined to the filesystem: a URL that is not a built file is a 404 by
    construction. A page `x/index.html` answers at `/x` and `/x/`. Routes registered
    before this call (the API, /health) win, so a build can never shadow them.
    """
    if not (web / "index.html").exists():
        return False
    for name in _MOUNTED_DIRS:
        if (web / name).is_dir():
            app.mount(f"/{name}", StaticFiles(directory=web / name), name=f"web-{name}")

    def serve(url: str, path: Path, media_type: str | None) -> None:
        app.add_api_route(
            url, lambda: FileResponse(path, media_type=media_type),
            methods=["GET"], include_in_schema=False)

    for path in sorted(p for p in web.rglob("*") if p.is_file()):
        rel = path.relative_to(web)
        if rel.parts[0] in _MOUNTED_DIRS:
            continue
        if rel.name == "index.html":
            page = "/".join(rel.parts[:-1])
            serve(f"/{page}", path, _HTML)
            if page:
                serve(f"/{page}/", path, _HTML)
        else:
            serve("/" + rel.as_posix(), path, _HTML if path.suffix == ".html" else None)
    return True


if not mount_frontend(app, _WEB):
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def root() -> HTMLResponse:
        return HTMLResponse(content=render_front_page(),
                            media_type="text/html; charset=utf-8")
