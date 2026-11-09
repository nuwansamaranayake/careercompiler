import type { Metadata } from "next";
import { Workspace } from "@/components/Workspace";

export const metadata: Metadata = {
  title: "Workspace — CareerCompiler",
  description:
    "Enter a resume and a job description. Get a fit verdict, a tailored resume, and a " +
    "cover letter, each sentence cited to a fact from your own resume.",
};

export default function WorkspacePage() {
  return <Workspace mode="own" />;
}
