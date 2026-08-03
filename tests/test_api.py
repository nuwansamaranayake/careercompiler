import json
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app import db, frontpage
from app.main import app

GOLDEN = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "synthetic" / "golden" /
     "golden.json").read_text(encoding="utf-8"))


@pytest.fixture()
def client():
    engine = sa.create_engine(
        "sqlite://",
        poolclass=sa.pool.StaticPool,
        connect_args={"check_same_thread": False},   # TestClient serves on another thread
    )
    db.metadata.create_all(engine)
    db.set_engine_for_tests(engine)
    return TestClient(app)


def _seed(client):
    cid = client.post("/api/v1/candidates",
                      json={"name": "T"}).json()["candidate_id"]
    client.post(f"/api/v1/candidates/{cid}/claims",
                json={"entries": GOLDEN["fact_graph"]})
    jid = client.post("/api/v1/jobs", json={
        "title": "Role", "requirements": GOLDEN["cases"][0]["requirements"]
    }).json()["job_id"]
    return cid, jid


def test_full_fit_loop(client):
    cid, jid = _seed(client)
    r = client.post("/api/v1/fit", json={"candidate_id": cid, "job_id": jid})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["verdict"] == "apply"
    full = client.get(f"/api/v1/fit/{body['fit_report_id']}").json()
    assert len(full["rows"]) == 4
    assert full["report"]["embedder"] == "hashing"


def test_fit_requires_claims_and_requirements(client):
    cid = client.post("/api/v1/candidates", json={"name": "T"}).json()["candidate_id"]
    jid = client.post("/api/v1/jobs", json={"title": "R"}).json()["job_id"]
    r = client.post("/api/v1/fit", json={"candidate_id": cid, "job_id": jid})
    assert r.status_code == 422


def test_extract_without_key_fails_loud(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    cid = client.post("/api/v1/candidates",
                      json={"name": "T", "resume_text": "x"}).json()["candidate_id"]
    r = client.post(f"/api/v1/candidates/{cid}/claims/extract")
    assert r.status_code == 503
    assert "OPENROUTER_API_KEY" in r.json()["detail"]


def test_bearer_auth_enforced_when_token_set(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "smoke_test_token", "sekrit")
    assert client.post("/api/v1/candidates", json={"name": "T"}).status_code == 401
    assert client.post("/api/v1/candidates", json={"name": "T"},
                       headers={"Authorization": "Bearer sekrit"}).status_code == 201


def test_get_fit_requires_bearer_when_token_set(client, monkeypatch):
    from app.config import settings
    cid, jid = _seed(client)
    rid = client.post("/api/v1/fit",
                      json={"candidate_id": cid, "job_id": jid}).json()["fit_report_id"]
    monkeypatch.setattr(settings, "smoke_test_token", "sekrit")
    assert client.get(f"/api/v1/fit/{rid}").status_code == 401
    assert client.get(f"/api/v1/fit/{rid}",
                      headers={"Authorization": "Bearer sekrit"}).status_code == 200


def test_fit_openrouter_embedder_without_key_is_typed_503(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    cid, jid = _seed(client)
    r = client.post("/api/v1/fit",
                    json={"candidate_id": cid, "job_id": jid, "embedder": "openrouter"})
    assert r.status_code == 503
    assert "OPENROUTER_API_KEY" in r.json()["detail"]


def test_extract_llm_call_runs_outside_db_transaction(client, monkeypatch):
    """The gateway call must never run inside an open session/transaction: a slow model
    would hold a pooled connection for its whole duration (the F4 review finding)."""
    from app import routes
    from app.engine.facts import claims_from_entries

    monkeypatch.setattr(routes, "_gateway", lambda: object())
    opened = []
    real_get_session = db.get_session

    def tracking_get_session():
        s = real_get_session()
        opened.append(s)
        return s

    monkeypatch.setattr(db, "get_session", tracking_get_session)

    def fake_extract(gateway, model, resume_text, source_name):
        in_tx = [s for s in opened if s.in_transaction()]
        assert not in_tx, "LLM call ran inside an open DB transaction"
        return claims_from_entries(
            [{"claim_key": "skill_python", "kind": "skill", "statement": "Python"}],
            source_name=source_name)

    monkeypatch.setattr(routes, "extract_facts", fake_extract)
    cid = client.post("/api/v1/candidates",
                      json={"name": "T", "resume_text": "Python"}).json()["candidate_id"]
    r = client.post(f"/api/v1/candidates/{cid}/claims/extract")
    assert r.status_code == 201, r.text
    assert r.json()["stored"] == 1


def test_gateway_client_is_time_bounded(monkeypatch):
    from app import routes
    from app.config import settings
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 12.5)
    monkeypatch.setattr(settings, "llm_max_retries", 1)
    gw = routes._gateway()
    assert gw._client.timeout == 12.5
    assert gw._client.max_retries == 1


def test_malformed_claims_rejected(client):
    cid = client.post("/api/v1/candidates", json={"name": "T"}).json()["candidate_id"]
    r = client.post(f"/api/v1/candidates/{cid}/claims",
                    json={"entries": [{"statement": "no key"}]})
    assert r.status_code == 422


def test_root_serves_a_real_html_page(client):
    """The front door must answer a browser. Every gate passed for hours while this 404ed."""
    r = client.get("/", headers={"Accept": "text/html"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    body = r.text
    assert len(body) > 500
    assert "CareerCompiler" in body
    for placeholder in ("TODO", "Lorem", "example.com", "XXX"):
        assert placeholder not in body


def test_root_publishes_the_eval_limits_sentence_verbatim():
    """The page quotes EVAL.md, so the two cannot drift apart silently."""
    import re
    from pathlib import Path
    from app.frontpage import render

    eval_md = (Path(__file__).resolve().parent.parent / "EVAL.md").read_text(encoding="utf-8")
    limits = " ".join(re.search(r"<!-- LIMITS -->\s*(.+?)\s*<!-- /LIMITS -->",
                                eval_md, re.S).group(1).split())
    assert limits in " ".join(render().split())


def test_root_reports_unknown_rather_than_a_fake_build_stamp(monkeypatch):
    """No build args means "unknown" on the page, never a plausible-looking placeholder."""
    from app import frontpage
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("APP_VERSION", raising=False)
    frontpage._template.cache_clear()
    body = frontpage.render()
    assert "unknown" in body and "__SHA__" not in body and "__VERSION__" not in body


def test_openapi_version_matches_the_version_the_front_page_renders(client):
    """A1: one version, one source.

    The served schema reported 0.1.0 (the FastAPI default, because no version was passed)
    while the front page reported the deployed tag. A schema that is wrong about its own
    version has not earned trust about anything else in it.
    """
    html = client.get("/").text
    m = re.search(r"version <code>([^<]+)</code>", html)
    assert m, "the front page no longer renders a version; this test needs updating"
    rendered = m.group(1)

    spec_version = client.get("/openapi.json").json()["info"]["version"]
    assert spec_version == rendered, (
        f"openapi.json says {spec_version!r} but the front page says {rendered!r}; "
        "they must come from the same source")


def test_build_version_is_read_from_the_environment(monkeypatch):
    """Equality alone would pass if both sources were hardcoded to the same wrong string.
    This proves the shared helper actually reflects the build argument."""
    monkeypatch.setenv("APP_VERSION", "9.9.9-test")
    assert frontpage.build_version() == "9.9.9-test"
    monkeypatch.delenv("APP_VERSION")
    assert frontpage.build_version() == "unreleased"


def test_shared_version_assertion_holds(client):
    """A3: the estate-wide check, via the shared helper rather than a drifting copy."""
    from groundwork.testing import assert_served_version_matches_front_page
    assert_served_version_matches_front_page(client)
