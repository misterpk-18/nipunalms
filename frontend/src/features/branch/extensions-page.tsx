/** Access extensions: students asking for more time on recordings and materials. Within the Branch Manager's limit they decide; beyond it they recommend and the Founder decides. */
import { useAuth } from "@/auth/auth";
import { PageHead } from "@/components/lms/ui";
import { ExtensionsTab } from "./extensions-requests";

export function BranchExtensions() {
  const { branchId } = useAuth();
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead
        title="Access extensions"
        description="Students asking for more time on recordings and materials. Decide what is within your limit; recommend the rest to the Founder."
      />
      <ExtensionsTab branchId={branchId} />
    </div>
  );
}
