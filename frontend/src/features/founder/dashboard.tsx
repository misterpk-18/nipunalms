import { Link } from "@tanstack/react-router";
import { useFounderSummary } from "@/api/dashboards";
import { Note, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { CrmTile, Tile, TileRow } from "@/features/shared/dashboard-parts";
import { fmtDate } from "@/features/shared/format";

export function FounderDashboard() {
  const query = useFounderSummary();
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <QueryView query={query}>
        {(d) => {
          const ceiling = d.decisions.ai_ceiling;
          const access = d.decisions.access_exceptions;
          return (
            <>
              <PageHead title="Founder / CEO overview" description="LMS academic domain (Module 25 ordering)" />
              <TileRow label="Priority tiles">
                <CrmTile rank={1} label="Verified collections against target" figure={d.crm.verified_collections} />
                <CrmTile rank={2} label="New paid Admissions against target" figure={d.crm.new_paid_admissions} />
                <CrmTile rank={3} label="Overdue amount" figure={d.crm.overdue_amount} />
              </TileRow>
              <TileRow label="Additional widgets">
                <Tile
                  label="Active enrolments in delivery"
                  value={d.active_enrolments.count}
                  hint={d.active_enrolments.by_branch.map((b) => `${b.branch.branch_name} ${b.count}`).join(" · ")}
                />
                <Tile
                  label="Batches at delivery risk"
                  value={d.batches_at_risk.count}
                  hint={d.batches_at_risk.items.map((b) => b.reason ?? b.readiness).join("; ") || "None"}
                />
                <Tile
                  label="Certificates awaiting approval"
                  value={d.certificates_awaiting_approval.count}
                  hint={d.certificates_awaiting_approval.by_branch.map((b) => `${b.branch.branch_name} ${b.count}`).join(" · ")}
                />
              </TileRow>

              <Section title="Decisions needing you">
                <ul className="space-y-2 text-sm">
                  <li className="flex flex-wrap justify-between gap-2">
                    <span>Approve monthly AI rupee ceiling (after developer estimate)</span>
                    <StatusBadge>{ceiling.state === "Configured" ? `Configured — ₹${ceiling.amount_inr.toLocaleString("en-IN")}` : ceiling.state}</StatusBadge>
                  </li>
                  {access.items.map((item) => (
                    <li key={item.request_id} className="flex flex-wrap justify-between gap-2">
                      <span>
                        Recording access exception after 2nd anniversary — {item.student_name} ({item.request_code}, asked {fmtDate(item.requested_at)}){" "}
                        <Link to="/branch/requests" className="underline">
                          Decide
                        </Link>
                      </span>
                      <StatusBadge>{access.state}</StatusBadge>
                    </li>
                  ))}
                  {access.count === 0 && (
                    <li className="flex flex-wrap justify-between gap-2">
                      <span>Recording access exceptions after 2nd anniversary</span>
                      <span className="text-muted-foreground">None waiting</span>
                    </li>
                  )}
                </ul>
              </Section>

              <StatusNote state="Integration Unavailable">Revenue and collections are CRM figures — not shown here.</StatusNote>
              <div className="flex flex-wrap gap-2 text-sm">
                <Link to="/admin" className="tap inline-flex items-center rounded-lg border px-3 hover:bg-accent">
                  Super Admin view
                </Link>
                <Link to="/branch" className="tap inline-flex items-center rounded-lg border px-3 hover:bg-accent">
                  Branch views
                </Link>
              </div>
              <Note>Only approved Module 25 ordering is used; unavailable sources display as Not Configured.</Note>
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
