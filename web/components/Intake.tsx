"use client";
/* Step one: the only two things the product needs from a person. */
import { useRef, useState } from "react";
import Link from "next/link";
import { fileSize } from "@/lib/format";
import { validateIntake, type IntakeErrors } from "@/lib/pipeline";
import type { IntakeInput } from "@/lib/types";

type Mode = "file" | "text";

export function Intake({ initial, onSubmit }: {
  initial: IntakeInput; onSubmit: (input: IntakeInput) => void;
}) {
  const [mode, setMode] = useState<Mode>(initial.resume?.kind === "text" ? "text" : "file");
  const [file, setFile] = useState<File | null>(
    initial.resume?.kind === "file" ? initial.resume.file : null);
  const [resumeText, setResumeText] = useState(
    initial.resume?.kind === "text" ? initial.resume.text : "");
  const [jobTitle, setJobTitle] = useState(initial.jobTitle);
  const [jobText, setJobText] = useState(initial.jobText);
  const [errors, setErrors] = useState<IntakeErrors>({});
  const [over, setOver] = useState(false);
  const picker = useRef<HTMLInputElement>(null);

  const current = (): IntakeInput => ({
    resume: mode === "file"
      ? (file ? { kind: "file", file } : null)
      : (resumeText.trim() ? { kind: "text", text: resumeText } : null),
    jobTitle,
    jobText,
  });

  const submit = () => {
    const input = current();
    const found = validateIntake(input);
    setErrors(found);
    if (!found.resume && !found.job) onSubmit(input);
  };

  return (
    <>
      <p className="eyebrow">Workspace · step 1 of 2</p>
      <h1 style={{ fontSize: "clamp(2rem, 4vw, 3rem)" }}>Bring two things.</h1>
      <p className="lede">
        Your resume and the job description. That is the whole form. The verdict, the
        tailored resume, and the cover letter are all built from these.
      </p>

      <div className="intake" style={{ marginTop: "2rem" }}>
        <section className="card" aria-labelledby="resume-h">
          <div className="row spread">
            <h3 id="resume-h">1 · Your resume</h3>
            <div className="seg" role="group" aria-label="How to provide the resume">
              <button type="button" aria-pressed={mode === "file"} data-testid="resume-file-tab"
                onClick={() => setMode("file")}>Upload file</button>
              <button type="button" aria-pressed={mode === "text"} data-testid="resume-paste-tab"
                onClick={() => setMode("text")}>Paste text</button>
            </div>
          </div>

          {mode === "file" ? (
            <div className="grow">
              <input ref={picker} type="file" accept=".pdf,.docx" className="sr-only"
                data-testid="resume-file" aria-label="Resume file, PDF or docx"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              {file ? (
                <div className="filecard" data-testid="resume-file-chosen">
                  <span className="ext">{file.name.split(".").pop()?.toUpperCase()}</span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <strong style={{ wordBreak: "break-all" }}>{file.name}</strong><br />
                    <span className="small dim">{fileSize(file.size)}</span>
                  </span>
                  <button type="button" className="quiet"
                    onClick={() => { setFile(null); if (picker.current) picker.current.value = ""; }}>
                    Remove
                  </button>
                </div>
              ) : (
                <div className="drop" role="button" tabIndex={0} data-over={over}
                  onClick={() => picker.current?.click()}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") picker.current?.click(); }}
                  onDragOver={(e) => { e.preventDefault(); setOver(true); }}
                  onDragLeave={() => setOver(false)}
                  onDrop={(e) => {
                    e.preventDefault(); setOver(false);
                    setFile(e.dataTransfer.files?.[0] ?? null);
                  }}>
                  <div>
                    <div className="big">Drop your resume here</div>
                    <div className="small dim">or click to choose · PDF or docx · 2 MB limit</div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="grow">
              <label className="field sr-only" htmlFor="resume-text">Resume text</label>
              <textarea id="resume-text" data-testid="resume-text" value={resumeText}
                placeholder="Paste the full text of your resume…"
                onChange={(e) => setResumeText(e.target.value)} />
            </div>
          )}
          {errors.resume && <p className="err small" role="alert" data-testid="resume-error">{errors.resume}</p>}
          <p className="tiny dim" style={{ margin: 0 }}>
            Every fact extracted must quote this document word for word. A scanned image
            has no text to quote, so paste the text instead.
          </p>
        </section>

        <section className="card" aria-labelledby="job-h">
          <h3 id="job-h">2 · The job description</h3>
          <div>
            <label className="field" htmlFor="job-title">Job title <span className="dim" style={{ fontWeight: 400 }}>(optional)</span></label>
            <input id="job-title" type="text" data-testid="job-title" value={jobTitle}
              placeholder="e.g. Platform Engineer"
              onChange={(e) => setJobTitle(e.target.value)} />
          </div>
          <div className="grow">
            <label className="field" htmlFor="job-text">Posting text</label>
            <textarea id="job-text" data-testid="job-text" value={jobText}
              placeholder="Paste the full posting, including the qualifications section…"
              onChange={(e) => setJobText(e.target.value)} />
          </div>
          {errors.job && <p className="err small" role="alert" data-testid="job-error">{errors.job}</p>}
          <p className="tiny dim" style={{ margin: 0 }}>
            The posting is read into typed requirements. You will see every one it found.
          </p>
        </section>
      </div>

      <div className="go">
        <p className="small dim" style={{ maxWidth: "36rem", margin: 0 }}>
          Your resume is personal data. It is stored in a private session tenant and deleted
          by a retention sweep once it is older than 7 days.{" "}
          Nothing to hand? <Link href="/demo/">Try the synthetic sample</Link>.
        </p>
        <button type="button" data-testid="analyze" onClick={submit}>
          Analyze my fit →
        </button>
      </div>
    </>
  );
}
