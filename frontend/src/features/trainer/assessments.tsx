import { useState } from "react";
import { PageHead, PillTabs } from "@/components/lms/ui";
import { GradingQueue } from "./grading";
import { MockInterviews } from "./interviews";
import { QuestionBank } from "./question-bank";
import { TestBuilder } from "./test-builder";

const TABS = ["Tests", "Question bank", "Grading queue", "Mock interviews"] as const;

export function TrainerAssessments() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Tests");
  return (
    <div className="mx-auto max-w-6xl">
      <PageHead title="Assessments" description="Tests, coding exercises, mock tests and interviews for the batches you teach." />
      <PillTabs tabs={TABS} value={tab} onChange={setTab} label="Assessment areas" />
      {tab === "Tests" && <TestBuilder />}
      {tab === "Question bank" && <QuestionBank />}
      {tab === "Grading queue" && <GradingQueue />}
      {tab === "Mock interviews" && <MockInterviews />}
    </div>
  );
}
