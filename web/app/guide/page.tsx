/* The visual guide. One section per task, numbered steps, a real screenshot per step.
   The screenshots are captured from the running interface by scripts/capture_guide.py
   on synthetic data with a scripted stand-in for the language model, and say so. */
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Guide — how to use CareerCompiler",
  description:
    "Step by step: enter a resume and a job description, read the career match verdict, " +
    "compile and edit a tailored resume, and compile a cover letter.",
};

type Step = { title: string; body: React.ReactNode; shot: string; alt: string; caption: string };
type Task = { id: string; n: string; title: string; lead: string; steps: Step[] };

const TASKS: Task[] = [
  {
    id: "start", n: "Start", title: "Enter your resume and the job description",
    lead: "Two inputs. Nothing else is asked for, and there is no account to create.",
    steps: [
      {
        title: "Add your resume",
        body: <>Open the <Link href="/workspace/">workspace</Link>. Drop a PDF or docx on the left card, or switch to <strong>Paste text</strong> and paste the resume. Files are limited to 2 MB. A scanned image has no text, so paste instead.</>,
        shot: "01-intake-empty.webp", alt: "The workspace intake screen with an empty resume card and an empty job description card",
        caption: "The intake screen. Resume on the left, job description on the right.",
      },
      {
        title: "Paste the job description",
        body: <>Paste the full posting on the right, including the qualifications section. The job title fills in from the posting&apos;s first line. Correct it if it is wrong, because the cover letter names the role with it. Then press <strong>Analyze my fit</strong>.</>,
        shot: "02-intake-filled.webp", alt: "The intake screen with resume text pasted and a job description pasted",
        caption: "Both inputs filled in. One button runs everything.",
      },
      {
        title: "Watch the build",
        body: <>Six steps run in order: a private session opens, the resume is stored, facts are extracted (each must quote your document word for word), the posting is stored and read into requirements, and your evidence is matched. If a step finds nothing to work with, the build stops and says why.</>,
        shot: "03-build-log.webp", alt: "The build log showing six pipeline steps with check marks and counts",
        caption: "The build log. Every line is one real request, with its result.",
      },
    ],
  },
  {
    id: "match", n: "Task 1", title: "Career match: should you apply?",
    lead: "The first tab answers the question before you spend time on documents.",
    steps: [
      {
        title: "Read the verdict",
        body: <>The stamp says <strong>apply</strong> or <strong>do not apply</strong>. Beside it, the count of requirements matched, partly matched, and missing. There is no percent score, because a percent would be invented. The same card shows the name your documents will be signed with, read from the first line of your resume. Press <strong>Change</strong> if it is wrong.</>,
        shot: "04-verdict-apply.webp", alt: "The results header with a green APPLY stamp and matched, partial and gap counts",
        caption: "An apply verdict with its counts.",
      },
      {
        title: "Check each requirement",
        body: <>The table lists every requirement in the posting&apos;s own words. <strong>Matched</strong> has direct evidence. <strong>Partial</strong> has related evidence. <strong>Gap</strong> has none. Must-haves are marked. The evidence column names the fact that earned the status.</>,
        shot: "05-match-table.webp", alt: "A table of job requirements, each with a status chip and the evidence behind it",
        caption: "Requirement by requirement, with the evidence named.",
      },
      {
        title: "Take a do-not-apply seriously",
        body: <>When a must-have requirement has no evidence, the verdict is do not apply and the case against is written out. You can still compile documents, but they will only say what your facts support. The gap stays a gap.</>,
        shot: "06-verdict-do-not-apply.webp", alt: "A red DO NOT APPLY stamp with the case against applying stated",
        caption: "The honest answer, from the sample posting with a planted must-have gap.",
      },
    ],
  },
  {
    id: "resume", n: "Task 2", title: "Resume: generate it, then modify it",
    lead: "The job chooses which of your facts make the page. It never rewords them to match the posting.",
    steps: [
      {
        title: "Pick a length and compile",
        body: <>Open the <strong>Resume</strong> tab. Choose <strong>Half page</strong> or <strong>One page</strong>, then press <strong>Compile the resume</strong>. A solver picks the facts that fit this job under that budget. Compiling takes about 30 seconds in our measured runs.</>,
        shot: "07-resume-start.webp", alt: "The resume tab with a length choice and a compile button",
        caption: "Length is a budget. The solver decides what fits.",
      },
      {
        title: "Read the sheet",
        body: <>Each line shows its entailment score in the margin: how strongly the cited facts support the sentence. The right rail lists what was left out and the typed reason for each omission.</>,
        shot: "08-resume-sheet.webp", alt: "A compiled resume on a paper sheet with line numbers and entailment scores",
        caption: "The compiled resume. Every line carries its score.",
      },
      {
        title: "Click a line to see its evidence",
        body: <>Select any line. The rail shows the facts it cites, each quoted from your own resume, and opens an editor for the wording.</>,
        shot: "09-line-evidence.webp", alt: "A selected resume line with the facts it cites and an edit box",
        caption: "One line, the facts that license it, and the editor.",
      },
      {
        title: "Try to overstate it",
        body: <>Change a number, or press <strong>Overstate it for me</strong>. The gate rejects the edit and shows why: the number is in no cited fact, or the entailment score fell under the threshold. Nothing is saved.</>,
        shot: "10-edit-rejected.webp", alt: "A compile error showing an edited sentence rejected against its evidence",
        caption: "A rejected edit. The error names the evidence it was scored against.",
      },
      {
        title: "Save an honest edit",
        body: <>Reword the line without adding a claim, then press <strong>Save edit</strong>. Both gates run again. On a pass the line is replaced, marked edited, and the PDF and docx carry it. One line holds up to 600 characters.</>,
        shot: "11-edit-saved.webp", alt: "A saved edit confirmation with the new entailment score",
        caption: "A saved edit. Downloads now carry this line.",
      },
      {
        title: "Download",
        body: <>Press <strong>PDF</strong> or <strong>Word (docx)</strong>. The file includes a provenance appendix mapping each line to its facts.</>,
        shot: "12-resume-download.webp", alt: "The download card with PDF and Word buttons",
        caption: "PDF and docx, each with its provenance appendix.",
      },
    ],
  },
  {
    id: "letter", n: "Task 3", title: "Cover letter",
    lead: "The same two gates as the resume. A letter is where overstating is most tempting, so it gets no exemption.",
    steps: [
      {
        title: "Compile the letter",
        body: <>Open the <strong>Cover letter</strong> tab and press <strong>Compile the cover letter</strong>.</>,
        shot: "13-letter-start.webp", alt: "The cover letter tab with a compile button",
        caption: "One button. No tone sliders, no invented enthusiasm.",
      },
      {
        title: "Know which words are yours",
        body: <>Lines marked <strong>template</strong> are fixed text: the greeting, the role line, the closing. They claim nothing about you. The sentences between them were written from your facts and each passed the gate. Click one to see its evidence or edit it, exactly as on the resume.</>,
        shot: "14-letter-sheet.webp", alt: "A compiled cover letter with template lines marked and evidence sentences scored",
        caption: "Template frame, gated evidence sentences.",
      },
      {
        title: "Download",
        body: <>PDF or docx, from the same rail. Saved edits are included.</>,
        shot: "15-letter-download.webp", alt: "The cover letter download card",
        caption: "Ready to attach.",
      },
    ],
  },
];

export default function Guide() {
  return (
    <>
      <p className="eyebrow">Guide</p>
      <h1>How to use CareerCompiler.</h1>
      <p className="lede">
        You enter a resume and a job description. Then you choose what you need: a career
        match verdict, a tailored resume, or a cover letter. This page walks through each.
      </p>
      <div className="note" style={{ marginTop: "1.4rem", maxWidth: "46rem" }}>
        The screenshots show the real interface running on <strong>synthetic data</strong>.
        The candidate and postings are invented, and a scripted stand-in replaced the
        language model during capture. The matcher, the solver, both gates, and the
        entailment model in these pictures are the real ones.
      </div>

      <nav className="toc" aria-label="Guide sections">
        {TASKS.map((t) => (
          <a href={`#${t.id}`} key={t.id}>
            <div className="card flat">
              <p className="eyebrow" style={{ marginBottom: "0.6rem" }}>{t.n}</p>
              <h3>{t.title}</h3>
            </div>
          </a>
        ))}
      </nav>

      {TASKS.map((t) => (
        <section className="task" id={t.id} key={t.id}>
          <header>
            <span className="n">{t.n.toUpperCase()}</span>
            <div>
              <h2>{t.title}</h2>
              <p className="dim" style={{ maxWidth: "40rem" }}>{t.lead}</p>
            </div>
          </header>
          {t.steps.map((s, i) => (
            <div className="step" key={s.shot}>
              <div className="txt">
                <h3><span>{i + 1}</span>{s.title}</h3>
                <p className="dim">{s.body}</p>
              </div>
              <figure className="shot">
                <img src={`/assets/guide/${s.shot}`} alt={s.alt} loading="lazy" />
                <figcaption>{s.caption} · synthetic data</figcaption>
              </figure>
            </div>
          ))}
        </section>
      ))}

      <section className="task">
        <header>
          <span className="n">ALSO</span>
          <div>
            <h2>Good to know</h2>
          </div>
        </header>
        <div className="grid2">
          <div className="card flat">
            <h3>The name on your documents</h3>
            <p className="dim small">You are never asked for your name. It is read from the first line of your resume when that line is plainly a name. If it is not, you are asked to type it once. Either way you can change it from the verdict card, and the next download is signed with the new name.</p>
          </div>
          <div className="card flat">
            <h3>Sessions end on their own</h3>
            <p className="dim small">A session lasts 30 minutes and has a fixed request budget. When it ends you see one screen with one button. Start a new session and run the analysis again.</p>
          </div>
          <div className="card flat">
            <h3>Interview prep</h3>
            <p className="dim small">The fourth tab builds a prep pack from the compiled resume: the facts behind each line, the numbers you may quote, and the questions a skeptical interviewer would ask.</p>
          </div>
          <div className="card flat">
            <h3>Nothing to hand?</h3>
            <p className="dim small">The <Link href="/demo/">sample</Link> runs the same screens on an invented candidate and two invented postings, one of each verdict.</p>
          </div>
        </div>
        <p className="no-print" style={{ marginTop: "2rem" }}>
          <Link href="/workspace/" className="btn">Open the workspace</Link>
        </p>
      </section>
    </>
  );
}
