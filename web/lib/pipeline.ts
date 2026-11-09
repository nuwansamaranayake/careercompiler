/* The intake pipeline: two inputs in, a fit verdict out. Six steps, each one real API
   call, reported as it starts and as it finishes. The pipeline stops, with the reason,
   the moment a step produces nothing to work with. It never continues on empty data. */
import * as api from "./api";
import { plural } from "./format";
import { stamp } from "./session";
import type {
  IntakeInput, IntakeResult, Named, ResumeInput, StepEvent, StepId, StoredSession,
} from "./types";

export const STEPS: { id: StepId; label: string }[] = [
  { id: "session", label: "Open a private session" },
  { id: "resume", label: "Store the resume" },
  { id: "facts", label: "Extract facts, each anchored to a quote" },
  { id: "job", label: "Store the job description" },
  { id: "requirements", label: "Read the posting into requirements" },
  { id: "match", label: "Match evidence to requirements" },
];

export const MAX_UPLOAD_BYTES = 2_000_000;
export const MIN_RESUME_CHARS = 200;
export const MIN_JOB_CHARS = 120;
export const DEFAULT_JOB_TITLE = "The role you pasted";

export type IntakeErrors = { resume?: string; job?: string };

export function validateResume(resume: ResumeInput | null): string | undefined {
  if (!resume) return "Add your resume: drop a PDF or docx, or paste the text.";
  if (resume.kind === "file") {
    const name = resume.file.name.toLowerCase();
    if (!name.endsWith(".pdf") && !name.endsWith(".docx")) return "PDF or docx only.";
    if (resume.file.size > MAX_UPLOAD_BYTES) return "That file is over the 2 MB limit.";
    if (resume.file.size === 0) return "That file is empty.";
    return undefined;
  }
  if (resume.text.trim().length < MIN_RESUME_CHARS) {
    return `Paste the full resume text (at least ${MIN_RESUME_CHARS} characters).`;
  }
  return undefined;
}

export function validateJob(jobText: string): string | undefined {
  if (jobText.trim().length < MIN_JOB_CHARS) {
    return `Paste the full job description (at least ${MIN_JOB_CHARS} characters), ` +
      "including the qualifications section.";
  }
  return undefined;
}

export function validateIntake(input: IntakeInput): IntakeErrors {
  const errors: IntakeErrors = {};
  const resume = validateResume(input.resume);
  const job = validateJob(input.jobText);
  if (resume) errors.resume = resume;
  if (job) errors.job = job;
  return errors;
}

/* A step that ran and produced nothing usable. Not a server error: the request
   succeeded, and continuing would mean matching against nothing. */
export class PipelineStop extends Error {
  readonly step: StepId;

  constructor(step: StepId, message: string) {
    super(message);
    this.name = "PipelineStop";
    this.step = step;
  }
}

export type PipelineDeps = {
  api: Pick<typeof api, "openSession" | "uploadResume" | "createCandidate" | "extractFacts"
    | "createJob" | "parseJob" | "runFit">;
  now: () => number;
  /* An already-open live session is reused, so a second analysis costs no session. */
  session: StoredSession | null;
};

export async function runIntake(
  deps: PipelineDeps, input: IntakeInput, onStep: (e: StepEvent) => void,
): Promise<IntakeResult> {
  const { resume } = input;
  if (!resume) throw new PipelineStop("resume", "No resume was provided.");

  async function step<T>(id: StepId, run: () => Promise<T>, note: (r: T) => string): Promise<T> {
    onStep({ id, state: "start" });
    const result = await run();
    onStep({ id, state: "done", note: note(result) });
    return result;
  }

  const session = await step("session",
    async () => deps.session ?? stamp(await deps.api.openSession(), deps.now()),
    (s) => `${s.request_budget} requests, expires on its own`);
  const token = session.token;

  const stored = await step("resume",
    async (): Promise<Named & { chars?: number }> => resume.kind === "file"
      ? deps.api.uploadResume(token, resume.file)
      : deps.api.createCandidate(token, resume.text),
    (r) => r.chars == null ? "pasted text" : `${r.chars.toLocaleString("en-US")} characters of text`);
  const candidateId = stored.candidate_id;

  // The server's `stored` counts every extracted claim, including the ones it stored as
  // rejected. Usable facts are the difference; that is the number worth showing.
  const usableOf = (f: { stored: number; rejected_span_anchor: number }) =>
    f.stored - f.rejected_span_anchor;
  const facts = await step("facts",
    () => deps.api.extractFacts(token, candidateId),
    (f) => f.rejected_span_anchor > 0
      ? `${plural(usableOf(f), "fact")}, ${f.rejected_span_anchor} rejected on anchoring`
      : plural(usableOf(f), "fact"));
  const usable = usableOf(facts);
  if (usable <= 0) {
    throw new PipelineStop("facts",
      "No facts could be anchored to your resume text, so there is nothing to match. " +
      "If this is a scanned PDF, paste the text instead.");
  }

  const jobTitle = input.jobTitle.trim() || DEFAULT_JOB_TITLE;
  const job = await step("job",
    () => deps.api.createJob(token, jobTitle, input.jobText),
    () => jobTitle);

  const parsed = await step("requirements",
    () => deps.api.parseJob(token, job.job_id),
    (p) => plural(p.parsed, "requirement"));
  if (parsed.parsed === 0) {
    throw new PipelineStop("requirements",
      "No requirements could be read out of that text, so the matcher has nothing to " +
      "match against. Paste the full posting, including the qualifications section.");
  }

  const fit = await step("match",
    () => deps.api.runFit(token, candidateId, job.job_id),
    (f) => `${f.matched} matched, ${f.partial} partial, ${plural(f.gaps, "gap")}`);

  return {
    session,
    candidateId,
    name: stored.name,
    nameSource: stored.name_source,
    jobId: job.job_id,
    jobTitle,
    facts: {
      usable,
      rejected: facts.rejected_span_anchor,
      rejects: facts.rejected ?? [],
    },
    requirements: parsed.parsed,
    fit,
  };
}
