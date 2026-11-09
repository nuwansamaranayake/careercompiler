import { describe, expect, it, vi } from "vitest";
import { ApiError } from "./api";
import {
  DEFAULT_JOB_TITLE, MAX_UPLOAD_BYTES, MIN_JOB_CHARS, MIN_RESUME_CHARS, PipelineStop, STEPS,
  runIntake, validateIntake, validateJob, validateResume,
  type PipelineDeps,
} from "./pipeline";
import { stamp } from "./session";
import type { IntakeInput, Session, StepEvent } from "./types";

const T0 = 1_800_000_000_000;
const WIRE: Session = {
  token: "tok", expires_in: 1800, request_budget: 60, synthetic: true,
  candidate_id: 1, candidate_name: "Jordan Alvarez", jobs: [],
};
const RESUME_TEXT = "Built and operated Python services in production for 6 years. ".repeat(5);
const JOB_TEXT = "We need Python services in production and Kubernetes experience. ".repeat(3);

function file(name: string, size: number): File {
  const f = new File(["x"], name);
  Object.defineProperty(f, "size", { value: size });
  return f;
}

function deps(over: Partial<PipelineDeps["api"]> = {}, session = null as PipelineDeps["session"]) {
  const api = {
    openSession: vi.fn(async () => WIRE),
    uploadResume: vi.fn(async () => ({
      candidate_id: 41, chars: 5321, name: "Your Name", name_source: "placeholder" as const })),
    createCandidate: vi.fn(async () => ({
      candidate_id: 42, name: "Jordan Alvarez", name_source: "resume_first_line" as const })),
    extractFacts: vi.fn(async () => ({
      stored: 12, rejected_span_anchor: 2,
      rejected: [{ claim_key: "k", statement: "s", quote: "q" }] })),
    createJob: vi.fn(async () => ({ job_id: 77 })),
    parseJob: vi.fn(async () => ({ parsed: 6 })),
    runFit: vi.fn(async () => ({
      fit_report_id: 9, verdict: "apply", matched: 4, partial: 1, gaps: 1,
      disqualifying_gaps: [] })),
    ...over,
  };
  return { api, now: () => T0, session } satisfies PipelineDeps;
}

const TEXT_INPUT: IntakeInput = {
  resume: { kind: "text", text: RESUME_TEXT }, jobTitle: "  Platform Engineer ", jobText: JOB_TEXT,
};

describe("validation", () => {
  it("requires a resume", () => {
    expect(validateResume(null)).toMatch(/Add your resume/);
  });
  it("accepts pdf and docx, case-insensitively, up to the limit", () => {
    expect(validateResume({ kind: "file", file: file("CV.PDF", 1000) })).toBeUndefined();
    expect(validateResume({ kind: "file", file: file("cv.docx", MAX_UPLOAD_BYTES) })).toBeUndefined();
  });
  it("rejects other types, oversize and empty files", () => {
    expect(validateResume({ kind: "file", file: file("cv.txt", 10) })).toBe("PDF or docx only.");
    expect(validateResume({ kind: "file", file: file("cv.pdf", MAX_UPLOAD_BYTES + 1) }))
      .toBe("That file is over the 2 MB limit.");
    expect(validateResume({ kind: "file", file: file("cv.pdf", 0) })).toBe("That file is empty.");
  });
  it("needs enough pasted resume text", () => {
    expect(validateResume({ kind: "text", text: "  short  " })).toMatch(String(MIN_RESUME_CHARS));
    expect(validateResume({ kind: "text", text: "x".repeat(MIN_RESUME_CHARS) })).toBeUndefined();
  });
  it("needs enough job text", () => {
    expect(validateJob("   ")).toMatch(String(MIN_JOB_CHARS));
    expect(validateJob("y".repeat(MIN_JOB_CHARS))).toBeUndefined();
  });
  it("collects both errors, or none", () => {
    expect(validateIntake({ resume: null, jobTitle: "", jobText: "" }))
      .toEqual({ resume: expect.any(String), job: expect.any(String) });
    expect(validateIntake(TEXT_INPUT)).toEqual({});
  });
});

describe("runIntake", () => {
  it("runs six steps in order and reports each start and finish", async () => {
    const d = deps();
    const events: StepEvent[] = [];
    const result = await runIntake(d, TEXT_INPUT, (e) => events.push(e));

    expect(events.map((e) => `${e.id}:${e.state}`)).toEqual(
      STEPS.flatMap((s) => [`${s.id}:start`, `${s.id}:done`]));
    expect(events.filter((e) => e.state === "done").map((e) => e.note)).toEqual([
      "60 requests, expires on its own",
      "pasted text",
      "10 facts, 2 rejected on anchoring",
      "Platform Engineer",
      "6 requirements",
      "4 matched, 1 partial, 1 gap",
    ]);
    expect(result).toEqual({
      session: stamp(WIRE, T0),
      candidateId: 42, name: "Jordan Alvarez", nameSource: "resume_first_line",
      jobId: 77, jobTitle: "Platform Engineer",
      facts: { usable: 10, rejected: 2, rejects: [{ claim_key: "k", statement: "s", quote: "q" }] },
      requirements: 6,
      fit: { fit_report_id: 9, verdict: "apply", matched: 4, partial: 1, gaps: 1,
        disqualifying_gaps: [] },
    });
    expect(d.api.createCandidate).toHaveBeenCalledWith("tok", RESUME_TEXT);
    expect(d.api.uploadResume).not.toHaveBeenCalled();
    expect(d.api.createJob).toHaveBeenCalledWith("tok", "Platform Engineer", JOB_TEXT);
    expect(d.api.runFit).toHaveBeenCalledWith("tok", 42, 77);
  });

  it("uploads a file resume and reports its extracted size", async () => {
    const d = deps({
      extractFacts: vi.fn(async () => ({ stored: 1, rejected_span_anchor: 0 })),
    });
    const f = file("cv.pdf", 9000);
    const events: StepEvent[] = [];
    const result = await runIntake(
      d, { resume: { kind: "file", file: f }, jobTitle: "", jobText: JOB_TEXT },
      (e) => events.push(e));

    expect(d.api.uploadResume).toHaveBeenCalledWith("tok", f);
    expect(d.api.createCandidate).not.toHaveBeenCalled();
    expect(events.find((e) => e.id === "resume" && e.state === "done")?.note)
      .toBe("5,321 characters of text");
    expect(events.find((e) => e.id === "facts" && e.state === "done")?.note).toBe("1 fact");
    expect(result.candidateId).toBe(41);
    expect(result).toMatchObject({ name: "Your Name", nameSource: "placeholder" });
    expect(result.jobTitle).toBe(DEFAULT_JOB_TITLE);
    expect(result.facts).toEqual({ usable: 1, rejected: 0, rejects: [] });
    expect(d.api.createJob).toHaveBeenCalledWith("tok", DEFAULT_JOB_TITLE, JOB_TEXT);
  });

  it("reuses a live session instead of opening another", async () => {
    const live = stamp({ ...WIRE, token: "existing" }, T0 - 5000);
    const d = deps({}, live);
    const result = await runIntake(d, TEXT_INPUT, () => {});
    expect(d.api.openSession).not.toHaveBeenCalled();
    expect(result.session).toBe(live);
    expect(d.api.createCandidate).toHaveBeenCalledWith("existing", RESUME_TEXT);
  });

  it("stops before any request when there is no resume", async () => {
    const d = deps();
    await expect(runIntake(d, { ...TEXT_INPUT, resume: null }, () => {}))
      .rejects.toMatchObject({ name: "PipelineStop", step: "resume" });
    expect(d.api.openSession).not.toHaveBeenCalled();
  });

  it("stops when every extracted fact failed to anchor", async () => {
    const d = deps({
      extractFacts: vi.fn(async () => ({ stored: 3, rejected_span_anchor: 3 })),
    });
    const events: StepEvent[] = [];
    const err = await runIntake(d, TEXT_INPUT, (e) => events.push(e)).catch((e) => e);
    expect(err).toBeInstanceOf(PipelineStop);
    expect(err.step).toBe("facts");
    expect(err.message).toMatch(/No facts could be anchored/);
    expect(d.api.createJob).not.toHaveBeenCalled();
    expect(events.at(-1)).toEqual({
      id: "facts", state: "done", note: "0 facts, 3 rejected on anchoring" });
  });

  it("stops when the posting yields no requirements", async () => {
    const d = deps({ parseJob: vi.fn(async () => ({ parsed: 0 })) });
    const err = await runIntake(d, TEXT_INPUT, () => {}).catch((e) => e);
    expect(err).toBeInstanceOf(PipelineStop);
    expect(err.step).toBe("requirements");
    expect(err.message).toMatch(/No requirements could be read/);
    expect(d.api.runFit).not.toHaveBeenCalled();
  });

  it("lets an API failure through untouched, leaving the step started and not done", async () => {
    const boom = new ApiError("HTTP", 503, "LLM extraction requires OPENROUTER_API_KEY");
    const d = deps({ extractFacts: vi.fn(async () => { throw boom; }) });
    const events: StepEvent[] = [];
    await expect(runIntake(d, TEXT_INPUT, (e) => events.push(e))).rejects.toBe(boom);
    expect(events.at(-1)).toEqual({ id: "facts", state: "start" });
  });
});
