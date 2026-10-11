/** Attendance & progress: students (at risk first), recovery requests and attendance corrections, with counts on the tabs. */
import { useQuery } from "@tanstack/react-query";
import { attendanceApi } from "@/api/attendance";
import { useActing } from "@/auth/acting";
import { PageHead, PillTabs } from "@/components/lms/ui";
import { CorrectionsTab, RecoveriesTab } from "./attendance-queues";
import { StudentsTab } from "./attendance-students";
import { pickTab, useUrlParams } from "./attendance-url";
import { BranchPicker } from "./my-work";

const TABS = ["students", "recoveries", "corrections"] as const;
const LABELS = { students: "Students", recoveries: "Recovery requests", corrections: "Corrections" };

export function BranchAttendance() {
  const { branchId } = useActing("branch");
  const [params, setParams] = useUrlParams();
  const tab = pickTab(TABS, params["tab"]);
  const counts = useQuery({ queryKey: ["attendance", "tab-counts", branchId], queryFn: () => attendanceApi.tabCounts(branchId) });
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead
        title="Attendance & progress"
        description="Who is falling behind, which missed classes can be made up, and which attendance mistakes need a decision."
        actions={<BranchPicker />}
      />
      <PillTabs
        label="Attendance and progress"
        tabs={TABS}
        labels={LABELS}
        value={tab}
        onChange={(next) => setParams({ tab: next === "students" ? undefined : next, page: undefined })}
        counts={counts.data ? { students: counts.data.students_at_risk, recoveries: counts.data.recoveries, corrections: counts.data.corrections } : undefined}
      />
      {tab === "students" && <StudentsTab branchId={branchId} params={params} setParams={setParams} />}
      {tab === "recoveries" && <RecoveriesTab branchId={branchId} />}
      {tab === "corrections" && <CorrectionsTab branchId={branchId} />}
    </div>
  );
}
