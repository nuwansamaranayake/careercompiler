/* One function per backend endpoint (contracts.md, Doctrine Rule 6). Nothing here
   retries, caches, or substitutes data: a failed call throws an ApiError carrying the
   server's own status and typed detail, and the UI shows it. */
import type {
  CompiledLetter, CompiledResume, ExtractResult, FitReport, FitSummary, GateVerdict, Named,
  Pack, Provenance, SavedLine, Session,
} from "./types";

export type ApiCode = "SESSION_EXPIRED" | "BUDGET_EXHAUSTED" | "HTTP" | "NETWORK";

export class ApiError extends Error {
  readonly code: ApiCode;
  readonly status: number;
  readonly detail: unknown;

  constructor(code: ApiCode, status: number, detail: unknown) {
    super(code === "HTTP" ? `HTTP ${status}` : code);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.detail = detail;
  }
}

async function send(path: string, init: RequestInit): Promise<Response> {
  let r: Response;
  try {
    r = await fetch(path, init);
  } catch (e) {
    throw new ApiError("NETWORK", 0, String(e));
  }
  if (r.ok) return r;
  const body = (await r.json().catch(() => ({}))) as { detail?: unknown };
  // 401 and 429 end a session only when a token was presented: opening a session is
  // unauthenticated, and its 429 is the per-address rate limit, not a spent budget.
  const authed = new Headers(init.headers).has("Authorization");
  if (authed && r.status === 401) throw new ApiError("SESSION_EXPIRED", 401, body.detail);
  if (authed && r.status === 429) throw new ApiError("BUDGET_EXHAUSTED", 429, body.detail);
  throw new ApiError("HTTP", r.status, body.detail);
}

function bearer(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

async function json<T>(token: string, path: string, method = "GET", body?: unknown): Promise<T> {
  const r = await send(path, {
    method,
    headers: { "Content-Type": "application/json", ...bearer(token) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return (await r.json()) as T;
}

export async function openSession(): Promise<Session> {
  const r = await send("/api/v1/demo/session", { method: "POST" });
  return (await r.json()) as Session;
}

/* No name is sent with a resume: the server reads it from the resume's first line and
   says how it got it (name_source), and the person can correct it afterwards. */
export async function uploadResume(token: string, file: File): Promise<Named & { chars: number }> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await send("/api/v1/candidates/upload", {
    method: "POST", headers: bearer(token), body: fd,
  });
  return (await r.json()) as Named & { chars: number };
}

export function createCandidate(token: string, resumeText: string) {
  return json<Named>(token, "/api/v1/candidates", "POST", { resume_text: resumeText });
}

export function renameCandidate(token: string, candidateId: number, name: string) {
  return json<Named>(token, `/api/v1/candidates/${candidateId}`, "PATCH", { name });
}

export function extractFacts(token: string, candidateId: number) {
  return json<ExtractResult>(token, `/api/v1/candidates/${candidateId}/claims/extract`, "POST");
}

export function createJob(token: string, title: string, description: string) {
  return json<{ job_id: number }>(token, "/api/v1/jobs", "POST", { title, description });
}

export function parseJob(token: string, jobId: number) {
  return json<{ parsed: number }>(token, `/api/v1/jobs/${jobId}/requirements/parse`, "POST");
}

export function runFit(token: string, candidateId: number, jobId: number) {
  return json<FitSummary>(token, "/api/v1/fit", "POST",
    { candidate_id: candidateId, job_id: jobId });
}

export function getFit(token: string, reportId: number) {
  return json<FitReport>(token, `/api/v1/fit/${reportId}`);
}

export function compileResume(
  token: string, candidateId: number, jobId: number, budgetLines: number,
) {
  return json<CompiledResume>(token, "/api/v1/compile", "POST",
    { candidate_id: candidateId, job_id: jobId, budget_lines: budgetLines });
}

export function compileLetter(token: string, candidateId: number, jobId: number) {
  return json<CompiledLetter>(token, "/api/v1/cover-letter", "POST",
    { candidate_id: candidateId, job_id: jobId });
}

export function getDocument(token: string, documentId: number) {
  return json<Provenance>(token, `/api/v1/compile/${documentId}`);
}

export function checkLine(token: string, documentId: number, text: string, cites: string[]) {
  return json<GateVerdict>(token, "/api/v1/compile/check", "POST",
    { document_id: documentId, text, cites });
}

export function saveLine(token: string, documentId: number, position: number, text: string) {
  return json<SavedLine>(token, `/api/v1/compile/${documentId}/bullets/${position}`, "PUT",
    { text });
}

export function buildPack(token: string, documentId: number) {
  return json<Pack>(token, "/api/v1/interview-pack", "POST", { document_id: documentId });
}

export async function downloadDocument(
  token: string, documentId: number, format: "pdf" | "docx",
): Promise<Blob> {
  const r = await send(`/api/v1/compile/${documentId}/${format}`, { headers: bearer(token) });
  return r.blob();
}

export async function downloadPack(token: string, documentId: number): Promise<Blob> {
  const r = await send("/api/v1/interview-pack", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...bearer(token) },
    body: JSON.stringify({ document_id: documentId, format: "docx" }),
  });
  return r.blob();
}
