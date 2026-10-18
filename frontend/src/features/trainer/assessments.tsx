import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { assessmentsApi } from "@/api/assessments";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, PillTabs } from "@/components/lms/ui";
import { MockInterviews } from "./interviews";
import { QuestionBank } from "@/features/shared/question-bank";
import { TestBuilder } from "./test-builder";

/** The tabs follow the order the work goes in: write questions, build a test from them, then run interviews. */
const TABS = ["Question bank", "Tests", "Interviews"] as const;
type Tab = (typeof TABS)[number];
const TAB_PARAM: Record<Tab, "questions" | "tests" | "interviews"> = { "Question bank": "questions", Tests: "tests", Interviews: "interviews" };
const FROM_PARAM = { questions: "Question bank", tests: "Tests", interviews: "Interviews" } as const;

const HINTS: Record<Tab, string> = {
  "Question bank": "Write questions once. The Branch Manager approves them, then you can put them in a test.",
  Tests: "Build a test from approved questions, then release it to one of your batches.",
  Interviews: "Create a practice interview, offer time slots and record feedback after each one.",
};

export function TrainerAssessments() {
  const { tab: wanted } = useSearch({ from: "/trainer/assessments" });
  const navigate = useNavigate();
  const tab: Tab = wanted && wanted !== "grading" ? FROM_PARAM[wanted] : "Tests";
  // The same lists the tabs below show, so the counts cost no extra request
  const questions = useQuery({ queryKey: ["questions", "list", "All"], queryFn: () => assessmentsApi.questions({}) });
  const tests = useQuery({ queryKey: ["tests", "list", "staff"], queryFn: () => assessmentsApi.tests() });
  const counts: Partial<Record<Tab, number>> = {
    "Question bank": questions.data?.meta.total ?? 0,
    Tests: tests.data?.data.filter((t) => t.kind !== "Mock interview").length ?? 0,
    Interviews: tests.data?.data.filter((t) => t.kind === "Mock interview").length ?? 0,
  };
  return (
    <div className="mx-auto max-w-6xl">
      <PageHead title="Assessments" description="Questions, tests and practice interviews for the batches you teach." />
      <PillTabs
        tabs={TABS}
        value={tab}
        onChange={(next) => void navigate({ to: "/trainer/assessments", search: { tab: TAB_PARAM[next] }, replace: true })}
        label="Assessment areas"
        counts={counts}
      />
      <p className="-mt-2 mb-4 text-sm text-muted-foreground">{HINTS[tab]}</p>
      {tab === "Question bank" && <QuestionBank />}
      {tab === "Tests" && <TestBuilder />}
      {tab === "Interviews" && <MockInterviews />}
      <div className="mt-4">
        <HowThisWorks>
          <p>
            A formal test (module, coding or final) needs pass marks, a closing time and the Branch Manager&apos;s approval before it can be released. Practice
            quizzes and mock tests can be released as soon as they have questions. Marking the written answers happens in To grade.
          </p>
        </HowThisWorks>
      </div>
    </div>
  );
}
