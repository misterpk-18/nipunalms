import { useBranchDashboard } from "@/api/dashboards";
import { useActing } from "@/auth/acting";
import { GettingStartedCard } from "@/components/lms/getting-started";
import { Note, PageHead, QueryView, StatusNote } from "@/components/lms/ui";
import { CrmTile, QuickLinks, Tile, TileRow } from "@/features/shared/dashboard-parts";
import { AcademicDashboard } from "@/features/academic/dashboard";
import { BranchPicker, MyWork } from "./my-work";
import { PaymentInstructions } from "./payment-instructions";

const LINKS = [
  ["/branch/batches", "Batches"],
  ["/branch/requests", "Escalations & extensions"],
  ["/branch/reports", "Certificates & reports"],
] as const;

/** The Branch Manager's home: My work first, then how the branch is doing. */
export function BranchDashboard() {
  const { branchId } = useActing("branch");
  const query = useBranchDashboard(branchId);
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHead
        title="My work"
        description={query.data ? `${query.data.scope.label} · what needs you today, most pressing first` : "What needs you today, most pressing first"}
        actions={<BranchPicker />}
      />
      <MyWork />
      <GettingStartedCard workspace="branch" />
      <QueryView query={query}>
        {(d) => (
          <>
            <h2 className="text-lg font-semibold">How the branch is doing</h2>
            <TileRow label="Priority tiles">
              <CrmTile rank={1} label="Branch verified collections against target" figure={d.crm.verified_collections} />
              <CrmTile rank={2} label="Branch new paid Admissions" figure={d.crm.new_paid_admissions} />
              <CrmTile rank={3} label="Overdue branch follow-ups" figure={d.crm.overdue_followups} />
            </TileRow>
            <TileRow label="Additional academic widgets">
              <Tile
                label="Running / starting batches"
                value={d.batches_running.count}
                hint={`${d.batches_running.total_open} batches not yet finished`}
                to="/branch/batches"
              />
              <Tile
                label="Schedule & recording exceptions"
                value={d.schedule_and_recording_exceptions.count}
                hint={`Recording ${d.schedule_and_recording_exceptions.recording_exceptions} · Reschedule requests ${d.schedule_and_recording_exceptions.reschedule_requests}`}
                to="/branch/schedule"
              />
              <Tile
                label="Open escalations & extension requests"
                value={d.requests_open.count}
                hint={`Escalations ${d.requests_open.escalations} · Extensions ${d.requests_open.extension_requests}`}
                to="/branch/requests"
              />
            </TileRow>
            {d.batch_risks.map((risk) => (
              <StatusNote key={risk.batch_id} tone="warning">
                {risk.batch_code}: {risk.reason ?? risk.readiness}
                {risk.recovery_owner && <> · Owner: {risk.recovery_owner}</>}
              </StatusNote>
            ))}
            <QuickLinks title="Go to" links={LINKS} />
            <Note>Finance and Admissions remain in the CRM. This view shows academic data for the locked branch only.</Note>
          </>
        )}
      </QueryView>
      <AcademicDashboard embedded />
      <PaymentInstructions />
    </div>
  );
}
