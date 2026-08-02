import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerCompiler — a resume compiler with compile errors",
  description:
    "Every sentence cites the career facts that license it. A sentence that claims more " +
    "than its cited evidence supports fails the compile, scored by a pinned NLI model.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <main>{children}</main>
      </body>
    </html>
  );
}
