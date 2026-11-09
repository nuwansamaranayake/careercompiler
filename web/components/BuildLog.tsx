"use client";
/* Step two: the pipeline, shown as what it is. Each line is one real API call. */
import { STEPS } from "@/lib/pipeline";
import type { StepId } from "@/lib/types";

export type StepState = { state: "pending" | "running" | "done" | "failed"; note?: string };
export type StepStates = Record<StepId, StepState>;

export function emptySteps(): StepStates {
  return Object.fromEntries(STEPS.map((s) => [s.id, { state: "pending" }])) as StepStates;
}

const MARK: Record<StepState["state"], string> = {
  pending: "·", running: "▸", done: "✓", failed: "✗",
};

export function BuildLog({ steps, error, onBack }: {
  steps: StepStates; error: string; onBack: () => void;
}) {
  return (
    <>
      <p className="eyebrow">Workspace · step 2 of 2</p>
      <h1 style={{ fontSize: "clamp(2rem, 4vw, 3rem)" }}>
        {error ? "The build stopped." : "Reading, then matching."}
      </h1>
      <p className="lede">
        {error
          ? "Nothing was guessed to get past this. Fix the input and run it again."
          : "The model reads. Deterministic code decides. This takes under a minute in our measured runs."}
      </p>
      <ol className="log" data-testid="build-log" aria-live="polite" style={{ marginTop: "2rem" }}>
        {STEPS.map((s) => {
          const st = steps[s.id];
          return (
            <li key={s.id} data-state={st.state} data-step={s.id}>
              <span className="mark" aria-hidden="true">{MARK[st.state]}</span>
              <span>
                <span className="what">{s.label}</span>
                {st.note && <span className="noted"> — {st.note}</span>}
              </span>
            </li>
          );
        })}
      </ol>
      {error && (
        <div className="note bad stack" role="alert" data-testid="pipeline-error" style={{ marginTop: "1.2rem" }}>
          <p style={{ margin: 0 }}>{error}</p>
          <p><button type="button" className="ghost" data-testid="edit-inputs" onClick={onBack}>← Edit the inputs</button></p>
        </div>
      )}
    </>
  );
}
