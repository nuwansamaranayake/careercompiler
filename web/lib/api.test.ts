import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import { ApiError } from "./api";

type Call = { url: string; init: RequestInit };
let calls: Call[] = [];

function respond(status: number, body: unknown, blob = false) {
  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    calls.push({ url, init });
    if (blob) return new Response(body as BodyInit, { status });
    return new Response(JSON.stringify(body), {
      status, headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function sent(i = 0) {
  const { url, init } = calls[i];
  const headers = new Headers(init.headers);
  return {
    url,
    method: init.method ?? "GET",
    auth: headers.get("Authorization"),
    contentType: headers.get("Content-Type"),
    body: typeof init.body === "string" ? JSON.parse(init.body) : init.body,
  };
}

beforeEach(() => { calls = []; });
afterEach(() => { vi.unstubAllGlobals(); });

describe("request mapping (contracts.md, one function per endpoint)", () => {
  it("opens a session without credentials", async () => {
    respond(201, { token: "t", expires_in: 1800 });
    const s = await api.openSession();
    expect(s.token).toBe("t");
    expect(sent()).toMatchObject({ url: "/api/v1/demo/session", method: "POST", auth: null });
  });

  it("uploads a resume as multipart with the bearer and no JSON content type", async () => {
    const named = { candidate_id: 7, chars: 1234, name: "Jordan Alvarez", name_source: "resume_first_line" };
    respond(201, named);
    const file = new File(["%PDF"], "cv.pdf", { type: "application/pdf" });
    const r = await api.uploadResume("tok", file);
    expect(r).toEqual(named);
    const s = sent();
    expect(s).toMatchObject({
      url: "/api/v1/candidates/upload", method: "POST", auth: "Bearer tok", contentType: null });
    const fd = s.body as FormData;
    expect(fd.has("name")).toBe(false);
    expect((fd.get("file") as File).name).toBe("cv.pdf");
  });

  it("creates a candidate from pasted text and sends no name", async () => {
    const named = { candidate_id: 3, name: "Your Name", name_source: "placeholder" };
    respond(201, named);
    expect(await api.createCandidate("tok", "resume body")).toEqual(named);
    const s = sent();
    expect(s).toMatchObject({
      url: "/api/v1/candidates", method: "POST", auth: "Bearer tok",
      contentType: "application/json" });
    expect(s.body).toEqual({ resume_text: "resume body" });
  });

  it("renames a candidate", async () => {
    respond(200, { candidate_id: 3, name: "Jordan Alvarez", name_source: "provided" });
    const r = await api.renameCandidate("tok", 3, "Jordan Alvarez");
    expect(r.name).toBe("Jordan Alvarez");
    expect(sent()).toMatchObject({
      url: "/api/v1/candidates/3", method: "PATCH", body: { name: "Jordan Alvarez" } });
  });

  it("extracts facts with a bodiless POST", async () => {
    respond(201, { stored: 5, rejected_span_anchor: 1 });
    await api.extractFacts("tok", 3);
    expect(sent()).toMatchObject({
      url: "/api/v1/candidates/3/claims/extract", method: "POST", body: undefined });
  });

  it("creates and parses a job", async () => {
    respond(201, { job_id: 9 });
    await api.createJob("tok", "Platform Engineer", "the posting");
    expect(sent(0)).toMatchObject({
      url: "/api/v1/jobs", method: "POST",
      body: { title: "Platform Engineer", description: "the posting" } });
    respond(201, { parsed: 4 });
    expect(await api.parseJob("tok", 9)).toEqual({ parsed: 4 });
    expect(sent(1)).toMatchObject({ url: "/api/v1/jobs/9/requirements/parse", method: "POST" });
  });

  it("runs and reads a fit", async () => {
    respond(201, { fit_report_id: 11, verdict: "apply" });
    await api.runFit("tok", 3, 9);
    expect(sent(0)).toMatchObject({
      url: "/api/v1/fit", method: "POST", body: { candidate_id: 3, job_id: 9 } });
    respond(200, { report: {}, rows: [] });
    await api.getFit("tok", 11);
    expect(sent(1)).toMatchObject({ url: "/api/v1/fit/11", method: "GET", auth: "Bearer tok" });
  });

  it("compiles a resume with the chosen budget, and a letter without one", async () => {
    respond(201, { document_id: 21 });
    await api.compileResume("tok", 3, 9, 14);
    expect(sent(0)).toMatchObject({
      url: "/api/v1/compile", method: "POST",
      body: { candidate_id: 3, job_id: 9, budget_lines: 14 } });
    await api.compileLetter("tok", 3, 9);
    expect(sent(1)).toMatchObject({
      url: "/api/v1/cover-letter", method: "POST", body: { candidate_id: 3, job_id: 9 } });
  });

  it("reads provenance, checks a line, and saves a line", async () => {
    respond(200, { bullets: [] });
    await api.getDocument("tok", 21);
    expect(sent(0)).toMatchObject({ url: "/api/v1/compile/21", method: "GET" });
    await api.checkLine("tok", 21, "edited", ["c1"]);
    expect(sent(1)).toMatchObject({
      url: "/api/v1/compile/check", method: "POST",
      body: { document_id: 21, text: "edited", cites: ["c1"] } });
    await api.saveLine("tok", 21, 2, "edited");
    expect(sent(2)).toMatchObject({
      url: "/api/v1/compile/21/bullets/2", method: "PUT", body: { text: "edited" } });
  });

  it("builds the interview pack as JSON and downloads it as docx", async () => {
    respond(201, { document_id: 21, bullets: [], gaps: [] });
    await api.buildPack("tok", 21);
    expect(sent(0)).toMatchObject({
      url: "/api/v1/interview-pack", method: "POST", body: { document_id: 21 } });
    respond(201, "PK-docx-bytes", true);
    const blob = await api.downloadPack("tok", 21);
    expect(await blob.text()).toBe("PK-docx-bytes");
    expect(sent(1)).toMatchObject({
      url: "/api/v1/interview-pack", method: "POST",
      body: { document_id: 21, format: "docx" } });
  });

  it("downloads a compiled document in the requested format", async () => {
    respond(200, "%PDF-bytes", true);
    const blob = await api.downloadDocument("tok", 21, "pdf");
    expect(await blob.text()).toBe("%PDF-bytes");
    expect(sent(0)).toMatchObject({ url: "/api/v1/compile/21/pdf", auth: "Bearer tok" });
    await api.downloadDocument("tok", 21, "docx");
    expect(sent(1).url).toBe("/api/v1/compile/21/docx");
  });
});

describe("failures are typed, never swallowed", () => {
  async function failure(run: () => Promise<unknown>): Promise<ApiError> {
    try {
      await run();
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      return e as ApiError;
    }
    throw new Error("expected the call to throw");
  }

  it("maps 401 with a token to SESSION_EXPIRED", async () => {
    respond(401, { detail: "missing or invalid bearer token" });
    const e = await failure(() => api.getFit("tok", 1));
    expect(e).toMatchObject({ code: "SESSION_EXPIRED", status: 401, message: "SESSION_EXPIRED" });
  });

  it("maps 429 with a token to BUDGET_EXHAUSTED", async () => {
    respond(429, { detail: "budget" });
    const e = await failure(() => api.runFit("tok", 1, 2));
    expect(e).toMatchObject({ code: "BUDGET_EXHAUSTED", status: 429 });
  });

  it("keeps a 429 on session open as a plain HTTP error with its detail", async () => {
    respond(429, { detail: "too many sessions from this address" });
    const e = await failure(() => api.openSession());
    expect(e).toMatchObject({
      code: "HTTP", status: 429, detail: "too many sessions from this address",
      message: "HTTP 429" });
  });

  it("carries a typed detail object through untouched", async () => {
    const detail = { error: "edit_rejected", entailment: { checked: true, ok: false } };
    respond(422, { detail });
    const e = await failure(() => api.saveLine("tok", 1, 0, "x"));
    expect(e).toMatchObject({ code: "HTTP", status: 422, detail });
  });

  it("survives a non-JSON error body", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>bad gateway</html>", { status: 502 })));
    const e = await failure(() => api.getDocument("tok", 1));
    expect(e).toMatchObject({ code: "HTTP", status: 502, detail: undefined });
  });

  it("maps a thrown fetch to NETWORK", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    const e = await failure(() => api.openSession());
    expect(e).toMatchObject({ code: "NETWORK", status: 0, detail: "TypeError: Failed to fetch" });
  });

  it("surfaces a failed download as an error, not an empty file", async () => {
    respond(403, { detail: "forbidden" });
    const e = await failure(() => api.downloadDocument("tok", 21, "pdf"));
    expect(e).toMatchObject({ code: "HTTP", status: 403, detail: "forbidden" });
  });
});
