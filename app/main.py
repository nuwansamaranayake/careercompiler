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

if (_WEB / "index.html").exists():
    app.mount("/_next", StaticFiles(directory=_WEB / "_next"), name="next-assets")

    @app.get("/", include_in_schema=False)
    def root() -> FileResponse:
        return FileResponse(_WEB / "index.html", media_type="text/html; charset=utf-8")

    @app.get("/demo", include_in_schema=False)
    @app.get("/demo/", include_in_schema=False)
    def demo_page() -> FileResponse:
        return FileResponse(_WEB / "demo" / "index.html",
                            media_type="text/html; charset=utf-8")
else:
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def root() -> HTMLResponse:
        return HTMLResponse(content=render_front_page(),
                            media_type="text/html; charset=utf-8")
