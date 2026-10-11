import { useFounderSummary } from "@/api/dashboards";
import { Note, PageHead, QueryView, Section } from "@/components/lms/ui";
import { CrmTile, Tile, TileRow } from "@/features/shared/dashboard-parts";
import { InboxList } from "./inbox-list";

/** The Founder's home: everything waiting for them first, then how the company is doing. */
export function FounderDashboard() {
  const query = useFounderSummary();
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHead title="Founder / CEO home" description="Decide what is waiting for you, then see how the company is doing." />
      <InboxList page="/founder" />
      <QueryView query={query} skeleton="cards">
        {(d) => (
          <Section title="How the company is doing">
            <div className="space-y-4">
              {d.crm_connected ? (
                <TileRow label="Money">
                  <CrmTile rank={1} label="Verified collections against target" figure={d.crm.verified_collections} />
                  <CrmTile rank={2} label="New paid Admissions against target" figure={d.crm.new_paid_admissions} />
                  <CrmTile rank={3} label="Overdue amount" figure={d.crm.overdue_amount} />
                </TileRow>
              ) : (
                <Note>Collections and overdue figures appear here once the CRM has sent them.</Note>
              )}
              <TileRow label="Delivery">
                <Tile
                  label="Active enrolments in delivery"
                  value={d.active_enrolments.count}
                  hint={d.active_enrolments.by_branch.map((b) => `${b.branch.branch_name} ${b.count}`).join(" · ")}
                />
                <Tile
                  label="Batches at delivery risk"
                  value={d.batches_at_risk.count}
                  hint={[...new Set(d.batches_at_risk.items.map((b) => b.reason ?? b.readiness))].join("; ") || "None"}
                />
                <Tile
                  label="Certificates waiting for a Branch Manager"
                  value={d.certificates_awaiting_approval.count}
                  hint={d.certificates_awaiting_approval.by_branch.map((b) => `${b.branch.branch_name} ${b.count}`).join(" · ")}
                />
              </TileRow>
            </div>
          </Section>
        )}
      </QueryView>
    </div>
  );
}
