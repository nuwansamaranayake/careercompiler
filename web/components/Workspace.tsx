"use client";
/* The workspace: intake, build log, results. One component drives both entry points.
   "own" starts from a person's resume and posting. "sample" starts from the seeded
   synthetic candidate and two seeded jobs, one fit and one honest do-not-apply. */
import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import { endsSession, errorMessage, plural, verdictLabel } from "@/lib/format";
import { PipelineStop, runIntake } from "@/lib/pipeline";
import { clearSession, loadSession, saveSession, stamp } from "@/lib/session";
import type { IntakeInput, IntakeResult, SeededJob, StoredSession } from "@/lib/types";
import { BuildLog, emptySteps, type StepStates } from "./BuildLog";
import { Intake } from "./Intake";
import { Results } from "./Results";
import { Chip, Spinner } from "./ui";

const EMPTY: IntakeInput = { resume: null, jobTitle: "", jobText: "" };

type Phase =
  | { at: "intake" }
  | { at: "running" }
  | { at: "results"; result: IntakeResult }
  | { at: "sample"; session: StoredSession; job: SeededJob | null }
  | { at: "ended"; message: string };

function store(): Storage | null {
  return typeof window === "undefined" ? null : window.sessionStorage;
}

export function Workspace({ mode }: { mode: "own" | "sample" }) {
  const [phase, setPhase] = useState<Phase>({ at: "intake" });
  const [input, setInput] = useState<IntakeInput>(EMPTY);
  const [steps, setSteps] = useState<StepStates>(emptySteps);
  const [error, setError] = useState("");
  const [opening, setOpening] = useState(false);

  /* Returns the sentence to show. A terminal error also ends the session, once, for
     the whole workspace: every tab calls this instead of handling 401 on its own. */
  const guard = useCallback((e: unknown): string => {
    const message = errorMessage(e);
    if (endsSession(e)) {
      const s = store();
      if (s) clearSession(s);
      setPhase({ at: "ended", message });
    }
    return message;
  }, []);

  const restart = useCallback(() => {
    setSteps(emptySteps()); setError(""); setPhase({ at: "intake" });
  }, []);

  const analyze = async (next: IntakeInput) => {
    setInput(next); setError(""); setSteps(emptySteps()); setPhase({ at: "running" });
    let running: keyof StepStates | null = null;
    try {
      const s = store();
      const result = await runIntake(
        { api, now: Date.now, session: s ? loadSession(s, Date.now()) : null,
          onSession: (session) => { if (s) saveSession(s, session); } },
        next,
        (e) => {
          running = e.state === "start" ? e.id : null;
          setSteps((prev) => ({
            ...prev,
            [e.id]: { state: e.state === "start" ? "running" : "done", note: e.note },
          }));
        });
      setPhase({ at: "results", result });
    } catch (e) {
      const failed = e instanceof PipelineStop ? e.step : running;
      if (failed) setSteps((prev) => ({ ...prev, [failed]: { ...prev[failed], state: "failed" } }));
      const message = guard(e);
      if (!endsSession(e)) setError(message);
    }
  };

  const openSample = async () => {
    setOpening(true); setError("");
    try {
      const s = store();
      // The sample needs the seeded candidate, which only a session that still knows
      // its own seed can supply; a stored session from this tab qualifies.
      const session = (s && loadSession(s, Date.now())) || stamp(await api.openSession(), Date.now());
      if (s) saveSession(s, session);
      setPhase({ at: "sample", session, job: null });
    } catch (e) { setError(guard(e)); }
    finally { setOpening(false); }
  };

  const sampleCtx = useMemo(() => {
    if (phase.at !== "sample" || !phase.job) return null;
    return {
      token: phase.session.token, candidateId: phase.session.candidate_id,
      jobId: phase.job.job_id, jobTitle: phase.job.title,
      who: phase.session.candidate_name, guard,
    };
  }, [phase, guard]);

  const ownCtx = useMemo(() => {
    if (phase.at !== "results") return null;
    const r = phase.result;
    return {
      token: r.session.token, candidateId: r.candidateId, jobId: r.jobId,
      jobTitle: r.jobTitle, who: r.name, guard,
    };
  }, [phase, guard]);

  if (phase.at === "ended") {
    return (
      <div className="card stack" data-testid="session-ended" role="alert">
        <h2>That session is over.</h2>
        <p className="dim">{phase.message}</p>
        <p><button type="button" data-testid="new-session" onClick={restart}>Start a new session</button></p>
      </div>
    );
  }

  if (phase.at === "results" && ownCtx) {
    const r = phase.result;
    return (
      <Results key={r.fit.fit_report_id} ctx={ownCtx} fitReportId={r.fit.fit_report_id}
        verdict={r.fit.verdict} synthetic={false}
        intakeNote={`Built from ${plural(r.facts.usable, "fact")} anchored in your resume` +
          (r.facts.rejected ? ` (${r.facts.rejected} rejected on anchoring and never used)` : "") +
          ` and ${plural(r.requirements, "requirement")} read from the posting.`}
        nameSource={r.nameSource}
        onRenamed={(name) => setPhase({
          at: "results", result: { ...r, name, nameSource: "provided" } })}
        onRestart={restart} restartLabel="← New analysis" />
    );
  }

  if (phase.at === "sample") {
    const { session, job } = phase;
    if (job && sampleCtx) {
      return (
        <Results key={job.fit_report_id} ctx={sampleCtx} fitReportId={job.fit_report_id}
          verdict={job.verdict} synthetic
          intakeNote={`${session.candidate_name} is an invented candidate. Nothing here describes a real person.`}
          onRestart={() => setPhase({ at: "sample", session, job: null })}
          restartLabel="← Other sample job" />
      );
    }
    return (
      <>
        <p className="eyebrow">Sample · synthetic data</p>
        <h1 style={{ fontSize: "clamp(2rem, 4vw, 3rem)" }}>One resume, two jobs.</h1>
        <p className="lede">
          {session.candidate_name} is invented. So are both postings. They are built so
          each answer the product gives is one click away.
        </p>
        <div className="grid2" style={{ marginTop: "2rem" }}>
          {session.jobs.map((j) => (
            <div className="card stack" key={j.job_id}>
              <Chip tone="warn">synthetic</Chip>
              <h3>{j.title}</h3>
              <p className="dim small">
                Seeded verdict: <strong>{verdictLabel(j.verdict)}</strong>.
              </p>
              <p style={{ marginBottom: 0 }}>
                <button type="button" data-testid={`sample-job-${j.verdict}`}
                  onClick={() => setPhase({ at: "sample", session, job: j })}>
                  Open this one →
                </button>
              </p>
            </div>
          ))}
        </div>
      </>
    );
  }

  if (mode === "sample") {
    return (
      <>
        <p className="eyebrow">Sample · synthetic data</p>
        <h1 style={{ fontSize: "clamp(2rem, 4vw, 3rem)" }}>See it work before you bring anything.</h1>
        <p className="lede">
          A seeded, invented candidate and two invented postings. One is a fit. The other
          carries a must-have the resume cannot evidence, so the verdict is do not apply.
        </p>
        <div className="card startcard" style={{ marginTop: "2rem" }}>
          <p className="dim" style={{ margin: 0 }}>
            You get a scoped token held only by this browser tab. It expires on its own
            after 30 minutes and has a fixed request budget.
          </p>
          {opening
            ? <Spinner label="Opening a session…" />
            : <button type="button" data-testid="open-sample" onClick={openSample}>Open the sample</button>}
        </div>
        {error && <div className="note bad" role="alert" style={{ marginTop: "1rem" }}>{error}</div>}
        <p className="small dim" style={{ marginTop: "1.5rem" }}>
          Have a resume and a posting? <Link href="/workspace/">Use the workspace</Link>.
        </p>
      </>
    );
  }

  if (phase.at === "running") {
    return <BuildLog steps={steps} error={error} onBack={restart} />;
  }

  return <Intake initial={input} onSubmit={analyze} />;
}
