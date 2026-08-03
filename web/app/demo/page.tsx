"use client";
/* The demo: resume -> job -> fit verdict -> compile -> THE REJECTION MOMENT -> docx.

   One continuous flow: bring a resume (seeded or your own upload), bring a job (seeded
   or paste your own posting), get the honest verdict, compile the evidence-backed page.
   E2 is the product: edit a bullet to overstate the evidence, submit, watch the gate
   reject it with the cited facts beside it and the score visible. Honest states
   everywhere: no fabricated numbers, unknown says unknown, errors show as errors. */
import { useCallback, useEffect, useRef, useState } from "react";

type SeededJob = { job_id: number; fit_report_id: number; title: string; verdict: string };
type Session = {
  token: string; expires_in: number; request_budget: number; synthetic: boolean;
  candidate_id: number; candidate_name: string; jobs: SeededJob[];
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
/* A compile refusal after the server's own repair loop exhausted: the sentence that
   could not be grounded, the facts it reached for, and why. Rendered as the product
   being honest — never with a retry button, because the retrying already happened. */
type Refusal = { sentence: string; cited: string[]; why: string; rounds: number } | null;

function refusalFrom(detail: unknown): Refusal {
  const d = detail as { error?: string; repair?: unknown[];
    violations?: { text?: string; cited?: string[]; detail?: string;
                   entailment?: number; threshold?: number }[] };
  if (!d?.error || !d.violations?.length) return null;
  const v = d.violations[0];
  const why = v.detail
    ?? (v.entailment != null
        ? `the evidence supports it at ${v.entailment.toFixed(2)}, below the ${v.threshold} the gate requires`
        : d.error);
  return { sentence: v.text ?? "(sentence unavailable)", cited: v.cited ?? [],
           why: why ?? d.error ?? "refused", rounds: (d.repair?.length ?? 0) + 1 };
}

function RefusalPanel({ r, what }: { r: NonNullable<Refusal>; what: string }) {
  return (
    <div className="panel reject">
      <p style={{ margin: 0 }}>
        <strong>This {what} draft was refused, after {r.rounds} attempt{r.rounds === 1 ? "" : "s"}.</strong>
      </p>
      <p className="small" style={{ margin: "0.4rem 0" }}>
        The sentence that could not be grounded: <em>{r.sentence}</em>
      </p>
      {r.cited.length > 0 && (
        <p className="small" style={{ margin: "0.4rem 0" }}>
          It was reaching for: {r.cited.map((s, i) => <span key={i}><code>{s}</code>{" "}</span>)}
        </p>
      )}
      <p className="small" style={{ margin: "0.4rem 0" }}>{r.why}.</p>
      <p className="small dim" style={{ marginBottom: 0 }}>
        The compiler re-drafted with the rejection as a constraint and still could not
        say this honestly, so the claim was refused rather than shipped. That is the
        product keeping its promise, not an error.
      </p>
    </div>
  );
}
/* Which resume is driving the flow right now. The seeded synthetic candidate by default;
   an upload replaces it for every fit and compile that follows. Ids stay internal. */
type ActiveResume = { cid: number; label: string; synthetic: boolean };
type FitState = { rid: number; verdict: string; forCid: number };

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
  const [active, setActive] = useState<ActiveResume>({
    cid: session.candidate_id, label: session.candidate_name, synthetic: true });
  const [customJobs, setCustomJobs] = useState<
    { job_id: number; title: string; initialFit: FitState }[]>([]);
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
      <h2>1 · The resume</h2>
      <p className="dim">
        Working from: <strong>{active.label}</strong>
        {active.synthetic
          ? <span className="chip syn">synthetic</span>
          : <span className="chip ok">your upload</span>}
        {!active.synthetic && (
          <button className="secondary" style={{ marginLeft: "0.6rem" }}
            onClick={() => setActive({ cid: session.candidate_id, label: session.candidate_name, synthetic: true })}>
            Switch back to the seeded resume
          </button>
        )}
      </p>
      <UploadPanel session={session} guard={guard}
        onReady={(cid, stats) => setActive({
          cid, synthetic: false,
          label: `your resume (${stats.stored} extracted facts)` })} />
      <h2>2 · The job, and the honest verdict</h2>
      <p className="dim">
        Two seeded postings, invented so both answers the product gives are one click away —
        or paste a real posting below and get the verdict on <strong>{active.synthetic ? "the seeded resume" : "your own resume"}</strong>.
      </p>
      {session.jobs.map((j) => (
        <FitCard key={j.job_id} session={session} jobId={j.job_id} title={j.title}
          candidateId={active.cid}
          initialFit={{ rid: j.fit_report_id, verdict: j.verdict, forCid: session.candidate_id }}
          guard={guard} />
      ))}
      {customJobs.map((j) => (
        <FitCard key={j.job_id} session={session} jobId={j.job_id} title={j.title}
          candidateId={active.cid} initialFit={j.initialFit} guard={guard} />
      ))}
      <CustomJobPanel session={session} candidateId={active.cid} guard={guard}
        onCreated={(job) => setCustomJobs((xs) => [...xs, job])} />
    </>
  );
}

function FitCard({ session, jobId, title, candidateId, initialFit, guard }: {
  session: Session; jobId: number; title: string; candidateId: number;
  initialFit?: FitState; guard: (e: unknown) => string;
}) {
  const [fit, setFit] = useState<FitState | null>(initialFit ?? null);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  // A fit report answers for one resume. If the active resume changed, the old
  // verdict is not this resume's verdict — require a fresh run, never reuse.
  const current = fit && fit.forCid === candidateId ? fit : null;
  const ok = current?.verdict === "apply";

  const runFit = async () => {
    setBusy(true); setMsg(""); setReport(null); setRows([]);
    try {
      const d = await api<{ fit_report_id: number; verdict: string }>(
        session.token, "/api/v1/fit", {
          method: "POST",
          body: JSON.stringify({ candidate_id: candidateId, job_id: jobId }),
        });
      setFit({ rid: d.fit_report_id, verdict: d.verdict, forCid: candidateId });
    } catch (e) { setMsg(guard(e)); }
    finally { setBusy(false); }
  };

  const load = async () => {
    if (!current) return;
    try {
      const d = await api<{ report: Record<string, unknown>; rows: Record<string, unknown>[] }>(
        session.token, `/api/v1/fit/${current.rid}`);
      setReport(d.report); setRows(d.rows);
    } catch (e) { setMsg(guard(e)); }
  };

  return (
    <div className="panel">
      <p style={{ margin: 0 }}>
        <strong>{title}</strong>
        {current
          ? <span className={`chip ${ok ? "ok" : "bad"}`}>{current.verdict.replace(/_/g, " ")}</span>
          : <button className="secondary" style={{ float: "right" }} onClick={runFit} disabled={busy}>
              {busy ? "Matching…" : "Run the fit for this resume"}
            </button>}
        {current && !report &&
          <button className="secondary" style={{ float: "right" }} onClick={load}>Why?</button>}
      </p>
      {msg && <p className="err small">{msg}</p>}
      {current && report && (
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
          <CompilePanel session={session} jobId={jobId} candidateId={candidateId} guard={guard} />
        </>
      )}
    </div>
  );
}

function CustomJobPanel({ session, candidateId, guard, onCreated }: {
  session: Session; candidateId: number; guard: (e: unknown) => string;
  onCreated: (job: { job_id: number; title: string; initialFit: FitState }) => void;
}) {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [stage, setStage] = useState<"idle" | "job" | "parse" | "fit">("idle");
  const [msg, setMsg] = useState("");

  const stages: Record<string, string> = {
    job: "Storing the posting…",
    parse: "Reading the posting into requirements — the model senses, the matcher decides…",
    fit: "Matching your evidence against the requirements…",
  };

  const submit = async () => {
    if (!text.trim()) { setMsg("paste the job posting text first"); return; }
    setMsg("");
    try {
      setStage("job");
      const t = title.trim() || "The role you pasted";
      const { job_id } = await api<{ job_id: number }>(session.token, "/api/v1/jobs", {
        method: "POST", body: JSON.stringify({ title: t, description: text }) });
      setStage("parse");
      const p = await api<{ parsed: number }>(
        session.token, `/api/v1/jobs/${job_id}/requirements/parse`, { method: "POST" });
      if (p.parsed === 0) {
        setMsg("No requirements could be read out of that text. The matcher has nothing to match against — try pasting the full posting, including the qualifications section.");
        setStage("idle"); return;
      }
      setStage("fit");
      const f = await api<{ fit_report_id: number; verdict: string }>(
        session.token, "/api/v1/fit", {
          method: "POST",
          body: JSON.stringify({ candidate_id: candidateId, job_id }) });
      onCreated({ job_id, title: t,
        initialFit: { rid: f.fit_report_id, verdict: f.verdict, forCid: candidateId } });
      setTitle(""); setText(""); setStage("idle");
    } catch (e) { setMsg(guard(e)); setStage("idle"); }
  };

  return (
    <div className="panel">
      <h2 style={{ marginTop: 0 }}>Paste a job posting</h2>
      <p className="dim small">
        Any posting, pasted as text. The model reads it into typed requirements — you will
        see every one it found, and the deterministic matcher scores your evidence against
        them. The verdict can be <em>do not apply</em>: that is the product working.
      </p>
      <p>
        <input type="text" placeholder="Job title (optional)" value={title}
          onChange={(e) => setTitle(e.target.value)} style={{ width: "100%" }} />
      </p>
      <textarea rows={8} placeholder="Paste the job description here…" value={text}
        onChange={(e) => setText(e.target.value)} style={{ width: "100%" }} />
      <p>
        <button onClick={submit} disabled={stage !== "idle"}>
          {stage === "idle" ? "Get the verdict" : stages[stage]}
        </button>
      </p>
      {msg && <p className="err small">{msg}</p>}
    </div>
  );
}

function CompilePanel({ session, jobId, candidateId, guard }: {
  session: Session; jobId: number; candidateId: number; guard: (e: unknown) => string;
}) {
  const [state, setState] = useState<"idle" | "run" | "done" | "fail">("idle");
  const [doc, setDoc] = useState<Compiled | null>(null);
  const [prov, setProv] = useState<ProvBullet[]>([]);
  const [refusal, setRefusal] = useState<Refusal>(null);
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
        body: JSON.stringify({ candidate_id: candidateId, job_id: jobId }),
      });
      setDoc(d);
      const p = await api<{ bullets: ProvBullet[] }>(session.token, `/api/v1/compile/${d.document_id}`);
      setProv(p.bullets);
      setState("done");
    } catch (e) {
      const err = e as Error & { detail?: unknown };
      const r = refusalFrom(err.detail);
      setRefusal(r);
      if (!r) setFailDetail(guard(e));
      setState("fail");
    }
  };

  if (state === "idle")
    return <p><button onClick={compile}>Compile this resume</button>{" "}
      <span className="dim small">the model phrases, two gates check, and the compiler
      repairs its own drafts; ~30 s in our measured runs</span></p>;
  if (state === "run")
    return <p className="dim"><span className="spin">◌</span> Compiling — {secs}s. Selection is
      deterministic; phrasing, the gates, and any self-repair take the time.</p>;
  if (state === "fail")
    return refusal
      ? <RefusalPanel r={refusal} what="resume" />
      : <div className="panel reject"><p style={{ margin: 0 }}>{failDetail.slice(0, 300)}</p></div>;
  return doc ? (
    <>
      <CompiledView doc={doc} prov={prov} session={session} guard={guard} />
      <LetterPanel session={session} jobId={jobId} candidateId={candidateId} guard={guard} />
      <PackPanel session={session} documentId={doc.document_id} guard={guard} />
    </>
  ) : null;
}

type Pack = {
  document_id: number; job_title: string; verdict: string; case_against: string | null;
  note: string;
  bullets: { text: string; facts: { key: string; statement: string; provenance: string }[];
             metrics: string[]; questions: string[] }[];
  gaps: { requirement: string; case: string; status: string; must_have: boolean;
          questions: string[] }[];
};

function PackPanel({ session, documentId, guard }: {
  session: Session; documentId: number; guard: (e: unknown) => string;
}) {
  const [state, setState] = useState<"idle" | "run" | "done">("idle");
  const [pack, setPack] = useState<Pack | null>(null);
  const [msg, setMsg] = useState("");
  const [dlMsg, setDlMsg] = useState("");

  const build = async () => {
    setState("run"); setMsg("");
    try {
      const d = await api<Pack>(session.token, "/api/v1/interview-pack", {
        method: "POST", body: JSON.stringify({ document_id: documentId }) });
      setPack(d); setState("done");
    } catch (e) { setMsg(guard(e)); setState("idle"); }
  };

  const download = async () => {
    try {
      const r = await fetch("/api/v1/interview-pack", {
        method: "POST",
        headers: { "Content-Type": "application/json",
                   Authorization: `Bearer ${session.token}` },
        body: JSON.stringify({ document_id: documentId, format: "docx" }) });
      if (!r.ok) { setDlMsg(`download failed: HTTP ${r.status}`); return; }
      const blob = await r.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `careercompiler-prep-${documentId}.docx`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) { setDlMsg(friendly(e)); }
  };

  if (state === "idle")
    return <p style={{ marginTop: "1.2rem" }}>
      <button onClick={build}>Build the interview pack</button>{" "}
      <span className="dim small">the story, the metrics, and the skeptical questions —
      built only from facts that survived the gate, gaps included</span>
      {msg && <span className="err small"> {msg}</span>}</p>;
  if (state === "run")
    return <p className="dim"><span className="spin">◌</span> Building the pack — the
      facts and gaps are assembled from stored rows; the model writes only the questions.</p>;
  if (!pack) return null;
  return (
    <>
      <h2 style={{ marginTop: "1.4rem" }}>Interview preparation</h2>
      <p className="dim small">{pack.note}</p>
      {pack.bullets.map((b, i) => (
        <div className="bullet" key={i}>
          <p style={{ margin: 0 }}><strong>{b.text}</strong></p>
          <div className="small" style={{ margin: "0.3rem 0 0 1rem" }}>
            {b.facts.map((f, j) => (
              <p key={j} style={{ margin: "0.15rem 0" }}>
                <code>{f.key}</code> — {f.statement}{" "}
                <span className="dim">({f.provenance})</span>
              </p>
            ))}
            <p className="dim" style={{ margin: "0.15rem 0" }}>
              metrics in the evidence:{" "}
              {b.metrics.length ? b.metrics.join(", ")
                : "none — the facts carry no number, so neither may your answer"}
            </p>
            {b.questions.length
              ? b.questions.map((q, j) => <p key={j} style={{ margin: "0.15rem 0" }}>❓ {q}</p>)
              : <p className="dim" style={{ margin: "0.15rem 0" }}>no questions generated for this bullet</p>}
          </div>
        </div>
      ))}
      <h2>The gaps — where you will be probed</h2>
      {pack.case_against && (
        <p className="small err"><strong>The fit report&apos;s case against applying:</strong>{" "}
          {pack.case_against}</p>
      )}
      {pack.gaps.length === 0 && (
        <p className="small dim">The fit report found no unmatched requirements.</p>
      )}
      {pack.gaps.map((g, i) => (
        <div className="bullet" key={i}>
          <p style={{ margin: 0 }}>
            <code>{g.requirement}</code>{g.must_have ? " *" : ""}{" "}
            <span className={`chip ${g.status === "gap" ? "bad" : ""}`}>{g.status}</span>{" "}
            <span className="small dim">{g.case}</span>
          </p>
          <div className="small" style={{ margin: "0.3rem 0 0 1rem" }}>
            {g.questions.map((q, j) => <p key={j} style={{ margin: "0.15rem 0" }}>❓ {q}</p>)}
            <p className="dim" style={{ margin: "0.15rem 0" }}>
              Prepare the honest answer: name the gap, name your nearest real experience
              from the evidence above, and say how you would close it.
            </p>
          </div>
        </div>
      ))}
      <p><button onClick={download}>Download the prep docx</button></p>
      {dlMsg && <p className="err small">{dlMsg}</p>}
    </>
  );
}

type Letter = {
  document_id: number; kind: string;
  greeting: string; opening: string; closing: string; signoff: string;
  sentences: Bullet[];
  omitted: { claim_key: string; reason: string; detail: string }[];
  gate: { model: string; revision: string; threshold: number };
};

function LetterPanel({ session, jobId, candidateId, guard }: {
  session: Session; jobId: number; candidateId: number; guard: (e: unknown) => string;
}) {
  const [state, setState] = useState<"idle" | "run" | "done" | "fail">("idle");
  const [letter, setLetter] = useState<Letter | null>(null);
  const [prov, setProv] = useState<ProvBullet[]>([]);
  const [refusal, setRefusal] = useState<Refusal>(null);
  const [failDetail, setFailDetail] = useState("");
  const [dlMsg, setDlMsg] = useState("");

  const compile = async () => {
    setState("run");
    try {
      const d = await api<Letter>(session.token, "/api/v1/cover-letter", {
        method: "POST",
        body: JSON.stringify({ candidate_id: candidateId, job_id: jobId }),
      });
      setLetter(d);
      const p = await api<{ bullets: ProvBullet[] }>(
        session.token, `/api/v1/compile/${d.document_id}`);
      setProv(p.bullets);
      setState("done");
    } catch (e) {
      const err = e as Error & { detail?: unknown };
      const r = refusalFrom(err.detail);
      setRefusal(r);
      if (!r) setFailDetail(guard(e));
      setState("fail");
    }
  };

  const download = async () => {
    if (!letter) return;
    try {
      const r = await fetch(`/api/v1/compile/${letter.document_id}/docx`, {
        headers: { Authorization: `Bearer ${session.token}` } });
      if (!r.ok) { setDlMsg(`download failed: HTTP ${r.status}`); return; }
      const blob = await r.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `careercompiler-letter-${letter.document_id}.docx`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) { setDlMsg(friendly(e)); }
  };

  if (state === "idle")
    return <p style={{ marginTop: "1.2rem" }}>
      <button onClick={compile}>Compile the cover letter</button>{" "}
      <span className="dim small">same gates as the resume, letter voice — a letter is
      where fabrication is most tempting, so it gets exactly the same checks</span></p>;
  if (state === "run")
    return <p className="dim"><span className="spin">◌</span> Compiling the letter — the
      model restates your facts in first person; both gates check every sentence.</p>;
  if (state === "fail")
    return refusal
      ? <RefusalPanel r={refusal} what="cover letter" />
      : <div className="panel reject"><p style={{ margin: 0 }}>{failDetail.slice(0, 300)}</p></div>;
  if (!letter) return null;
  return (
    <>
      <h2 style={{ marginTop: "1.4rem" }}>The cover letter</h2>
      <p className="dim small">
        The greeting, the role line, and the closing are fixed template text: they may name
        the role because they claim nothing about you. The model wrote only the evidence
        sentences — each cites its facts and passed the {letter.gate.threshold} entailment
        gate. Click one for provenance; challenge it to see the compile error.
      </p>
      <div className="panel">
        <p>{letter.greeting}</p>
        <p>{letter.opening} <span className="chip syn">template</span></p>
        {prov.map((b) => (
          <BulletRow key={b.position} bullet={b} session={session}
            threshold={letter.gate.threshold} guard={guard} />
        ))}
        <p>{letter.closing} <span className="chip syn">template</span></p>
        <p style={{ whiteSpace: "pre-line" }}>{letter.signoff}</p>
      </div>
      {letter.omitted.length > 0 && (
        <p className="small dim">
          Left out: {letter.omitted.map((o) => o.claim_key).join(", ")} — the letter budget
          keeps it short; the resume carries the full evidence.
        </p>
      )}
      <p><button onClick={download}>Download the letter docx</button>{" "}
        <span className="dim small">the provenance map ships inside the document</span></p>
      {dlMsg && <p className="err small">{dlMsg}</p>}
    </>
  );
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
      <h2 style={{ marginTop: "1.4rem" }}>The compiled page</h2>
      <p className="dim small">
        {doc.bullets.length} bullets, {doc.used_lines} of {doc.budget_lines} budget lines.
        Gate: <code>{doc.gate.model}</code> @ <code>{doc.gate.revision.slice(0, 12)}</code>,
        threshold {doc.gate.threshold}. Click a bullet for its provenance; challenge one to
        see the compile error.
      </p>
      <p className="dim small">
        <strong>How tailoring works here:</strong> the job chose which facts made this
        page; it did not reword them. The renderer never sees the posting — steering
        wording toward requirements produced claims the evidence did not support, so the
        gate rejected them and we removed the steering. The cover letter below is the one
        exception: its fixed frame may name the role, and its sentences still pass the
        same gate.
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

function UploadPanel({ session, guard, onReady }: {
  session: Session; guard: (e: unknown) => string;
  onReady: (cid: number, stats: { stored: number; rejected: number }) => void;
}) {
  const [state, setState] = useState<"idle" | "up" | "extracting" | "done">("idle");
  const [msg, setMsg] = useState("");
  const [stats, setStats] = useState<{ stored: number; rejected: number } | null>(null);
  const [rejects, setRejects] = useState<{ claim_key: string; statement: string; quote: string | null }[]>([]);
  const [showRejects, setShowRejects] = useState(false);
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
      setState("extracting");
      const ex = await api<{ stored: number; rejected_span_anchor: number;
        rejected?: { claim_key: string; statement: string; quote: string | null }[] }>(
        session.token, `/api/v1/candidates/${candidate_id}/claims/extract`, { method: "POST" });
      const st = { stored: ex.stored, rejected: ex.rejected_span_anchor };
      setStats(st);
      setRejects(ex.rejected ?? []);
      setState("done");
      onReady(candidate_id, st);
    } catch (e) { setMsg(guard(e)); setState("idle"); }
  };

  return (
    <div className="panel">
      <p className="dim small" style={{ marginTop: 0 }}>
        <strong>Or bring your own.</strong> PDF or docx. This is personal data: it lives only
        in your session&apos;s tenant and is deleted by the retention sweep once it is older
        than 7 days. Extraction is span-anchored — every extracted fact must quote your
        document verbatim, and a quote that fails to anchor is stored rejected and never
        used.
      </p>
      <p>
        <input type="file" ref={fileRef} accept=".pdf,.docx" />{" "}
        <button onClick={upload} disabled={state === "up" || state === "extracting"}>
          {state === "up" ? "Uploading…" : state === "extracting" ? "Extracting facts…" : "Upload and extract"}
        </button>
      </p>
      {msg && <p className="err small">{msg}</p>}
      {state === "done" && stats && (
        <>
          <p className="small">
            Extracted <strong>{stats.stored}</strong> facts from your resume
            {stats.rejected > 0 && <>; <strong>{stats.rejected}</strong> rejected on span anchoring
            (they will never match)</>}. It is now the working resume — run a fit on a seeded
            job, or paste a posting below.
          </p>
          {rejects.length > 0 && (
            <div className="small">
              <p className="dim" style={{ margin: "0.3rem 0" }}>
                A rejection is the anchor check working, not an error: every fact must quote
                your document verbatim, and these could not be located in it.{" "}
                <button className="secondary" onClick={() => setShowRejects(!showRejects)}>
                  {showRejects ? "Hide them" : `Show the ${rejects.length} rejected`}
                </button>
              </p>
              {showRejects && rejects.map((x, i) => (
                <p key={i} style={{ margin: "0.2rem 0" }}>
                  <code>{x.claim_key}</code> — {x.statement}<br />
                  <span className="dim">offered as evidence: “{x.quote ?? "(empty quote)"}” —
                  not found verbatim in your document, so it will never match a requirement
                  or reach a page.</span>
                </p>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
