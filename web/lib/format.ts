/* Turning server responses into words. Every function here is pure. None of them invent
   a number: when the server did not say, the answer is "unknown" or nothing. */
import { ApiError } from "./api";
import type { GateVerdict } from "./types";

/* A compile refusal after the server's own repair loop is exhausted: the sentence that
   could not be grounded, the facts it reached for, and why. */
export type Refusal = { sentence: string; cited: string[]; why: string; rounds: number };

type RefusalDetail = {
  error?: string;
  repair?: { stage?: string }[];
  violations?: {
    text?: string; cited?: string[]; detail?: string; entailment?: number; threshold?: number;
  }[];
};

export function refusalFrom(detail: unknown): Refusal | null {
  const d = detail as RefusalDetail | null | undefined;
  if (!d || typeof d !== "object" || !d.error || !d.violations?.length) return null;
  const v = d.violations[0];
  const why = v.detail
    ?? (v.entailment != null
      ? `the evidence supports it at ${score(v.entailment)}, below the ${v.threshold} the gate requires`
      : d.error);
  // One attempt per failed evaluation round. The revision_unchanged marker is the loop
  // stopping honestly, not an attempt. Never a count the log does not carry.
  const rounds = (d.repair ?? []).filter((e) => e.stage !== "revision_unchanged").length;
  return {
    sentence: v.text ?? "(sentence unavailable)",
    cited: v.cited ?? [],
    why,
    rounds: Math.max(rounds, 1),
  };
}

/* A rejected saved edit carries the same evidence as the live check. */
export function rejectedEditFrom(detail: unknown): GateVerdict | null {
  const d = detail as { error?: string } & Partial<GateVerdict> | null | undefined;
  if (!d || typeof d !== "object" || d.error !== "edit_rejected") return null;
  if (!d.reference_integrity || !d.entailment) return null;
  return { ok: false, reference_integrity: d.reference_integrity, entailment: d.entailment };
}

/* Typed details: entailment_unavailable carries {error, message}; key-gate 503s and
   renderer 502s carry a plain string. */
export function plainDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail) return detail;
  const d = detail as { message?: string; error?: string } | null | undefined;
  if (d && typeof d === "object" && d.message) return `${d.error ?? "unavailable"}: ${d.message}`;
  return fallback;
}

export const SESSION_EXPIRED =
  "This session expired. Start a new one. Anything you uploaded stays in its expired " +
  "tenant until the retention sweep deletes it.";
export const BUDGET_EXHAUSTED = "This session's request budget is spent. Start a new one.";

/* True when the error ends the session: the only honest next step is a new one. */
export function endsSession(e: unknown): boolean {
  return e instanceof ApiError && (e.code === "SESSION_EXPIRED" || e.code === "BUDGET_EXHAUSTED");
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === "SESSION_EXPIRED") return SESSION_EXPIRED;
    if (e.code === "BUDGET_EXHAUSTED") return BUDGET_EXHAUSTED;
    if (e.code === "NETWORK") return `Could not reach the API: ${plainDetail(e.detail, "network error")}`;
    return plainDetail(e.detail, `The server answered HTTP ${e.status}.`);
  }
  return e instanceof Error ? e.message : String(e);
}

export function verdictLabel(verdict: string): string {
  return verdict.replace(/_/g, " ");
}

export type Tone = "ok" | "warn" | "bad" | "plain";

export function statusTone(status: string): Tone {
  if (status === "matched" || status === "apply") return "ok";
  if (status === "partial") return "warn";
  if (status === "gap" || status === "do_not_apply") return "bad";
  return "plain";
}

/* "active_ts_sci_clearance" -> "active ts sci clearance". Keys are machine names; this
   only makes them readable, it does not rename them. */
export function humanKey(key: string): string {
  return key.replace(/[_-]+/g, " ").trim();
}

/* Truncated, never rounded: 0.9976 reads "0.99", not "1.00". A score that looks like
   certainty when it is not would be the interface overstating the gate. */
export function score(value: number | null | undefined, digits = 2): string {
  if (value == null) return "unknown";
  const k = 10 ** digits;
  return (Math.floor(value * k + 1e-9) / k).toFixed(digits);
}

/* A deterministic, clearly labelled overstatement so the rejection is one click away.
   It runs in the browser and multiplies the first number by ten, or prepends a claim
   no resume fact supports. Typing your own edit goes through the same gate. */
export function overstate(text: string): string {
  const n = text.match(/\d[\d,]*/);
  if (n) return text.replace(n[0], String(Number(n[0].replace(/,/g, "")) * 10));
  return "Directed the entire engineering organisation. " + text;
}

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}
