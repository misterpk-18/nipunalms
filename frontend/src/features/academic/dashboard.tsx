import { useAcademicSummary } from "@/api/dashboards";
import { useActing } from "@/auth/acting";
import { Note, PageHead, QueryView, StatusNote } from "@/components/lms/ui";
import { QuickLinks, Tile, TileRow } from "@/features/shared/dashboard-parts";

const LINKS = [
  ["/branch/curriculum", "Curriculum versions"],
  ["/branch/batches", "Batches"],
  ["/branch/schedule", "Schedule"],
  ["/branch/recording-exceptions", "Recording exceptions"],
  ["/branch/completion", "Completion review"],
  ["/branch/certificates", "Certificate eligibility"],
] as const;

/** The branch's academic work. `embedded` puts it under the Branch Manager dashboard instead of on a page of its own. */
export function AcademicDashboard({ embedded = false }: { embedded?: boolean }) {
  const { branchId } = useActing("branch");
  const query = useAcademicSummary(branchId);
  return (
    <div className={embedded ? "space-y-5" : "mx-auto max-w-6xl space-y-5"}>
      <QueryView query={query}>
        {(d) => (
          <>
            {embedded ? (
              <h2 className="text-lg font-semibold">Academic work</h2>
            ) : (
              <PageHead title="Academic dashboard" description={`${d.scope.label} · batches, classes and approvals that need you`} />
            )}
            <TileRow label="Priority tiles">
              <Tile rank={1} label="Enrolments awaiting batch allocation" value={d.allocation_queue.count} to="/branch/waiting" />
              <Tile
                rank={2}
                label="Academic results awaiting publication review"
                value={d.results_awaiting_publication.count}
                hint="Provisional or moderated, not published"
                to="/branch/assessments"
              />
              <Tile
                rank={3}
                label="Unfulfilled recording promises"
                value={d.recording_exceptions.count}
                hint="From the Recording Exception Queue"
                to="/branch/recording-exceptions"
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
                to="/branch/exceptions"
              />
            </TileRow>
            {d.batch_risks.map((risk) => (
              <StatusNote key={risk.batch_id} tone={risk.readiness === "Blocked" ? "danger" : "warning"}>
                {risk.batch_code}: {risk.reason ?? risk.readiness}
                {risk.recovery_owner && <> · Owner: {risk.recovery_owner}</>}. Paid receipts and Admissions are preserved.
              </StatusNote>
            ))}
            <QuickLinks title="Quick links" links={LINKS} />
          </>
        )}
      </QueryView>
    </div>
  );
}
