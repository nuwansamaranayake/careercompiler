import type { Metadata } from "next";
import Link from "next/link";
import "@fontsource-variable/fraunces/opsz.css";
import "@fontsource-variable/fraunces/opsz-italic.css";
import "@fontsource-variable/hanken-grotesk";
import "@fontsource-variable/jetbrains-mono";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerCompiler — a resume compiler with compile errors",
  description:
    "Bring a resume and a job description. Get a fit verdict, a tailored resume, and a " +
    "cover letter. Every sentence cites the career facts that license it, and a sentence " +
    "that claims more than its cited evidence supports fails the compile, scored by a " +
    "pinned NLI model.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="wrap">
          <header className="masthead">
            <Link href="/" className="wordmark">CareerCompiler</Link>
            <nav className="nav" aria-label="Main">
              <Link href="/workspace/">Workspace</Link>
              <Link href="/demo/">Sample</Link>
              <Link href="/guide/">Guide</Link>
            </nav>
          </header>
          <main>{children}</main>
          <footer className="colophon">
            <span>The model senses. Deterministic code decides. You approve.</span>
            <span>
              <a href="/docs">API reference</a> ·{" "}
              <a href="https://github.com/nuwansamaranayake/careercompiler">Source</a> ·{" "}
              an AiGNITE portfolio build
            </span>
          </footer>
        </div>
      </body>
    </html>
  );
}
