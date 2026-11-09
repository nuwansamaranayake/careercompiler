"""Single-behaviour gaps across the small modules."""
from __future__ import annotations

import json
import runpy

import pytest
import sqlalchemy as sa
import redis as redis_lib
from fastapi.testclient import TestClient
from groundwork import Env

from app import db, demo, fixtures, main
from app.config import settings
from app.engine import entailment, linker
from app.engine.embedding import HashingEmbedder
from app.engine.facts import claims_from_entries, extract_facts
from app.engine.fit import build_report, render_markdown
from app.engine.jd import Requirement, parse_jd
from app.engine.linker import Bullet
from app.engine.matcher import match
from app.engine.selector import select


class Gateway:
    def __init__(self, result):
        self.result = result

    def complete(self, *, model, messages, json_schema=None, temperature=0.0):
        return self.result


def _claims():
    return claims_from_entries([
        {"claim_key": "lead", "kind": "role", "statement": "Led a team of 4 engineers."}])


# ---- engine ------------------------------------------------------------------------

def test_extract_facts_accepts_a_bare_array():
    resume = "Led a team of 4 engineers at Acme."
    gw = Gateway([{"claim_key": "lead", "kind": "role", "statement": "Led a team of 4",
                   "quote": "Led a team of 4 engineers", "confidence": 0.9}])
    [c] = extract_facts(gw, "m", resume, "resume.txt")
    assert c.claim_key == "lead"
    assert c.core.verification.status == "pending"
    assert c.core.evidence_ref.span == (0, len("Led a team of 4 engineers"))


def test_parse_jd_refuses_without_model():
    with pytest.raises(RuntimeError, match="LLM_MODEL_EXTRACTION"):
        parse_jd(Gateway({}), "", "text")


def test_match_with_no_requirements_returns_no_rows():
    assert match([], _claims(), HashingEmbedder()) == []


def test_render_markdown_appends_contract_note():
    reqs = [Requirement(req_key="lead", text="Led a team of 4 engineers", kind="experience",
                        must_have=True)]
    report = build_report(match(reqs, _claims(), HashingEmbedder()))
    plain = render_markdown(report)
    noted = render_markdown(report, "Contract: see EVAL.md.")
    assert "Contract: see EVAL.md." not in plain
    assert noted.endswith("\nContract: see EVAL.md.\n")
    assert noted.startswith(plain.rstrip("\n"))


def test_gate_report_raise_if_broken():
    ok = entailment.GateReport()
    assert ok.ok and ok.raise_if_broken() is None
    bad = entailment.GateReport(violations=[entailment.EntailmentViolation(
        bullet_index=0, text="Directed everything.", premise="Led 4.", entailment=0.01,
        threshold=0.5)])
    assert not bad.ok
    with pytest.raises(entailment.EntailmentError, match="1 sentence.*outran.*0.01"):
        bad.raise_if_broken()


def test_gate_skips_bullets_whose_citations_resolve_to_nothing():
    claims = _claims()
    calls = []

    def scorer(p, h):
        calls.append((p, h))
        return 0.9

    report = entailment.gate(
        [Bullet("Orphan.", ["nope"]), Bullet(" I led 4. ", [claims[0].core.claim_id])],
        claims, 0.5, "m", "r", scorer=scorer)
    assert calls == [("Led a team of 4 engineers.", "I led 4.")]
    assert report.scored == [(1, 0.9)]
    assert report.ok


def test_link_report_raise_if_broken_and_sentence_split():
    assert linker.LinkReport().raise_if_broken() is None
    claims = _claims()
    rep = linker.check([Bullet("No cites.", [])], claims, selected_ids=None)
    assert not rep.ok
    with pytest.raises(linker.ReferenceIntegrityError):
        rep.raise_if_broken()
    assert linker.sentences("One. Two!  Three? tail") == ["One.", "Two!", "Three?", "tail"]


def test_select_rejects_negative_budget():
    with pytest.raises(ValueError, match="must not be negative"):
        select(_claims(), [], [], -1)


# ---- fixtures, db, demo wiring -----------------------------------------------------

def test_fixture_loader_fails_loud(tmp_path, monkeypatch):
    monkeypatch.setattr(fixtures, "_DEMO", tmp_path / "missing.json")
    with pytest.raises(NotImplementedError, match="Synthetic demo dataset not found"):
        fixtures.load_synthetic_fixture()
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    monkeypatch.setattr(fixtures, "_DEMO", bad)
    with pytest.raises(ValueError, match="JSON array"):
        fixtures.load_synthetic_fixture()
    good = tmp_path / "good.json"
    good.write_text(json.dumps([{"a": 1}]), encoding="utf-8")
    monkeypatch.setattr(fixtures, "_DEMO", good)
    assert fixtures.load_synthetic_fixture() == [{"a": 1}]


def test_get_engine_builds_from_settings_once_and_hands_out_sessions(monkeypatch):
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_Session", None)
    monkeypatch.setattr(settings, "database_url", "sqlite://")
    e = db.get_engine()
    assert e.url.drivername == "sqlite"
    assert db.get_engine() is e
    with db.get_session() as s:
        assert s.execute(sa.text("select 1")).scalar() == 1


def test_get_redis_builds_a_client_from_settings_and_caches_it(monkeypatch):
    monkeypatch.setattr(demo, "_client", None)
    monkeypatch.setattr(demo, "_kit", None)
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6399/3")
    c = demo.get_redis()
    assert isinstance(c, redis_lib.Redis)
    assert c.connection_pool.connection_kwargs["db"] == 3
    assert demo.get_redis() is c


# ---- main --------------------------------------------------------------------------

def test_demo_endpoint_is_disabled_outside_development(monkeypatch):
    monkeypatch.setattr(settings, "app_env", Env.production)
    r = TestClient(main.app).get("/api/v1/demo")
    assert r.status_code == 503
    assert r.json()["detail"] == "demo fixture disabled outside development"


def test_demo_endpoint_empty_fixture_is_500(monkeypatch):
    monkeypatch.setattr(settings, "app_env", Env.development)
    monkeypatch.setattr(main, "load_synthetic_fixture", lambda: [])
    r = TestClient(main.app).get("/api/v1/demo")
    assert r.status_code == 500
    assert r.json()["detail"] == "synthetic fixture is empty"


def test_module_with_a_built_frontend_serves_it_instead_of_the_legacy_page(
        tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>built front door</html>", encoding="utf-8")
    monkeypatch.setenv("WEB_DIR", str(tmp_path))
    ns = runpy.run_module("app.main", run_name="app_main_with_web")
    client = TestClient(ns["app"])
    r = client.get("/")
    assert r.status_code == 200
    assert r.text == "<html>built front door</html>"
    assert client.get("/health").json()["status"] == "ok"
    # no assets or _next directory in this build, so nothing is mounted under them
    assert client.get("/assets/x.js").status_code == 404
