"use client";
/* The results desk: the verdict up top, then one tab per thing a person came for. Tabs
   stay mounted while hidden, so a compiled resume survives a look at the cover letter. */
import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import { humanKey, plural, statusTone } from "@/lib/format";
import type { FitReport, NameSource, Pack } from "@/lib/types";
import { DocumentTab, type Ctx } from "./DocumentTab";
import { Chip, Spinner, Stamp, saveBlob } from "./ui";

type TabId = "match" | "resume" | "letter" | "prep";
const TABS: { id: TabId; label: string }[] = [
  { id: "match", label: "Career match" },
  { id: "resume", label: "Resume" },
  { id: "letter", label: "Cover letter" },
  { id: "prep", label: "Interview prep" },
];

export type ResultsProps = {
  ctx: Ctx; fitReportId: number; verdict: string; synthetic: boolean;
  intakeNote?: string; onRestart: () => void; restartLabel: string;
  /* Present for a person's own resume: how the name was found, and how to correct it. */
  nameSource?: NameSource; onRenamed?: (name: string) => void;
};

const NAME_NOTE: Record<NameSource, string> = {
  resume_first_line: "read from the first line of your resume",
  provided: "as you entered it",
  placeholder: "we could not read a name from your resume",
};

/* The name signs the cover letter, so it is shown, sourced, and correctable. */
function SignedAs({ ctx, source, onRenamed }: {
  ctx: Ctx; source: NameSource; onRenamed: (name: string) => void;
}) {
  const [editing, setEditing] = useState(source === "placeholder");
  const [value, setValue] = useState(source === "placeholder" ? "" : ctx.who);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const save = async () => {
    if (!value.trim()) { setMessage("Enter the name to sign your documents with."); return; }
    setBusy(true); setMessage("");
    try {
      const r = await api.renameCandidate(ctx.token, ctx.candidateId, value.trim());
      onRenamed(r.name);
      setEditing(false);
    } catch (e) { setMessage(ctx.guard(e)); }
    finally { setBusy(false); }
  };

  if (!editing) {
    return (
      <p className="small dim" data-testid="signed-as" style={{ marginBottom: 0 }}>
        Documents are signed as <strong style={{ color: "var(--ink)" }}>{ctx.who}</strong>{" "}
        ({NAME_NOTE[source]}).{" "}
        <button type="button" className="link" data-testid="rename" onClick={() => { setValue(ctx.who); setEditing(true); }}>
          Change
        </button>
      </p>
    );
  }
  return (
    <div className={source === "placeholder" ? "note" : ""} style={{ marginTop: "0.7rem" }} data-testid="name-form">
      <label className="field" htmlFor="doc-name">
        {source === "placeholder"
          ? "We could not read your name from the resume. Add it so your documents are signed correctly."
          : "Name on your documents"}
      </label>
      <div className="row">
        <input id="doc-name" type="text" data-testid="name-input" value={value} maxLength={120}
          style={{ maxWidth: "20rem" }} placeholder="Your full name"
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") save(); }} />
        <button type="button" className="quiet" data-testid="name-save" disabled={busy} onClick={save}>
          {busy ? "Saving…" : "Save name"}
        </button>
      </div>
      {message && <p className="err small" role="alert">{message}</p>}
    </div>
  );
}

export function Results({
  ctx, fitReportId, verdict, synthetic, intakeNote, onRestart, restartLabel, nameSource, onRenamed,
}: ResultsProps) {
  const [tab, setTab] = useState<TabId>("match");
  const [report, setReport] = useState<FitReport | null>(null);
  const [reportError, setReportError] = useState("");
  const [resumeDoc, setResumeDoc] = useState<number | null>(null);
  const { token, guard } = ctx;

  useEffect(() => {
    let live = true;
    api.getFit(token, fitReportId)
      .then((r) => { if (live) setReport(r); })
      .catch((e) => { if (live) setReportError(guard(e)); });
    return () => { live = false; };
  }, [token, fitReportId, guard]);

  const apply = verdict === "apply";
  return (
    <>
      <div className="card verdict" data-testid="verdict">
        <Stamp verdict={verdict} />
        <div>
          <p className="eyebrow" style={{ marginBottom: "0.5rem" }}>
            Verdict for {synthetic && <Chip tone="warn">synthetic sample</Chip>}
          </p>
          <h2>{ctx.jobTitle}</h2>
          {report ? (
            <div className="tally" data-testid="tally">
              <div className="ok"><b>{report.report.matched}</b>matched</div>
              <div className="warn"><b>{report.report.partial}</b>partial</div>
              <div className="bad"><b>{report.report.gaps}</b>{report.report.gaps === 1 ? "gap" : "gaps"}</div>
            </div>
          ) : !reportError && <Spinner label="Loading the report…" />}
          {intakeNote && <p className="small dim" style={{ marginBottom: 0 }}>{intakeNote}</p>}
          {nameSource && onRenamed && (
            <SignedAs key={nameSource} ctx={ctx} source={nameSource} onRenamed={onRenamed} />
          )}
        </div>
        <button type="button" className="quiet" data-testid="restart" onClick={onRestart}>{restartLabel}</button>
      </div>

      <div className="tabs" role="tablist" aria-label="Results">
        {TABS.map((t, i) => (
          <button key={t.id} type="button" role="tab" id={`tab-${t.id}`} data-testid={`tab-${t.id}`}
            aria-selected={tab === t.id} aria-controls={`panel-${t.id}`} onClick={() => setTab(t.id)}>
            <span className="k">{i + 1}</span> {t.label}
          </button>
        ))}
      </div>

      <section role="tabpanel" id="panel-match" aria-labelledby="tab-match" hidden={tab !== "match"}>
        {reportError && <div className="note bad" role="alert">{reportError}</div>}
        {report && (
          <div className="stack">
            {report.report.case_against && (
              <div className={`note ${apply ? "" : "bad"}`} data-testid="case-against">
                <strong>The case against applying:</strong> {report.report.case_against}
              </div>
            )}
            <div className="card">
              <table className="fit" data-testid="fit-table">
                <thead><tr><th>Requirement</th><th>Status</th><th>Evidence</th></tr></thead>
                <tbody>
                  {report.rows.map((r) => (
                    <tr key={r.req_key}>
                      <td>
                        <span className="req">{r.requirement ?? humanKey(r.req_key)}</span>
                        {r.must_have && <span className="must">must-have</span>}
                      </td>
                      <td><Chip tone={statusTone(r.status)}>{r.status}</Chip></td>
                      <td className="small dim">{r.explanation ?? "unknown"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card flat startcard">
              <p className="dim" style={{ margin: 0 }}>
                {apply
                  ? "The evidence supports applying. Compile the documents from the same facts."
                  : "You can still compile the documents. They will only say what your facts support, so the gaps above stay gaps."}
              </p>
              <div className="row">
                <button type="button" data-testid="go-resume" onClick={() => setTab("resume")}>Resume →</button>
                <button type="button" className="ghost" data-testid="go-letter" onClick={() => setTab("letter")}>Cover letter →</button>
              </div>
            </div>
          </div>
        )}
      </section>

      <section role="tabpanel" id="panel-resume" aria-labelledby="tab-resume" hidden={tab !== "resume"}>
        <DocumentTab kind="resume" ctx={ctx} onCompiled={setResumeDoc} />
      </section>

      <section role="tabpanel" id="panel-letter" aria-labelledby="tab-letter" hidden={tab !== "letter"}>
        <DocumentTab kind="letter" ctx={ctx} />
      </section>

      <section role="tabpanel" id="panel-prep" aria-labelledby="tab-prep" hidden={tab !== "prep"}>
        {resumeDoc == null ? (
          <div className="card startcard">
            <div>
              <h3>Compile the resume first</h3>
              <p className="dim">
                The prep pack is built from the lines that passed the gate, so it needs a
                compiled resume to work from.
              </p>
            </div>
            <button type="button" onClick={() => setTab("resume")}>Go to Resume →</button>
          </div>
        ) : (
          <PrepTab key={resumeDoc} ctx={ctx} documentId={resumeDoc} />
        )}
      </section>
    </>
  );
}

function PrepTab({ ctx, documentId }: { ctx: Ctx; documentId: number }) {
  const [status, setStatus] = useState<"idle" | "running" | "done">("idle");
  const [pack, setPack] = useState<Pack | null>(null);
  const [message, setMessage] = useState("");

  const build = async () => {
    setStatus("running"); setMessage("");
    try {
      setPack(await api.buildPack(ctx.token, documentId));
      setStatus("done");
    } catch (e) { setMessage(ctx.guard(e)); setStatus("idle"); }
  };

  const download = async () => {
    setMessage("");
    try {
      saveBlob(await api.downloadPack(ctx.token, documentId), `careercompiler-prep-${documentId}.docx`);
    } catch (e) { setMessage(ctx.guard(e)); }
  };

  if (status !== "done" || !pack) {
    return (
      <div className="card startcard">
        <div>
          <h3>Build the interview pack</h3>
          <p className="dim">
            For each line on your resume: the facts behind it, the numbers you may quote,
            and the questions a skeptical interviewer would ask. Gaps included.
          </p>
          {message && <p className="err small" role="alert">{message}</p>}
        </div>
        {status === "running"
          ? <Spinner label="Building the pack…" />
          : <button type="button" data-testid="build-pack" onClick={build}>Build the pack</button>}
      </div>
    );
  }

  return (
    <div className="bench" data-testid="pack">
      <div className="card">
        <h3>Your lines, and what backs them</h3>
        <p className="small dim">{pack.note}</p>
        {pack.bullets.map((b, i) => (
          <div className="qa" key={i}>
            <strong>{b.text}</strong>
            {b.facts.map((f, j) => (
              <div className="fact" key={j}><code>{humanKey(f.key)} · {humanKey(f.provenance)}</code>{f.statement}</div>
            ))}
            <p className="tiny dim">
              Numbers in the evidence: {b.metrics.length
                ? b.metrics.join(", ")
                : "none. The facts carry no number, so neither may your answer."}
            </p>
            {b.questions.length
              ? b.questions.map((q, j) => <p className="q" key={j}>{q}</p>)
              : <p className="tiny dim">No questions were generated for this line.</p>}
          </div>
        ))}
      </div>
      <aside className="rail">
        <div className="card flat stack">
          <h3>Where you will be probed</h3>
          {pack.case_against && <p className="small err">{pack.case_against}</p>}
          {pack.gaps.length === 0 && <p className="small dim">The fit report found no unmatched requirements.</p>}
          {pack.gaps.map((g, i) => (
            <div className="qa" key={i}>
              <p style={{ margin: 0 }}>
                <strong style={{ textTransform: "capitalize" }}>{humanKey(g.requirement)}</strong>{" "}
                <Chip tone={statusTone(g.status)}>{g.status}</Chip>
              </p>
              <p className="small dim">{g.case}</p>
              {g.questions.map((q, j) => <p className="q" key={j}>{q}</p>)}
            </div>
          ))}
          <p className="tiny dim">
            {plural(pack.gaps.length, "gap")}. Prepare the honest answer: name the gap, name
            your nearest real experience, and say how you would close it.
          </p>
        </div>
        <div className="card flat stack">
          <button type="button" data-testid="download-pack" onClick={download}>Download as Word (docx)</button>
          {message && <p className="err small" role="alert">{message}</p>}
        </div>
      </aside>
    </div>
  );
}
