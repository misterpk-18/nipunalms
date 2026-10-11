/** Issues for the Super Admin: everything wrong or stuck in every branch, with Assign to hand one to the person who should fix it. */
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead } from "@/components/lms/ui";
import { IssuesList } from "@/features/branch/issues";
import { useCanAdminister } from "./format";

export function AdminIssues() {
  const canAssign = useCanAdminister();
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead
        title="Issues"
        description="Everything that is wrong or stuck in every branch. Assign each issue to the person who should fix it, or press Go fix it to open it yourself."
      />
      <IssuesList canAssign={canAssign} branchScoped={false} />
      <HowThisWorks>
        <p>An issue stays here until what caused it is fixed; it then leaves the list by itself.</p>
        <p>Assign names an owner and tells them. Add note records what was done or will be done, and makes you the owner.</p>
        <p>Issues that already have an owner set on their own screen (for example a student request) are reassigned there.</p>
      </HowThisWorks>
    </div>
  );
}
