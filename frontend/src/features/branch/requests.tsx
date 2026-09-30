import { useState } from "react";
import { PageHead, PillTabs } from "@/components/lms/ui";
import { AccessExtensions } from "@/features/branch/access-extensions";
import { BranchEscalations } from "@/features/branch/escalations";

const TABS = ["Escalations", "Access extensions"] as const;

/** The Branch Manager's requests: support escalations and recording/material access-extension requests. */
export function BranchRequests() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Escalations");
  return (
    <div className="mx-auto max-w-6xl">
      <PageHead
        title="Escalations & access-extension requests"
        description="Support requests escalated to you and requests to extend recording or material access."
      />
      <PillTabs label="Request types" tabs={TABS} value={tab} onChange={setTab} />
      {tab === "Escalations" ? <BranchEscalations /> : <AccessExtensions />}
    </div>
  );
}
