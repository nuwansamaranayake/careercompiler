"""Smoke: real business endpoints with real processing, against a running instance.

Flow: health -> dev fixture -> create candidate -> enter self-attested claims (keyless
product path) -> create job with entry-path requirements -> run the deterministic fit ->
fetch the stored report and assert a schema-valid verdict. Requires the database to be up
(Standard 2: a health check alone is not a smoke test).
"""
import json
import os
import sys
from pathlib import Path

import httpx

BASE = f"http://{os.getenv('API_HOST', '127.0.0.1')}:{os.getenv('API_PORT', '8000')}"
TOKEN = os.getenv("SMOKE_TEST_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
GOLDEN = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "golden" / "golden.json"


def get(path: str):
    r = httpx.get(BASE + path, headers=HEADERS, timeout=10)
    r.raise_for_status()
    body = r.json()
    assert body, f"{path} returned an empty body"
    return body


def post(path: str, payload: dict, expect: int = 201):
    r = httpx.post(BASE + path, headers=HEADERS, json=payload, timeout=30)
    assert r.status_code == expect, f"{path}: {r.status_code} {r.text[:200]}"
    return r.json()


def main():
    get("/health")
    assert get("/api/v1/demo").get("items"), "demo endpoint returned no items"

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    cid = post("/api/v1/candidates", {"name": "Smoke Candidate"})["candidate_id"]
    stored = post(f"/api/v1/candidates/{cid}/claims",
                  {"entries": golden["fact_graph"]})["stored"]
    assert stored > 0, "no claims stored"

    case = golden["cases"][0]
    jid = post("/api/v1/jobs", {"title": "Smoke Role",
                                "requirements": case["requirements"]})["job_id"]
    fit = post("/api/v1/fit", {"candidate_id": cid, "job_id": jid})
    assert fit["verdict"] in ("apply", "do_not_apply"), "fit returned no verdict"

    full = get(f"/api/v1/fit/{fit['fit_report_id']}")
    assert full["rows"], "stored report has no match rows"
    assert full["report"]["verdict"] == fit["verdict"]
    print("SMOKE OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"SMOKE FAILED: {e}", file=sys.stderr)
        sys.exit(1)
