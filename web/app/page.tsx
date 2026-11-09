/* The landing page. Every sentence here traces to docs/agent-legibility/ (the 2026-08-03
   truth layer and its 2026-11-09 addendum). The limits block is verbatim from EVAL.md
   and the deploy gate asserts it stays that way. */
import Link from "next/link";
import { LIMITS } from "@/lib/limits";

export default function Landing() {
  return (
    <>
      <section className="hero">
        <div className="reveal">
          <p className="eyebrow">Two inputs · three documents · every sentence cited</p>
          <h1>A resume compiler with <em>compile errors.</em></h1>
          <p className="lede">
            Bring a resume and a job description. Get an honest verdict, a tailored resume,
            and a cover letter. Every sentence cites a fact from your own resume. A sentence
            that claims more than its evidence supports fails the build.
          </p>
          <div className="row actions">
            <Link href="/workspace/" className="btn">Open the workspace</Link>
            <Link href="/demo/" className="btn ghost">Try the sample</Link>
            <Link href="/guide/" className="small">How to use it →</Link>
          </div>
          <p className="small dim" style={{ marginTop: "1.2rem" }}>
            No sign-up. Sessions expire on their own after 30 minutes.
          </p>
        </div>

        <div className="specimen" aria-label="How the gate scores a sentence">
          <span className="stamp bad sm">Compile error</span>
          <div className="sheet">
            <p className="for" style={{ marginTop: 0 }}>Entailment gate · measured, EVAL.md</p>
            <div className="measure" style={{ color: "var(--sheet-green)" }}>
              <span>faithful sentence</span>
              <span className="bar"><i style={{ width: "99.76%" }} /><span className="tick" /></span>
              <span>0.9976</span>
            </div>
            <div className="measure" style={{ color: "var(--sheet-red)" }}>
              <span>inflated verb&nbsp;&nbsp;&nbsp;&nbsp;</span>
              <span className="bar"><i style={{ width: "0.6%" }} /><span className="tick" /></span>
              <span>0.0015</span>
            </div>
            <p className="frame small" style={{ margin: "1.1rem 0 0" }}>
              The mark is the 0.7 threshold. A sentence scored below it against its own
              cited facts does not reach the page. There is no weaker fallback.
            </p>
          </div>
        </div>
      </section>

      <section className="section">
        <h2>What you leave with</h2>
        <div className="grid3 numbered">
          <div className="card flat">
            <h3>Career match</h3>
            <p className="dim">
              Apply, or do not apply. Each requirement in the posting is marked matched,
              partial, or gap, with the evidence named. When a must-have has no evidence,
              the case against applying is stated plainly.
            </p>
          </div>
          <div className="card flat">
            <h3>Tailored resume</h3>
            <p className="dim">
              A solver picks which of your facts fit this job under a page budget. Edit any
              line: the gate checks your edit, and a pass is saved into the PDF and docx.
            </p>
          </div>
          <div className="card flat">
            <h3>Cover letter</h3>
            <p className="dim">
              Compiled through the same two gates as the resume. The greeting and closing
              are fixed template text. The evidence sentences each cite their facts.
            </p>
          </div>
        </div>
      </section>

      <section className="section">
        <h2>How it stays honest</h2>
        <div className="grid3 numbered">
          <div>
            <h3>Facts, anchored</h3>
            <p className="dim">
              Your resume is read into atomic facts. Each fact must quote your document
              verbatim. A quote that cannot be found is stored rejected and never used.
            </p>
          </div>
          <div>
            <h3>Selection, not rewording</h3>
            <p className="dim">
              The job decides which facts make the page. The model that phrases them never
              sees the posting, so wording does not drift toward what the employer wants to
              hear.
            </p>
          </div>
          <div>
            <h3>Two gates, no bypass</h3>
            <p className="dim">
              A sentence that cites nothing, or carries a number found in no cited fact,
              fails. Then a pinned entailment model scores the sentence against its facts.
              If the model cannot run, the compile fails with a typed error.
            </p>
          </div>
        </div>
      </section>

      <section className="section">
        <h2>Published limits</h2>
        <div className="note limits">
          <p style={{ margin: 0 }}>{LIMITS}</p>
        </div>
      </section>

      <section className="section">
        <div className="grid2">
          <div>
            <h2>Not for</h2>
            <p className="dim">
              Not an ATS keyword stuffer. Not a writer that invents achievements. Not a
              percent-match scorer. It will tell you not to apply.
            </p>
          </div>
          <div>
            <h2>Your data</h2>
            <p className="dim">
              A resume is personal data. It stays in your session&apos;s own tenant, readable
              only with that session&apos;s token, and is deleted by a retention sweep once it
              is older than 7 days.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
