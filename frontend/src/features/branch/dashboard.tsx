import { useBranchDashboard } from "@/api/dashboards";
import { Note, PageHead, QueryView, StatusNote } from "@/components/lms/ui";
import { CrmTile, QuickLinks, Tile, TileRow } from "@/features/shared/dashboard-parts";

const LINKS = [
  ["/branch/operations", "Batches, schedule & people"],
  ["/branch/requests", "Escalations & extensions"],
  ["/branch/reports", "Certificates & reports"],
] as const;

export function BranchDashboard() {
  const query = useBranchDashboard();
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <QueryView query={query}>
        {(d) => (
          <>
            <PageHead title="Branch academic dashboard" description={`${d.scope.label} · LMS academic domain (Module 25 ordering)`} />
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
                to="/branch/operations"
              />
              <Tile
                label="Schedule & recording exceptions"
                value={d.schedule_and_recording_exceptions.count}
                hint={`Recording ${d.schedule_and_recording_exceptions.recording_exceptions} · Reschedule requests ${d.schedule_and_recording_exceptions.reschedule_requests}`}
                to="/branch/operations"
              />
              <Tile
                label="Open escalations & extension requests"
                value={d.requests_open.count}
                hint={`Escalations ${d.requests_open.escalations} · Extensions ${d.requests_open.extension_requests}`}
                to="/branch/requests"
              />
            </TileRow>
            {d.batch_risks.map((risk) => (
              <StatusNote key={risk.batch_id} state="Pending Verification">
                {risk.batch_code}: {risk.reason ?? risk.readiness}
                {risk.recovery_owner && <> · Recovery Owner: {risk.recovery_owner}</>}
              </StatusNote>
            ))}
            <QuickLinks title="Go to" links={LINKS} />
            <Note>Finance and Admissions remain in the CRM. This view shows academic data for the locked branch only.</Note>
          </>
        )}
      </QueryView>
    </div>
  );
}
