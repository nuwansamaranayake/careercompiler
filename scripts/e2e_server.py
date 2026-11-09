"""The browser e2e harness: the real app with three named doubles. Development only.

    python scripts/e2e_server.py --port 8765

What is REAL here: every route, the tenancy guard, the matcher, the CP-SAT selector, the
linker, the pinned entailment model, the repair loop, the PDF and docx writers, and the
built frontend (web/out) served exactly as the image serves it.

What is a DOUBLE, and why:
  * Postgres -> a sqlite file. The suite already runs the same schema on sqlite.
  * Redis    -> groundwork.testing.FakeRedis, the double the demo tests use.
  * The LLM  -> ScriptedLLM below. A real model call spends against a paid key, and a
    browser suite that costs money per run stops being run. The script is deterministic
    and deliberately dull: it copies sentences, it never composes any.

This file is never imported by the app and refuses to start outside development. It is
a test fixture with a port, not a mode of the product (Standard 3: no silent fallback
outside development — this one is neither silent nor outside development).

The entailment weights must be on disk: set HF_HOME to a cache holding the revision the
Dockerfile pins (the image bakes it at /opt/hf).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NLI_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
NLI_REVISION = "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"
ESTATE_TOKEN = "e2e-estate-token"

# Set BEFORE the app imports: environment beats a developer's .env, so the real key and
# the real embedding model in that file can never be picked up. The base URL points at a
# closed port so that a call that somehow escaped the script fails instead of spending.
os.environ.update({
    "APP_ENV": "development",
    "OPENROUTER_API_KEY": "e2e-scripted-not-a-key",
    "OPENROUTER_BASE_URL": "http://127.0.0.1:9/never",
    "EMBEDDING_MODEL": "",
    "LLM_MODEL_EXTRACTION": "scripted/extraction",
    "LLM_MODEL_REASONING": "scripted/reasoning",
    "LLM_MODEL_JUDGE": "scripted/judge",
    "SMOKE_TEST_TOKEN": ESTATE_TOKEN,
    "NLI_MODEL": NLI_MODEL,
    "NLI_MODEL_REVISION": NLI_REVISION,
    "HF_HUB_OFFLINE": "1",
    "DEMO_SESSIONS_PER_IP_HOUR": "10000",
})
os.environ.setdefault("WEB_DIR", str(ROOT / "web" / "out"))
os.environ.setdefault("HF_HOME", str(ROOT / "data" / "local" / "hf"))


def _slug(text: str, used: set[str]) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())[:4]
    base = "_".join(words) or "item"
    key, n = base, 2
    while key in used:
        key, n = f"{base}_{n}", n + 1
    used.add(key)
    return key


def _first_person(statement: str) -> str:
    return "I " + statement[:1].lower() + statement[1:]


class ScriptedLLM:
    """Answers the four schemas the engine asks for by copying, never by composing.

    Extraction: every full sentence of the resume becomes one fact whose quote is that
    sentence, so anchoring is exercised for real. Requirements: every list line of the
    posting. Rendering: the fact statement itself (first person for a letter). Questions:
    two fixed questions per id. Nothing here can overstate, so every rejection the
    browser suite sees comes from an edit a person typed, through the real gates.
    """

    def complete(self, *, model: str, messages: list[dict],
                 json_schema: dict | None = None, temperature: float = 0.0, **_):
        name = (json_schema or {}).get("name")
        system, user = messages[0]["content"], messages[-1]["content"]
        if name == "atomic_claims":
            return self._claims(user)
        if name == "requirements":
            return self._requirements(user)
        if name == "fact_renderings":
            return self._renderings(system, json.loads(user))
        if name == "interview_questions":
            return self._questions(json.loads(user))
        raise RuntimeError(f"ScriptedLLM has no script for schema {name!r}")

    @staticmethod
    def _claims(resume: str) -> dict:
        used: set[str] = set()
        claims = []
        for para in resume.split("\n"):
            for sentence in re.split(r"(?<=\.)\s+", para.strip()):
                if len(sentence.split()) < 6 or not sentence.endswith("."):
                    continue
                claims.append({
                    "claim_key": _slug(sentence, used),
                    "kind": "magnitude" if re.search(r"\d", sentence) else "skill",
                    "statement": sentence, "quote": sentence, "confidence": 0.9})
        return {"claims": claims}

    @staticmethod
    def _requirements(posting: str) -> dict:
        used: set[str] = set()
        reqs, must = [], True
        for raw in posting.splitlines():
            line = raw.strip()
            if not line.startswith(("-", "*", "•")):
                if re.search(r"nice to have|preferred|bonus", line, re.I):
                    must = False
                elif re.search(r"requirement|must have|qualification", line, re.I):
                    must = True
                continue
            text = line.lstrip("-*• ").strip()
            if text:
                reqs.append({"req_key": _slug(text, used), "text": text,
                             "kind": "skill", "must_have": must})
        return {"requirements": reqs}

    @staticmethod
    def _renderings(system: str, payload: dict) -> dict:
        if "renderings" in payload:          # the repair loop: restate the fact itself
            return {"renderings": [{"id": r["id"], "text": r["fact"]}
                                   for r in payload["renderings"]]}
        letter = "cover-letter" in system
        return {"renderings": [
            {"id": f["id"],
             "text": _first_person(f["statement"]) if letter else f["statement"]}
            for f in payload["facts"]]}

    @staticmethod
    def _questions(payload: dict) -> dict:
        ids = [b["id"] for b in payload.get("bullets", [])] + \
              [g["id"] for g in payload.get("gaps", [])]
        return {"items": [{"id": i, "questions": [
            "What was your own part in this, as opposed to the team's?",
            "What would you do differently if you did it again?"]} for i in ids]}


def build_app(db_path: Path):
    """Wire the doubles into the real app and return it."""
    import sqlalchemy as sa
    from groundwork import Env
    from groundwork.testing import FakeRedis

    from app import db, demo, routes
    from app.config import settings
    from app.main import app

    if settings.app_env is not Env.development:
        raise SystemExit("e2e_server refuses to run outside development")
    if settings.embedding_model or settings.openrouter_api_key != "e2e-scripted-not-a-key":
        raise SystemExit("e2e_server: a real key or embedding model leaked into settings")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    engine = sa.create_engine(f"sqlite:///{db_path.as_posix()}",
                              connect_args={"check_same_thread": False})
    db.metadata.create_all(engine)
    db.set_engine_for_tests(engine)
    demo.set_redis_for_tests(FakeRedis())
    routes._gateway = lambda: ScriptedLLM()
    return app


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--db", default=str(ROOT / "data" / "local" / "e2e.sqlite"))
    args = ap.parse_args()

    import uvicorn

    app = build_app(Path(args.db))
    web = Path(os.environ["WEB_DIR"])
    print(f"E2E HARNESS — sqlite, FakeRedis, ScriptedLLM. Real gates. "
          f"web={'built' if (web / 'index.html').exists() else 'MISSING (run npm run build)'}",
          flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
