"use client";
/* Small shared pieces. No logic lives here: wording and decisions come from web/lib. */
import type { ReactNode } from "react";
import { humanKey, score, statusTone, verdictLabel, type Refusal } from "@/lib/format";
import type { Fact, GateVerdict } from "@/lib/types";

export function Chip({ tone, children }: { tone?: string; children: ReactNode }) {
  return <span className={`chip ${tone ?? ""}`}>{children}</span>;
}

export function Spinner({ label }: { label: string }) {
  return (
    <span className="row dim" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

export function Stamp({ verdict, small }: { verdict: string; small?: boolean }) {
  const tone = statusTone(verdict);
  return (
    <span className={`stamp ${tone === "bad" ? "bad" : ""} ${small ? "sm" : ""}`}
      data-testid="verdict-stamp" data-verdict={verdict}>
      {verdictLabel(verdict)}
    </span>
  );
}

export function saveBlob(blob: Blob, filename: string): void {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}

/* The gate's answer, set like compiler output. A pass and a reject share one shape so
   the difference the eye lands on is the verdict, not the layout. */
export function GateOutput({ verdict, facts }: { verdict: GateVerdict; facts: Fact[] }) {
  const e = verdict.entailment;
  if (verdict.ok) {
    return (
      <div className="diag pass" data-testid="gate-verdict" data-ok="true">
        <span className="head">ok: compiles</span>{"\n"}
        <span className="gutter">  | </span>entailment {score(e.score, 4)} ≥ threshold {e.threshold ?? "unknown"}{"\n"}
        <span className="gutter">  = </span>the cited facts support this sentence
      </div>
    );
  }
  return (
    <div className="diag" data-testid="gate-verdict" data-ok="false">
      <span className="head">error: the sentence outran its evidence</span>{"\n"}
      {verdict.reference_integrity.violations.map((v, i) => (
        <span key={`r${i}`}>
          <span className="gutter">  | </span>{v.failure}: {v.detail}{"\n"}
        </span>
      ))}
      {e.checked && !e.ok && (
        <span>
          <span className="gutter">  | </span>entailment {score(e.score, 4)} &lt; threshold {e.threshold ?? "unknown"}{"\n"}
        </span>
      )}
      {e.checked && e.violations?.map((v, i) => (
        <span key={`e${i}`}><span className="gutter">  | </span>{v.detail}{"\n"}</span>
      ))}
      <span className="gutter">  = </span>scored against:{"\n"}
      {facts.map((f) => (
        <span key={f.claim_id}>
          <span className="gutter">      </span>{f.claim_key ?? "unknown"}: {f.statement ?? "unknown"}{"\n"}
        </span>
      ))}
    </div>
  );
}

export function RefusalPanel({ refusal, what }: { refusal: Refusal; what: string }) {
  return (
    <div className="note bad stack" data-testid="refusal">
      <p style={{ margin: 0 }}>
        <strong>
          This {what} was refused after {refusal.rounds} attempt{refusal.rounds === 1 ? "" : "s"}.
        </strong>
      </p>
      <p>The sentence that could not be grounded: <em>{refusal.sentence}</em></p>
      {refusal.cited.length > 0 && (
        <p>It was reaching for: {refusal.cited.map((c) => <code key={c}>{humanKey(c)} </code>)}</p>
      )}
      <p>{refusal.why}.</p>
      <p className="dim">
        The compiler re-drafted with the rejection as a constraint and still could not say
        this honestly, so the claim was refused rather than shipped. That is the product
        keeping its promise, not an error.
      </p>
    </div>
  );
}
