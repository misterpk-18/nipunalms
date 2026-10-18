/** Attendance across branches, read-only: the Students tab of Attendance & progress with a branch filter. Decisions on recoveries and corrections stay with Branch Managers. */
import { PageHead } from "@/components/lms/ui";
import { StudentsTab } from "@/features/shared/attendance-students";
import { BranchFilter } from "@/features/shared/branch-filter";
import { type CentralArea } from "@/features/shared/central-area";
import { useUrlParams } from "@/features/shared/url-state";

export function AttendanceOverview({ area }: { area: CentralArea }) {
  const [params, setParams] = useUrlParams();
  const branch = params["branch"] ? Number(params["branch"]) : null;
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead
        title="Attendance"
        description="Who is falling behind, in one branch or in all of them. This is a read-only view: recovery and correction decisions are made by each branch's Branch Manager."
      />
      <div className="w-full sm:w-64">
        <BranchFilter value={branch} onChange={(id) => setParams({ branch: id === null ? undefined : String(id), page: undefined })} />
      </div>
      <StudentsTab base={area.base} branchId={branch} params={params} setParams={setParams} />
    </div>
  );
}
