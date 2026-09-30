import { Section } from "@/components/lms/ui";
import { SupportDesk } from "@/features/shared/support-desk";

/** Support requests escalated to the Branch Manager, manually or after their SLA passed (the "Escalations" tab of the branch requests page). */
export function BranchEscalations() {
  return (
    <Section title="Support escalations">
      <SupportDesk mode="staff" caption="Escalated support requests" empty="No support requests are escalated to you." base={{ escalated: true }} />
    </Section>
  );
}
