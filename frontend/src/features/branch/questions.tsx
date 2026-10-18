/** Question approvals: questions trainers wrote for tests, waiting for the Branch Manager to approve. */
import { PageHead } from "@/components/lms/ui";
import { QuestionBank } from "@/features/shared/question-bank";

export function BranchQuestions() {
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead title="Question approvals" description="Questions trainers wrote for tests. Approve them before they can be used in a test." />
      <QuestionBank canApprove initialStatus="Draft" />
    </div>
  );
}
