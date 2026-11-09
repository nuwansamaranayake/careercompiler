"use client";
/* One tab for both compiled documents. A resume and a cover letter go through the same
   pipeline and the same gates, so they share one component: compile, read on a sheet,
   click a line for its evidence, edit it, download. */
import { useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import {
  humanKey, overstate, plainDetail, plural, refusalFrom, rejectedEditFrom, score,
  type Refusal,
} from "@/lib/format";
import type {
  CompiledLetter, CompiledResume, GateVerdict, Omission, ProvLine,
} from "@/lib/types";
import { GateOutput, RefusalPanel, Spinner, saveBlob } from "./ui";

export type DocKind = "resume" | "letter";
export type Ctx = {
  token: string; candidateId: number; jobId: number; jobTitle: string; who: string;
  /* Returns the message to show. Ends the session when the error is terminal. */
  guard: (e: unknown) => string;
};

const BUDGETS = [
  { lines: 14, label: "Half page" },
  { lines: 28, label: "One page" },
];

type Doc =
  | { kind: "resume"; data: CompiledResume }
  | { kind: "letter"; data: CompiledLetter };

export function DocumentTab({ kind, ctx, onCompiled }: {
  kind: DocKind; ctx: Ctx; onCompiled?: (documentId: number) => void;
}) {
  const what = kind === "resume" ? "resume" : "cover letter";
  const [status, setStatus] = useState<"idle" | "running" | "done" | "failed">("idle");
  const [doc, setDoc] = useState<Doc | null>(null);
  const [lines, setLines] = useState<ProvLine[]>([]);
  const [edited, setEdited] = useState<number[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [failText, setFailText] = useState("");
  const [budget, setBudget] = useState(28);
  const [secs, setSecs] = useState(0);
  const [dlError, setDlError] = useState("");
  const started = useRef(0);

  useEffect(() => {
    if (status !== "running") return;
    const iv = setInterval(() => setSecs(Math.round((Date.now() - started.current) / 1000)), 500);
    return () => clearInterval(iv);
  }, [status]);

  const compile = async () => {
    setStatus("running"); setSecs(0); setRefusal(null); setFailText(""); setSelected(null);
    setEdited([]); setDlError("");
    started.current = Date.now();
    try {
      const next: Doc = kind === "resume"
        ? { kind, data: await api.compileResume(ctx.token, ctx.candidateId, ctx.jobId, budget) }
        : { kind, data: await api.compileLetter(ctx.token, ctx.candidateId, ctx.jobId) };
      const prov = await api.getDocument(ctx.token, next.data.document_id);
      setDoc(next); setLines(prov.bullets); setStatus("done");
      onCompiled?.(next.data.document_id);
    } catch (e) {
      const detail = e instanceof api.ApiError ? e.detail : undefined;
      const r = refusalFrom(detail);
      setRefusal(r);
      if (!r) setFailText(plainDetail(detail, ctx.guard(e)));
      else ctx.guard(e);
      setStatus("failed");
    }
  };

  const download = async (format: "pdf" | "docx") => {
    if (!doc) return;
    setDlError("");
    try {
      const blob = await api.downloadDocument(ctx.token, doc.data.document_id, format);
      const stem = kind === "resume" ? "careercompiler-resume" : "careercompiler-cover-letter";
      saveBlob(blob, `${stem}-${doc.data.document_id}.${format}`);
    } catch (e) { setDlError(ctx.guard(e)); }
  };

  if (status === "idle" || status === "failed") {
    return (
      <div className="stack">
        {status === "failed" && (refusal
          ? <RefusalPanel refusal={refusal} what={what} />
          : <div className="note bad" role="alert" data-testid={`${kind}-error`}>{failText}</div>)}
        <div className="card startcard">
          <div>
            <h3>{kind === "resume" ? "Compile a resume for this job" : "Compile a cover letter for this job"}</h3>
            <p className="dim">
              {kind === "resume"
                ? "A solver picks which of your facts fit this posting under the page budget. The model phrases each one, then two gates check every sentence against the facts it cites."
                : "A short letter in the first person. The greeting, role line, and closing are fixed template text. The model writes only the evidence sentences, and each passes the same two gates as the resume."}
            </p>
            {kind === "resume" && (
              <div className="row" style={{ marginTop: "0.9rem" }}>
                <span className="small" id="len-l">Length</span>
                <div className="seg" role="group" aria-labelledby="len-l">
                  {BUDGETS.map((b) => (
                    <button key={b.lines} type="button" aria-pressed={budget === b.lines}
                      data-testid={`budget-${b.lines}`} onClick={() => setBudget(b.lines)}>
                      {b.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <p className="tiny dim">About 30 seconds in our measured runs.</p>
          </div>
          <button type="button" data-testid={`compile-${kind}`} onClick={compile}>
            {status === "failed" ? "Try again" : `Compile the ${what}`}
          </button>
        </div>
      </div>
    );
  }

  if (status === "running" || !doc) {
    return (
      <div className="card">
        <Spinner label={`Compiling the ${what} — ${secs}s. Selection is deterministic; phrasing, the gates, and any self-repair take the time.`} />
      </div>
    );
  }

  const gate = doc.data.gate;
  const omitted: Omission[] = doc.data.omitted;
  const current = lines.find((l) => l.position === selected) ?? null;

  const lineButton = (l: ProvLine, n: number) => (
    <li key={l.position}>
      <button type="button" className={`line ${edited.includes(l.position) ? "edited" : ""}`}
        aria-pressed={selected === l.position} data-testid={`${kind}-line-${n}`}
        onClick={() => setSelected(selected === l.position ? null : l.position)}>
        <span className="ln" aria-hidden="true">L{String(n + 1).padStart(2, "0")}</span>
        <span>{l.text}</span>
        <span className="sc" title="Entailment score against the cited facts">{score(l.entailment)}</span>
      </button>
    </li>
  );

  return (
    <div className="bench">
      <article className="sheet" data-testid={`${kind}-sheet`}>
        <div className="who">{ctx.who}</div>
        <div className="for">
          {kind === "resume" ? "Resume · tailored for" : "Cover letter ·"} {ctx.jobTitle}
        </div>
        {doc.kind === "letter" && (
          <>
            <p>{doc.data.greeting}</p>
            <p className="frame">{doc.data.opening}<span className="tpl">template</span></p>
          </>
        )}
        <ul className="lines">{lines.map(lineButton)}</ul>
        {doc.kind === "letter" && (
          <>
            <p className="frame">{doc.data.closing}<span className="tpl">template</span></p>
            {/* The server's frame is "Sincerely,\n<name>". The name is read live so a
                rename shows here at once, as it will in the next download. */}
            <p style={{ whiteSpace: "pre-line" }} data-testid="signoff">
              {doc.data.signoff.split("\n")[0]}{"\n"}{ctx.who}
            </p>
          </>
        )}
      </article>

      <aside className="rail">
        <div className="card flat stack">
          <h3>Download</h3>
          <div className="row">
            <button type="button" data-testid={`${kind}-download-pdf`} onClick={() => download("pdf")}>PDF</button>
            <button type="button" className="ghost" data-testid={`${kind}-download-docx`} onClick={() => download("docx")}>Word (docx)</button>
          </div>
          <p className="tiny dim" style={{ margin: 0 }}>
            The provenance appendix ships inside the file. Saved edits are included.
          </p>
          {dlError && <p className="err small" role="alert">{dlError}</p>}
        </div>

        {current ? (
          <LineEditor key={current.position} line={current} ctx={ctx} threshold={gate.threshold}
            onSaved={(text, entailment) => {
              setLines((ls) => ls.map((l) =>
                l.position === current.position ? { ...l, text, entailment } : l));
              setEdited((xs) => xs.includes(current.position) ? xs : [...xs, current.position]);
            }} />
        ) : (
          <div className="card flat">
            <h3>Check or change a line</h3>
            <p className="small dim">
              Click any line on the sheet to see the facts it cites and to edit it. The
              number beside each line is its entailment score. The gate passes at {gate.threshold}.
            </p>
          </div>
        )}

        <div className="card flat">
          <h3>What this is built from</h3>
          <p className="small dim">
            {plural(lines.length, "line")}
            {doc.kind === "resume" && <>, {doc.data.used_lines} of {doc.data.budget_lines} budget lines</>}.
            Gate <code>{gate.model.split("/").pop()}</code> @ <code>{gate.revision.slice(0, 8)}</code>.
          </p>
          {doc.kind === "resume" && doc.data.uncovered_must.length > 0 && (
            <p className="small err">
              Must-have requirements with no evidence on this page:{" "}
              {doc.data.uncovered_must.map(humanKey).join(", ")}.
            </p>
          )}
          {omitted.length > 0 && (
            <details>
              <summary className="small">{plural(omitted.length, "fact")} left out, and why</summary>
              {omitted.map((o, i) => (
                <div className="fact" key={i}>
                  <code>{humanKey(o.claim_key)} · {humanKey(o.reason)}</code>
                  {o.detail}
                </div>
              ))}
            </details>
          )}
          <p style={{ marginBottom: 0 }}>
            <button type="button" className="quiet" data-testid={`${kind}-recompile`}
              onClick={() => { setStatus("idle"); setDoc(null); }}>
              {kind === "resume" ? "Change length or recompile" : "Recompile"}
            </button>
          </p>
        </div>
      </aside>
    </div>
  );
}

function LineEditor({ line, ctx, threshold, onSaved }: {
  line: ProvLine; ctx: Ctx; threshold: number;
  onSaved: (text: string, entailment: number | null) => void;
}) {
  const [text, setText] = useState(line.text);
  const [busy, setBusy] = useState<"" | "check" | "save">("");
  const [verdict, setVerdict] = useState<GateVerdict | null>(null);
  const [saved, setSaved] = useState(false);
  const [message, setMessage] = useState("");
  const changed = text.trim() !== line.text.trim() && text.trim().length > 0;

  const check = async (candidate: string) => {
    setBusy("check"); setMessage(""); setVerdict(null); setSaved(false);
    try {
      setVerdict(await api.checkLine(ctx.token, line.document_id, candidate, line.cites));
    } catch (e) { setMessage(ctx.guard(e)); }
    finally { setBusy(""); }
  };

  const save = async () => {
    setBusy("save"); setMessage(""); setVerdict(null); setSaved(false);
    try {
      const r = await api.saveLine(ctx.token, line.document_id, line.position, text.trim());
      onSaved(r.text, r.entailment);
      setText(r.text);
      setSaved(true);
    } catch (e) {
      const rejected = rejectedEditFrom(e instanceof api.ApiError ? e.detail : undefined);
      if (rejected) setVerdict(rejected);
      else setMessage(ctx.guard(e));
    } finally { setBusy(""); }
  };

  return (
    <div className="card flat stack" data-testid="line-editor">
      <h3>This line cites</h3>
      <div>
        {line.facts.map((f) => (
          <div className="fact" key={f.claim_id}>
            <code>{f.claim_key ? humanKey(f.claim_key) : "unknown"} · {f.provenance ? humanKey(f.provenance) : "unknown"}</code>
            {f.statement ?? "unknown"}
          </div>
        ))}
      </div>
      <div>
        <label className="field" htmlFor={`edit-${line.position}`}>Edit the wording</label>
        <textarea id={`edit-${line.position}`} data-testid="edit-text" rows={4} value={text}
          style={{ minHeight: "6rem" }}
          onChange={(e) => { setText(e.target.value); setSaved(false); }} />
      </div>
      <div className="row">
        <button type="button" data-testid="save-edit" disabled={!changed || busy !== ""} onClick={save}>
          {busy === "save" ? "Checking, then saving…" : "Save edit"}
        </button>
        <button type="button" className="ghost" data-testid="check-edit" disabled={busy !== ""}
          onClick={() => check(text)}>
          {busy === "check" ? "Checking…" : "Check only"}
        </button>
      </div>
      <p className="tiny dim" style={{ margin: 0 }}>
        An edit is saved only if both gates pass at {threshold}. The facts a line cites
        cannot be changed here.{" "}
        <button type="button" className="link" data-testid="overstate" disabled={busy !== ""}
          onClick={() => { const t = overstate(line.text); setText(t); check(t); }}>
          Overstate it for me
        </button>{" "}
        to watch a rejection.
      </p>
      {message && <p className="err small" role="alert">{message}</p>}
      {saved && (
        <div className="note ok" data-testid="edit-saved">
          Saved. The gate scored it {score(line.entailment, 4)}. Downloads now carry this line.
        </div>
      )}
      {verdict && <GateOutput verdict={verdict} facts={line.facts} />}
    </div>
  );
}
