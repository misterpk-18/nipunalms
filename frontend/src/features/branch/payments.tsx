/** Payment instructions: how students pay at this branch, shown on their Next payment card. */
import { useAuth } from "@/auth/auth";
import { PageHead, Section } from "@/components/lms/ui";
import { PaymentInstructions } from "@/features/shared/payment-instructions";

export function BranchPayments() {
  const { allowedBranches, branchId } = useAuth();
  const branches = allowedBranches.filter((b) => branchId === null || b.branch_id === branchId);
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageHead title="Payment instructions" description="Where and how students pay fees at your branch." />
      <Section title="How students pay fees">
        <PaymentInstructions branches={branches} initialBranchId={branchId} readOnly />
      </Section>
    </div>
  );
}
