from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
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

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root() -> HTMLResponse:
    """The front door. Public by design: a browser must get a page, not a 404."""
    return HTMLResponse(content=render_front_page(),
                        media_type="text/html; charset=utf-8")
