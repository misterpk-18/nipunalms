/** The words of the Recordings screen: where to find a Drive file id and the reasons a recording can have a problem. */
import type { ProblemReason, Recording } from "@/api/content";

export const DRIVE_HINT =
  "Where to find it: open the recording in Google Drive, choose Share > Copy link, and paste the long code between /d/ and /view (the file id). Until Drive is connected the LMS only stores this id.";

export const PROBLEM_CHOICES: { value: ProblemReason; label: string; needsNote: boolean; noteLabel: string }[] = [
  { value: "processing", label: "It is still being prepared", needsNote: false, noteLabel: "Anything students should know (optional)" },
  { value: "partial", label: "Only part of the class was captured", needsNote: true, noteLabel: "What was and was not captured" },
  { value: "unavailable", label: "No recording exists", needsNote: true, noteLabel: "Why there is no recording" },
  { value: "on_hold", label: "Hold it back for review", needsNote: true, noteLabel: "Why it is held back" },
];

/** The plain reason of a recording's problem, with the note when there is one. */
export function problemText(problem: NonNullable<Recording["problem"]>): string {
  const choice = PROBLEM_CHOICES.find((c) => c.value === problem.reason);
  const base = choice?.label ?? problem.label;
  return problem.note ? `${base}: ${problem.note}` : base;
}
