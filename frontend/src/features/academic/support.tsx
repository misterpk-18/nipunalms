import { PageHead } from "@/components/lms/ui";
import { SupportDesk } from "@/features/shared/support-desk";

export function AcademicSupport() {
  return (
    <>
      <PageHead
        title="Academic Support"
        description="Support requests of your branch, with their named owners. Reply, resolve, escalate or reassign from a request."
      />
      <SupportDesk mode="staff" caption="Support requests" empty="No support requests for your branch." />
    </>
  );
}
