"""The demo-path gate: walk the exact sequence a visitor follows, fail the release on
any break.

session -> upload (synthetic PDF built in-script) -> paste job -> parse -> verdict ->
compile -> cover letter -> interview pack -> both docx downloads. Synthetic content
only — never the private corpus (Part 6.2). Every call carries an explicit timeout; a
step that fails prints the step name and the body and exits 1. No -k anywhere: TLS is
verified by default.

Run:  python scripts/demo_path_smoke.py --base https://careercompiler.aigniteconsulting.ai
Exit: 0 = the whole visitor path works; 1 = the named step broke (release-blocking);
      2 = usage error.
"""
from __future__ import annotations

import argparse
import sys
import time

import httpx

LINES = [
    "Casey Morgan",
    "Platform Engineer - Synthetic Fixture",
    "Experience",
    "Ran Kubernetes in production across 3 clusters serving 40 microservices.",
    "Wrote Terraform modules that provisioned all cloud infrastructure as code.",
    "Cut mean deploy time 35% by rebuilding the CI pipeline with GitHub Actions.",
    "Carried the on-call pager and led incident response for a 99.95% uptime platform.",
    "Led a platform team of 5 engineers at Vantage Systems from 2020 to 2024.",
]

JOB = ("Platform Engineer, Fixture Systems. We run everything on Kubernetes and codify "
       "our cloud with Terraform. Requirements: Kubernetes in production. Terraform "
       "infrastructure as code. CI/CD pipeline ownership. On-call incident response. "
       "Nice to have: team leadership.")


def synthetic_pdf() -> bytes:
    """A minimal single-page text PDF; pypdf extracts every line verbatim."""
    parts = ["BT /F1 11 Tf 40 760 Td 14 TL"]
    for i, line in enumerate(LINES):
        esc = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        if i:
            parts.append("T*")
        parts.append(f"({esc}) Tj")
    parts.append("ET")
    stream = " ".join(parts).encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream
        + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF").encode()
    return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True,
                    help="e.g. https://careercompiler.aigniteconsulting.ai")
    args = ap.parse_args()
    c = httpx.Client(base_url=args.base, timeout=30)
    llm = httpx.Client(base_url=args.base, timeout=300)  # compile/letter/pack do repairs
    t_start = time.time()
    step = "?"

    def fail(body: str) -> int:
        print(f"DEMO PATH BROKEN at step: {step} — {body[:400]}")
        return 1

    try:
        step = "1 session"
        r = c.post("/api/v1/demo/session")
        if r.status_code != 201:
            return fail(r.text)
        s = r.json()
        tok = {"Authorization": f"Bearer {s['token']}"}
        print(f"[{step}] ok budget={s['request_budget']}")

        step = "2 upload"
        r = c.post("/api/v1/candidates/upload", headers=tok,
                   data={"name": "Casey Morgan"},
                   files={"file": ("casey-fixture.pdf", synthetic_pdf(),
                                   "application/pdf")})
        if r.status_code != 201:
            return fail(r.text)
        cid = r.json()["candidate_id"]

        step = "2b extract"
        r = llm.post(f"/api/v1/candidates/{cid}/claims/extract", headers=tok)
        if r.status_code != 201 or r.json().get("stored", 0) < 4:
            return fail(f"{r.status_code} {r.text[:200]}")
        print(f"[{step}] ok stored={r.json()['stored']} "
              f"rejected={r.json()['rejected_span_anchor']}")

        step = "3 paste job"
        r = c.post("/api/v1/jobs", headers=tok,
                   json={"title": "Platform Engineer, Fixture Systems",
                         "description": JOB})
        if r.status_code != 201:
            return fail(r.text)
        jid = r.json()["job_id"]

        step = "3b parse"
        r = llm.post(f"/api/v1/jobs/{jid}/requirements/parse", headers=tok)
        if r.status_code != 201 or r.json().get("parsed", 0) < 3:
            return fail(f"{r.status_code} {r.text[:200]}")
        print(f"[{step}] ok parsed={r.json()['parsed']}")

        step = "4 verdict"
        r = c.post("/api/v1/fit", headers=tok,
                   json={"candidate_id": cid, "job_id": jid})
        if r.status_code != 201:
            return fail(r.text)
        verdict = r.json()["verdict"]
        print(f"[{step}] ok verdict={verdict}")

        step = "5 compile"
        r = llm.post("/api/v1/compile", headers=tok,
                     json={"candidate_id": cid, "job_id": jid})
        if r.status_code != 201:
            return fail(f"{r.status_code} {r.text[:300]}")
        doc = r.json()
        did = doc["document_id"]
        print(f"[{step}] ok bullets={len(doc['bullets'])} "
              f"repair_rounds={len(doc.get('repair', []))}")

        step = "5b resume docx"
        r = c.get(f"/api/v1/compile/{did}/docx", headers=tok)
        if r.status_code != 200 or r.content[:2] != b"PK" or len(r.content) < 5000:
            return fail(f"{r.status_code} {len(r.content)}B")

        step = "6 cover letter"
        r = llm.post("/api/v1/cover-letter", headers=tok,
                     json={"candidate_id": cid, "job_id": jid})
        if r.status_code != 201:
            return fail(f"{r.status_code} {r.text[:300]}")
        letter = r.json()
        print(f"[{step}] ok sentences={len(letter['sentences'])} "
              f"repair_rounds={len(letter.get('repair', []))}")

        step = "6b letter docx"
        r = c.get(f"/api/v1/compile/{letter['document_id']}/docx", headers=tok)
        if r.status_code != 200 or r.content[:2] != b"PK":
            return fail(f"{r.status_code} {len(r.content)}B")

        step = "7 interview pack"
        r = llm.post("/api/v1/interview-pack", headers=tok,
                     json={"document_id": did})
        if r.status_code != 201 or not r.json().get("bullets"):
            return fail(f"{r.status_code} {r.text[:200]}")
        print(f"[{step}] ok bullets={len(r.json()['bullets'])} "
              f"gaps={len(r.json()['gaps'])}")

        step = "7b pack docx"
        r = llm.post("/api/v1/interview-pack", headers=tok,
                     json={"document_id": did, "format": "docx"})
        if r.status_code != 201 or r.content[:2] != b"PK":
            return fail(f"{r.status_code} {len(r.content)}B")

    except httpx.HTTPError as e:
        return fail(f"transport: {e!r}")

    print(f"DEMO PATH OK in {time.time() - t_start:.0f}s — every step a visitor "
          f"walks, walked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
