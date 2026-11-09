/* Wire types. Each mirrors one response in contracts.md; nothing here is invented
   client-side. */

export type SeededJob = { job_id: number; fit_report_id: number; title: string; verdict: string };

export type Session = {
  token: string;
  expires_in: number;
  request_budget: number;
  synthetic: boolean;
  candidate_id: number;
  candidate_name: string;
  jobs: SeededJob[];
};

/* A session as this browser tab holds it: the wire session plus the wall-clock moment
   it stops being valid, so a stale tab drops it before the server has to refuse it. */
export type StoredSession = Session & { expires_at: number };

/* Who the documents are signed as, and how the server came to that name. */
export type NameSource = "provided" | "resume_first_line" | "placeholder";
export type Named = { candidate_id: number; name: string; name_source: NameSource };

export type RejectedFact = { claim_key: string; statement: string; quote: string | null };

export type ExtractResult = {
  stored: number;
  rejected_span_anchor: number;
  rejected?: RejectedFact[];
};

export type FitSummary = {
  fit_report_id: number;
  verdict: string;
  matched: number;
  partial: number;
  gaps: number;
  disqualifying_gaps: string[];
};

export type FitRow = {
  req_key: string;
  /* The requirement in the posting's own words; null if it was removed since. */
  requirement: string | null;
  must_have: boolean;
  status: string;
  direct: boolean;
  score: number;
  explanation: string | null;
};

export type FitReport = {
  report: {
    verdict: string;
    matched: number;
    partial: number;
    gaps: number;
    disqualifying: string[];
    case_against: string;
  };
  rows: FitRow[];
};

export type Line = { position: number; text: string; cites: string[]; entailment: number | null };

export type Fact = {
  claim_id: string;
  claim_key: string | null;
  statement: string | null;
  provenance: string | null;
};

export type ProvLine = Line & { document_id: number; facts: Fact[] };

export type Omission = { claim_key: string; reason: string; detail: string };

export type Gate = { model: string; revision: string; threshold: number };

export type CompiledResume = {
  document_id: number;
  bullets: Line[];
  omitted: Omission[];
  covered_must: string[];
  uncovered_must: string[];
  used_lines: number;
  budget_lines: number;
  gate: Gate;
};

export type CompiledLetter = {
  document_id: number;
  kind: string;
  greeting: string;
  opening: string;
  closing: string;
  signoff: string;
  sentences: Line[];
  omitted: Omission[];
  gate: Gate;
};

export type Provenance = { bullets: ProvLine[] };

export type GateVerdict = {
  ok: boolean;
  reference_integrity: { ok: boolean; violations: { failure: string; detail: string }[] };
  entailment: {
    checked: boolean;
    ok?: boolean;
    score?: number | null;
    threshold?: number;
    violations?: { detail: string; premise: string }[];
  };
};

export type SavedLine = {
  document_id: number;
  position: number;
  saved: true;
  text: string;
  cites: string[];
  entailment: number | null;
};

export type Pack = {
  document_id: number;
  job_title: string;
  verdict: string;
  case_against: string | null;
  note: string;
  bullets: {
    text: string;
    facts: { key: string; statement: string; provenance: string }[];
    metrics: string[];
    questions: string[];
  }[];
  gaps: {
    requirement: string;
    case: string;
    status: string;
    must_have: boolean;
    questions: string[];
  }[];
};

export type ResumeInput = { kind: "file"; file: File } | { kind: "text"; text: string };

export type IntakeInput = { resume: ResumeInput | null; jobTitle: string; jobText: string };

export type StepId = "session" | "resume" | "facts" | "job" | "requirements" | "match";

export type StepEvent = { id: StepId; state: "start" | "done"; note?: string };

export type IntakeResult = {
  session: StoredSession;
  candidateId: number;
  name: string;
  nameSource: NameSource;
  jobId: number;
  jobTitle: string;
  facts: { usable: number; rejected: number; rejects: RejectedFact[] };
  requirements: number;
  fit: FitSummary;
};
