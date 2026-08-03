"use client";
/* The demo: fit verdicts -> compile -> THE REJECTION MOMENT -> provenance -> docx.

   E2 is the product: edit a bullet to overstate the evidence, submit, watch the gate
   reject it with the cited facts beside it and the score visible. Honest states
   everywhere: no fabricated numbers, unknown says unknown, errors show as errors. */
import { useCallback, useEffect, useRef, useState } from "react";

type Job = { job_id: number; fit_report_id: number; title: string; verdict: string };
type Session = {
  token: string; expires_in: number; request_budget: number; synthetic: boolean;
  candidate_id: number; candidate_name: string; jobs: Job[];
};
type Bullet = { position: number; text: string; cites: string[]; entailment: number | null };
type Fact = { claim_id: string; claim_key: string | null; statement: string | null; provenance: string | null };
type ProvBullet = Bullet & { document_id: number; facts: Fact[] };
type Compiled = {
  document_id: number; bullets: Bullet[];
  omitted: { claim_key: string; reason: string; detail: string }[];
  covered_must: string[]; uncovered_must: string[];
  used_lines: number; budget_lines: number;
  gate: { model: string; revision: string; threshold: number };
};
type CheckResult = {
  ok: boolean;
  reference_integrity: { ok: boolean; violations: { failure: string; detail: string }[] };
  entailment: { checked: boolean; ok?: boolean; score?: number | null; threshold?: number;
                violations?: { detail: string; premise: string }[] };
};

const S_KEY = "cc-demo-session";

function useSession() {
  const [session, setSession] = useState<Session | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const raw = sessionStorage.getItem(S_KEY);
    if (raw) try { setSession(JSON.parse(raw)); } catch { /* stale */ }
  }, []);
  const start = useCallback(async () => {
    setBusy(true); setErr("");
    try {
      const r = await fetch("/api/v1/demo/session", { method: "POST" });
      if (!r.ok) { setErr(`could not open a session: HTTP ${r.status} — ${(await r.json()).detail ?? ""}`); return; }
      const s = (await r.json()) as Session;
      sessionStorage.setItem(S_KEY, JSON.stringify(s));
      setSession(s);
    } catch (e) { setErr(`could not reach the API: ${String(e)}`); }
    finally { setBusy(false); }
  }, []);
  const drop = useCallback(() => { sessionStorage.removeItem(S_KEY); setSession(null); }, []);
  return { session, start, drop, err, busy };
}

async function api<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(init?.headers ?? {}) },
  });
  if (r.status === 401) throw new Error("SESSION_EXPIRED");
  if (r.status === 429) throw new Error("BUDGET_EXHAUSTED");
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    const err = new Error(`HTTP ${r.status}`) as Error & { detail?: unknown };
    err.detail = body?.detail;
    throw err;
  }
  return r.json();
}

function friendly(e: unknown): string {
  const m = e instanceof Error ? e.message : String(e);
  if (m === "SESSION_EXPIRED") return "This demo session expired. Start a new one. The seeded data was synthetic; anything you uploaded stays in its expired tenant until the retention sweep deletes it.";
  if (m === "BUDGET_EXHAUSTED") return "This session's request budget is spent. Start a new one.";
  return m;
}

// Deterministic, clearly-labelled overstatement presets. These run in your browser and
// exist so the rejection is reachable in seconds; typing your own works the same way.
function inflate(text: string): string {
  const n = text.match(/\d[\d,]*/);
  if (n) return text.replace(n[0], String(Number(n[0].replace(/,/g, "")) * 10));
  return "Directed the entire engineering organisation. " + text;
}

export default function Demo() {
  const { session, start, drop, err, busy } = useSession();
  return (
    <>
      <p className="dim mono small"><a href="/">CareerCompiler</a> / live demo</p>
      <h1>The demo</h1>
      <div className="panel limits">
        <strong>Synthetic data.</strong> The seeded candidate and jobs are invented and
        labelled as such. If you upload your own resume it is personal data: it stays in a
        session-scoped tenant and is automatically deleted by a retention sweep once it
        is older than 7 days (proven by row count against production). Tailoring here is evidence
        selection — the renderer never sees the job posting, so wording does not shift per
        job; what changes is which facts make the page.
      </div>
      {!session ? (
        <div className="panel">
          <button onClick={start} disabled={busy}>
            {busy ? "Opening session…" : "Start the demo — no sign-up"}
          </button>
          <p className="dim small">
            You get a scoped bearer token held only by this browser tab. It expires on its
            own and has a fixed request budget. Every server read still requires a token:
            the demo never opens an unauthenticated path.
          </p>
          {err && <p className="err">{err}</p>}
        </div>
      ) : (
        <SessionView session={session} restart={() => { drop(); }} />
      )}
    </>
  );
}

function SessionView({ session, restart }: { session: Session; restart: () => void }) {
  const [fatal, setFatal] = useState("");
  const guard = useCallback((e: unknown) => {
    const msg = friendly(e);
    if (msg.startsWith("This ")) setFatal(msg); // expiry/budget end the session honestly
    return msg;
  }, []);
  if (fatal) {
    return (
      <div className="panel reject">
        <p>{fatal}</p>
        <button onClick={restart}>Start a new session</button>
      </div>
    );
  }
  return (
    <>
      <h2>1 · Honest fit verdicts <span className="chip syn">synthetic</span></h2>
      <p className="dim">
        Candidate: <strong>{session.candidate_name}</strong> — five seeded facts, each carrying provenance. Two job
        postings, seeded so you can see both answers the product gives.
      </p>
      {session.jobs.map((j) => (
        <FitCard key={j.job_id} session={session} job={j} guard={guard} />
      ))}
      <UploadPanel session={session} guard={guard} />
    </>
  );
}

function FitCard({ session, job, guard }: { session: Session; job: Job; guard: (e: unknown) => string }) {
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [msg, setMsg] = useState("");
  const ok = job.verdict === "apply";
  const load = async () => {
    try {
      const d = await api<{ report: Record<string, unknown>; rows: Record<string, unknown>[] }>(
        session.token, `/api/v1/fit/${job.fit_report_id}`);
      setReport(d.report); setRows(d.rows);
    } catch (e) { setMsg(guard(e)); }
  };
  return (
    <div className="panel">
      <p style={{ margin: 0 }}>
        <strong>{job.title}</strong>
        <span className={`chip ${ok ? "ok" : "bad"}`}>{job.verdict.replace(/_/g, " ")}</span>
        {!report && <button className="secondary" style={{ float: "right" }} onClick={load}>Why?</button>}
      </p>
      {msg && <p className="err small">{msg}</p>}
      {report && (
        <>
          {typeof report.case_against === "string" && report.case_against && (
            <p className={`small ${ok ? "dim" : "err"}`}>
              <strong>The case against applying:</strong> {report.case_against}
            </p>
          )}
          <table className="fit">
            <thead><tr><th>requirement</th><th>status</th><th>evidence</th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td className="mono">{String(r.req_key)}{r.must_have ? " *" : ""}</td>
                  <td><span className={`chip ${r.status === "matched" ? "ok" : r.status === "gap" ? "bad" : ""}`}>{String(r.status)}</span></td>
                  <td className="small dim">{String(r.explanation ?? "unknown")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <CompilePanel session={session} job={job} guard={guard} />
        </>
      )}
    </div>
  );
}

function CompilePanel({ session, job, guard }: { session: Session; job: Job; guard: (e: unknown) => string }) {
  const [state, setState] = useState<"idle" | "run" | "done" | "fail">("idle");
  const [doc, setDoc] = useState<Compiled | null>(null);
  const [prov, setProv] = useState<ProvBullet[]>([]);
  const [failDetail, setFailDetail] = useState<string>("");
  const t0 = useRef(0);
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    if (state !== "run") return;
    const iv = setInterval(() => setSecs(Math.round((Date.now() - t0.current) / 1000)), 500);
    return () => clearInterval(iv);
  }, [state]);

  const compile = async () => {
    setState("run"); t0.current = Date.now();
    try {
      const d = await api<Compiled>(session.token, "/api/v1/compile", {
        method: "POST",
        body: JSON.stringify({ candidate_id: session.candidate_id, job_id: job.job_id }),
      });
      setDoc(d);
      const p = await api<{ bullets: ProvBullet[] }>(session.token, `/api/v1/compile/${d.document_id}`);
      setProv(p.bullets);
      setState("done");
    } catch (e) {
      const err = e as Error & { detail?: { error?: string; violations?: { detail?: string }[] } };
      if (err.detail?.error) {
        // A real gate rejection of the model's own draft — show it as what it is.
        setFailDetail(`${err.detail.error}: ${err.detail.violations?.[0]?.detail ?? "see API response"}`);
        setState("fail");
      } else { setFailDetail(guard(e)); setState("fail"); }
    }
  };

  if (state === "idle")
    return <p><button onClick={compile}>Compile this resume</button>{" "}
      <span className="dim small">the model phrases, two gates check; ~30 s in our measured runs</span></p>;
  if (state === "run")
    return <p className="dim"><span className="spin">◌</span> Compiling — {secs}s. Selection is
      deterministic; phrasing and the gates take the time.</p>;
  if (state === "fail")
    return (
      <div className="panel reject">
        <p><strong>The compile failed its own gate.</strong> {failDetail.slice(0, 300)}</p>
        <p className="small dim">This is the product working, not breaking: a draft that
          outran its evidence was refused. Compile again for a fresh draft.</p>
        <button className="secondary" onClick={compile}>Compile again</button>
      </div>
    );
  return doc ? <CompiledView doc={doc} prov={prov} session={session} guard={guard} /> : null;
}

function CompiledView({ doc, prov, session, guard }: {
  doc: Compiled; prov: ProvBullet[]; session: Session; guard: (e: unknown) => string;
}) {
  const [dlMsg, setDlMsg] = useState("");
  const download = async () => {
    try {
      const r = await fetch(`/api/v1/compile/${doc.document_id}/docx`, {
        headers: { Authorization: `Bearer ${session.token}` } });
      if (!r.ok) { setDlMsg(`download failed: HTTP ${r.status}`); return; }
      const blob = await r.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `careercompiler-${doc.document_id}.docx`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) { setDlMsg(friendly(e)); }
  };
  return (
    <>
      <h2 style={{ marginTop: "1.4rem" }}>2 · The compiled page</h2>
      <p className="dim small">
        {doc.bullets.length} bullets, {doc.used_lines} of {doc.budget_lines} budget lines.
        Gate: <code>{doc.gate.model}</code> @ <code>{doc.gate.revision.slice(0, 12)}</code>,
        threshold {doc.gate.threshold}. Click a bullet for its provenance; challenge one to
        see the compile error.
      </p>
      {prov.map((b) => (
        <BulletRow key={b.position} bullet={b} session={session} threshold={doc.gate.threshold} guard={guard} />
      ))}
      {doc.omitted.length > 0 && (
        <>
          <h2>What was left out, and why</h2>
          {doc.omitted.map((o, i) => (
            <p key={i} className="small dim">
              <code>{o.claim_key}</code> — <strong>{o.reason.replace(/_/g, " ")}</strong>: {o.detail}
            </p>
          ))}
        </>
      )}
      {doc.uncovered_must.length > 0 && (
        <p className="err small">Must-have requirements without evidence on this page:{" "}
          {doc.uncovered_must.join(", ")}</p>
      )}
      <p><button onClick={download}>Download the docx</button>{" "}
        <span className="dim small">the provenance map ships inside the document</span></p>
      {dlMsg && <p className="err small">{dlMsg}</p>}
    </>
  );
}

function BulletRow({ bullet, session, threshold, guard }: {
  bullet: ProvBullet; session: Session; threshold: number; guard: (e: unknown) => string;
}) {
  const [open, setOpen] = useState(false);
  const [challenge, setChallenge] = useState(false);
  const [text, setText] = useState(bullet.text);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const check = async (t: string) => {
    setBusy(true); setMsg(""); setResult(null);
    try {
      // document_id travels through the cites' document via the API contract:
      const d = await api<CheckResult>(session.token, "/api/v1/compile/check", {
        method: "POST",
        body: JSON.stringify({ document_id: bullet.document_id, text: t, cites: bullet.cites }),
      });
      setResult(d);
    } catch (e) { setMsg(guard(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="bullet">
      <p style={{ margin: 0, cursor: "pointer" }} onClick={() => setOpen(!open)}>
        • {bullet.text}
        {bullet.entailment != null
          ? <span className="chip ok">entails {bullet.entailment.toFixed(2)}</span>
          : <span className="chip">entailment unknown</span>}
      </p>
      {open && (
        <div className="small" style={{ margin: "0.4rem 0 0 1rem" }}>
          <p className="dim" style={{ margin: 0 }}>Cited facts:</p>
          {bullet.facts.map((f) => (
            <p key={f.claim_id} style={{ margin: "0.15rem 0" }}>
              <code>{f.claim_key ?? "unknown"}</code> — {f.statement ?? "unknown"}{" "}
              <span className="dim">({f.provenance ?? "unknown"})</span>
            </p>
          ))}
          {!challenge ? (
            <button className="danger-ish" style={{ marginTop: "0.4rem" }}
              onClick={() => { setChallenge(true); setResult(null); }}>
              Challenge this sentence
            </button>
          ) : (
            <div style={{ marginTop: "0.5rem" }}>
              <textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} />
              <p style={{ margin: "0.4rem 0" }}>
                <button onClick={() => check(text)} disabled={busy}>
                  {busy ? "Checking…" : "Recheck against the evidence"}
                </button>{" "}
                <button className="secondary" onClick={() => { const t = inflate(bullet.text); setText(t); check(t); }} disabled={busy}>
                  Overstate it for me
                </button>
              </p>
              {msg && <p className="err">{msg}</p>}
              {result && <CheckVerdict r={result} threshold={threshold} facts={bullet.facts} />}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CheckVerdict({ r, threshold, facts }: { r: CheckResult; threshold: number; facts: Fact[] }) {
  if (r.ok)
    return (
      <div className="panel pass">
        <p style={{ margin: 0 }}>
          <strong>Compiles.</strong> The evidence supports this sentence
          {r.entailment.score != null && <> at <code>{r.entailment.score.toFixed(4)}</code> against
          the {threshold} threshold</>}.
        </p>
      </div>
    );
  return (
    <div className="panel reject">
      <p style={{ margin: 0 }}><strong>Compile error.</strong> The sentence outran its evidence.</p>
      {r.reference_integrity.violations.map((v, i) => (
        <p key={i} className="small" style={{ margin: "0.3rem 0" }}>
          <code>{v.failure}</code>: {v.detail}
        </p>
      ))}
      {r.entailment.checked && r.entailment.violations?.map((v, i) => (
        <p key={i} className="small" style={{ margin: "0.3rem 0" }}>
          entailment <code>{r.entailment.score?.toFixed(4) ?? "unknown"}</code> against the{" "}
          {r.entailment.threshold} threshold — {v.detail}
        </p>
      ))}
      <p className="small dim" style={{ marginBottom: 0 }}>The evidence it was scored against:</p>
      {facts.map((f) => (
        <p key={f.claim_id} className="small" style={{ margin: "0.15rem 0" }}>
          <code>{f.claim_key ?? "unknown"}</code> — {f.statement ?? "unknown"}
        </p>
      ))}
    </div>
  );
}

function UploadPanel({ session, guard }: { session: Session; guard: (e: unknown) => string }) {
  const [state, setState] = useState<"idle" | "up" | "extracting" | "done">("idle");
  const [msg, setMsg] = useState("");
  const [stats, setStats] = useState<{ stored: number; rejected: number } | null>(null);
  const [cid, setCid] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const upload = async () => {
    const f = fileRef.current?.files?.[0];
    if (!f) { setMsg("choose a PDF or docx first"); return; }
    setState("up"); setMsg("");
    try {
      const fd = new FormData();
      fd.append("name", "My upload");
      fd.append("file", f);
      const r = await fetch("/api/v1/candidates/upload", {
        method: "POST", headers: { Authorization: `Bearer ${session.token}` }, body: fd });
      if (!r.ok) { setMsg(`upload failed: HTTP ${r.status} — ${(await r.json()).detail ?? ""}`); setState("idle"); return; }
      const { candidate_id } = await r.json();
      setCid(candidate_id);
      setState("extracting");
      const ex = await api<{ stored: number; rejected_span_anchor: number }>(
        session.token, `/api/v1/candidates/${candidate_id}/claims/extract`, { method: "POST" });
      setStats({ stored: ex.stored, rejected: ex.rejected_span_anchor });
      setState("done");
    } catch (e) { setMsg(guard(e)); setState("idle"); }
  };

  return (
    <div className="panel">
      <h2 style={{ marginTop: 0 }}>3 · Or use your own resume</h2>
      <p className="dim small">
        PDF or docx. This is personal data: it lives only in your session&apos;s tenant and is
        deleted by the retention sweep once it is older than 7 days. Extraction is
        span-anchored — every extracted fact must quote
        your document verbatim, and a quote that fails to anchor is stored rejected and never
        used.
      </p>
      <p>
        <input type="file" ref={fileRef} accept=".pdf,.docx" />{" "}
        <button onClick={upload} disabled={state === "up" || state === "extracting"}>
          {state === "up" ? "Uploading…" : state === "extracting" ? "Extracting facts…" : "Upload and extract"}
        </button>
      </p>
      {msg && <p className="err small">{msg}</p>}
      {state === "done" && stats && cid != null && (
        <p className="small">
          Extracted <strong>{stats.stored}</strong> facts
          {stats.rejected > 0 && <>; <strong>{stats.rejected}</strong> rejected on span anchoring
          (they will never match)</>}. Your candidate id is <code>{cid}</code> — run a fit
          against a seeded job above by compiling from the API, or open a fresh session to
          start over. The full custom-job flow ships after this demo.
        </p>
      )}
    </div>
  );
}
