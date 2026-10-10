import { PageHead } from "@/components/lms/ui";
import { SupportDesk } from "@/features/shared/support-desk";

export function AcademicSupport() {
  return (
    <>
      <PageHead
        title="Academic Support"
        description="Reply to, resolve, escalate or reassign your branch's support requests."
      />
      <SupportDesk mode="staff" caption="Support requests" empty="No support requests for your branch." />
    </>
  );
}
