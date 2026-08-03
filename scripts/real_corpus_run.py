"""The real-corpus proof: one real resume against every supplied posting, full pipeline,
every outcome recorded. (Part 5)

Generic runner — it embeds no private content and is safe to commit. Private inputs come
from --resume and --jobs (both should live under fixtures/private/, which is gitignored);
the full per-pairing record is written NEXT TO the inputs (also private). Stdout carries
aggregates and mechanisms only — safe for EVAL.md.

Tenancy (Part 5.2): rows are created with an estate token under a `smoke-<stamp>Z-priv…-`
name prefix. Demo tokens are prefix-scoped, so demo visitors cannot guard through to
these rows, and the estate retention sweep deletes the smoke- family after 7 days — the
personal data cleans itself up.

Run:
  python scripts/real_corpus_run.py --base <url> --token <estate token> \
      --resume fixtures/private/<file>.pdf --jobs fixtures/private/jobs \
      --out fixtures/private
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import time
from pathlib import Path

import httpx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--resume", required=True)
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    H = {"Authorization": f"Bearer {args.token}"}
    c = httpx.Client(base_url=args.base, timeout=60)
    llm = httpx.Client(base_url=args.base, timeout=420)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ns = f"smoke-{stamp}-priv01-"
    record: dict = {"stamp": stamp, "base": args.base, "pairings": []}

    resume = Path(args.resume)
    with resume.open("rb") as f:
        r = c.post("/api/v1/candidates/upload", headers=H,
                   data={"name": f"{ns}corpus-candidate"},
                   files={"file": (resume.name, f, "application/pdf")})
    if r.status_code != 201:
        print(f"ABORT: resume upload {r.status_code} {r.text[:200]}")
        return 1
    cid = r.json()["candidate_id"]
    record["resume_chars"] = r.json().get("chars")

    e = llm.post(f"/api/v1/candidates/{cid}/claims/extract", headers=H)
    if e.status_code != 201:
        print(f"ABORT: extract {e.status_code} {e.text[:200]}")
        return 1
    ex = e.json()
    record["extraction"] = {"stored": ex["stored"],
                            "rejected": ex["rejected_span_anchor"],
                            "rejected_detail": ex.get("rejected", [])}
    print(f"extraction: {ex['stored']} facts, {ex['rejected_span_anchor']} rejected "
          f"on span anchoring "
          f"({100 * ex['rejected_span_anchor'] / max(ex['stored'], 1):.1f}%)")

    def gate_summary(detail: dict) -> dict:
        toks = []
        for v in detail.get("violations", []):
            m = re.search(r"the number '([^']+)'", v.get("detail", "") or "")
            toks.append({"failure": v.get("failure") or "entailment",
                         "token": m.group(1) if m else None,
                         "entailment": v.get("entailment")})
        return {"error": detail.get("error"), "violations": toks,
                "repair_rounds": len(detail.get("repair", []))}

    out = Path(args.out) / f"corpus_results_{stamp}.json"

    def checkpoint():
        """The record survives any single pairing's crash (review, 2026-08-03)."""
        out.write_text(json.dumps(record, indent=1), encoding="utf-8")

    for jobfile in sorted(Path(args.jobs).glob("*.txt")):
        p: dict = {"job": jobfile.name}
        t0 = time.time()
        try:
            jr = c.post("/api/v1/jobs", headers=H, json={
                "title": f"{ns}{jobfile.stem}",
                "description": jobfile.read_text(encoding="utf-8")})
            if jr.status_code != 201:
                p["outcome"] = f"job_create_failed_{jr.status_code}"
                record["pairings"].append(p)
                checkpoint()
                continue
            jid = jr.json()["job_id"]
            pr = llm.post(f"/api/v1/jobs/{jid}/requirements/parse", headers=H)
            p["parsed"] = pr.json().get("parsed") if pr.status_code == 201 else 0
            p["parse_status"] = pr.status_code
            if not p["parsed"]:
                p["outcome"] = "no_requirements_parsed"
                record["pairings"].append(p)
                checkpoint()
                print(f"{jobfile.name}: parsed=0 -> honest stop (nothing to match)")
                continue

            fr = c.post("/api/v1/fit", headers=H,
                        json={"candidate_id": cid, "job_id": jid})
            if fr.status_code != 201:
                p["outcome"] = f"fit_failed_{fr.status_code}"
                record["pairings"].append(p)
                checkpoint()
                continue
            fit = fr.json()
            p["verdict"] = fit.get("verdict")
            p["embedder"] = fit.get("embedder")
            rows = c.get(f"/api/v1/fit/{fit['fit_report_id']}", headers=H).json()["rows"]
            p["must_matched"] = [x["req_key"] for x in rows
                                 if x["must_have"] and x["status"] == "matched"]
            p["must_missed"] = [x["req_key"] for x in rows
                                if x["must_have"] and x["status"] != "matched"]

            cm = llm.post("/api/v1/compile", headers=H,
                          json={"candidate_id": cid, "job_id": jid})
            if cm.status_code == 201:
                body = cm.json()
                p["compile"] = {"ok": True, "bullets": len(body["bullets"]),
                                "repair_rounds": len(body.get("repair", [])),
                                "min_entail": min((b["entailment"] or 0)
                                                  for b in body["bullets"])}
                did = body["document_id"]
                lt = llm.post("/api/v1/cover-letter", headers=H,
                              json={"candidate_id": cid, "job_id": jid})
                p["letter"] = ({"ok": True,
                                "sentences": len(lt.json()["sentences"]),
                                "repair_rounds": len(lt.json().get("repair", []))}
                               if lt.status_code == 201
                               else {"ok": False,
                                     **gate_summary(lt.json().get("detail", {}))})
                pk = llm.post("/api/v1/interview-pack", headers=H,
                              json={"document_id": did})
                p["pack"] = ({"ok": True, "bullets": len(pk.json()["bullets"]),
                              "gaps": len(pk.json()["gaps"])}
                             if pk.status_code == 201
                             else {"ok": False, "status": pk.status_code})
                p["outcome"] = "compiled"
            else:
                p["compile"] = {"ok": False,
                                **gate_summary(cm.json().get("detail", {}))}
                p["outcome"] = "compile_refused"
        except Exception as exc:  # noqa: BLE001 — a pairing's crash is a recorded
            # finding, never the death of the whole record (review, 2026-08-03).
            p["outcome"] = f"error: {exc!r}"
        p["secs"] = round(time.time() - t0, 1)
        record["pairings"].append(p)
        checkpoint()
        print(f"{jobfile.name}: verdict={p.get('verdict')} "
              f"must={len(p.get('must_matched', []))}/"
              f"{len(p.get('must_matched', [])) + len(p.get('must_missed', []))} "
              f"outcome={p['outcome']} "
              f"repairs={p.get('compile', {}).get('repair_rounds', '-')} "
              f"({p['secs']}s)")

    checkpoint()
    compiled = [p for p in record["pairings"] if p.get("outcome") == "compiled"]
    refused = [p for p in record["pairings"] if p.get("outcome") == "compile_refused"]
    repairs = sum(p.get("compile", {}).get("repair_rounds", 0)
                  for p in record["pairings"] if p.get("compile"))
    print(f"\nAGGREGATE: {len(record['pairings'])} pairings | "
          f"compiled {len(compiled)} | refused {len(refused)} | "
          f"honest-stops {sum(1 for p in record['pairings'] if p['outcome'] == 'no_requirements_parsed')} | "
          f"total repair rounds {repairs}")
    print(f"full record (private): {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
