import { useAcademicSummary } from "@/api/dashboards";
import { Note, PageHead, QueryView, StatusNote } from "@/components/lms/ui";
import { QuickLinks, Tile, TileRow } from "@/features/shared/dashboard-parts";

const LINKS = [
  ["/academic/curriculum", "Curriculum versions"],
  ["/academic/batches", "Batch management"],
  ["/academic/schedule", "Schedule"],
  ["/academic/recording-exceptions", "Recording exceptions"],
  ["/academic/completion", "Completion review"],
  ["/academic/certificates", "Certificate eligibility"],
] as const;

export function AcademicDashboard() {
  const query = useAcademicSummary();
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <QueryView query={query}>
        {(d) => (
          <>
            <PageHead title="Academic dashboard" description={`${d.scope.label} · LMS academic domain`} />
            <TileRow label="Priority tiles">
              <Tile
                rank={1}
                label="Enrolments awaiting batch allocation"
                value={d.allocation_queue.count}
                hint={`Includes Curriculum Mapping Pending (${d.allocation_queue.curriculum_mapping_pending})`}
                to="/academic/batches"
              />
              <Tile
                rank={2}
                label="Academic results awaiting publication review"
                value={d.results_awaiting_publication.count}
                hint="Provisional or moderated, not published"
                to="/academic/assessments"
              />
              <Tile
                rank={3}
                label="Unfulfilled recording promises"
                value={d.recording_exceptions.count}
                hint="From the Recording Exception Queue"
                to="/academic/recording-exceptions"
              />
            </TileRow>
            <TileRow label="Additional academic widgets">
              <Tile label="Batches delivery-ready" value={`${d.batches_ready.ready} / ${d.batches_ready.total}`} hint="Running or forming batches" />
              <Tile
                label="Academic reviews awaiting"
                value={d.reviews_awaiting.count}
                hint={`Content ${d.reviews_awaiting.content} · Completion ${d.reviews_awaiting.completion} · Certificates ${d.reviews_awaiting.certificates}`}
              />
              <Tile
                label="Open exceptions"
                value={d.open_exceptions.count}
                hint={`${d.open_exceptions.awaiting_owner} awaiting a named owner`}
                to="/academic/exceptions"
              />
            </TileRow>
            {d.batch_risks.map((risk) => (
              <StatusNote key={risk.batch_id} state={risk.readiness === "Blocked" ? "Failed" : "Pending Verification"}>
                {risk.batch_code}: {risk.reason ?? risk.readiness}
                {risk.recovery_owner && <> · Recovery Owner: {risk.recovery_owner}</>}. Paid receipts and Admissions are preserved.
              </StatusNote>
            ))}
            <QuickLinks title="Quick links" links={LINKS} />
            <Note>Four distinct records: Accepted Delivery Plan · Batch · Course Enrolment / component allocation · Actual Class Session.</Note>
          </>
        )}
      </QueryView>
    </div>
  );
}
