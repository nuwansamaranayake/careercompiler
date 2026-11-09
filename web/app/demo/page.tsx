import type { Metadata } from "next";
import { Workspace } from "@/components/Workspace";

export const metadata: Metadata = {
  title: "Sample — CareerCompiler",
  description:
    "The workspace on synthetic data: one invented candidate, two invented postings, " +
    "one apply verdict and one do-not-apply.",
};

export default function SamplePage() {
  return <Workspace mode="sample" />;
}
