import { Link } from "@tanstack/react-router";
import { useAdminSummary } from "@/api/dashboards";
import { DataTable, Note, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { istDateTime } from "@/features/admin/format";
import { CrmTile, QuickLinks, Tile, TileRow } from "@/features/shared/dashboard-parts";

const LINKS = [
  ["/admin/integrations", "Integration readiness"],
  ["/admin/exceptions", "Exception queues"],
  ["/admin/security", "Security readiness"],
  ["/academic", "Academic (all branches)"],
  ["/branch", "Branch views"],
] as const;

export function AdminDashboard() {
  const query = useAdminSummary();
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <QueryView query={query}>
        {(d) => (
          <>
            <PageHead title="Super Admin — all authorised branches" description="Readiness register and exception queues" />
            <TileRow label="Priority tiles">
              <Tile
                rank={1}
                label="Critical integration failures"
                value={d.integration_failures.count}
                hint={`${d.integration_failures.source}${d.integration_failures.codes.length ? ` · ${d.integration_failures.codes.join(", ")}` : ""}`}
                to="/admin/integrations"
              />
              <Tile
                rank={2}
                label="Work awaiting named ownership/cover"
                value={d.awaiting_owner.count}
                hint="Open exceptions with no named owner"
                to="/admin/exceptions"
              />
              <CrmTile rank={3} label="Overdue payment verifications" figure={d.crm.overdue_payment_verifications} />
            </TileRow>
            <TileRow label="Additional widgets">
              <Tile
                label="Integrations operationally verified"
                value={`${d.integrations_verified.verified} / ${d.integrations_verified.total}`}
                hint="Verified needs evidence"
                to="/admin/integrations"
              />
              <Tile label="Failed provisioning" value={d.provisioning.count} hint="Access held back until the enrolment is provisioned" to="/admin/students" />
              <Tile label="Open exceptions (all queues)" value={d.open_exceptions.count} to="/admin/exceptions" />
            </TileRow>
            <StatusNote state="Integration Unavailable">
              CRM/LMS sync, Meet, Drive, AI and messaging are not verified; nothing here is treated as live.
            </StatusNote>

            <Section title="CRM / LMS sync status">
              <DataTable
                caption="Sync"
                rows={d.sync.flows}
                getKey={(f) => f.flow}
                cols={[
                  { h: "Flow", c: (f) => f.flow },
                  { h: "Last successful", c: (f) => (f.last_successful_at ? istDateTime(f.last_successful_at) : "Never") },
                  { h: "State", c: (f) => <StatusBadge>{f.state}</StatusBadge> },
                  { h: "Detail", c: (f) => f.detail ?? "—" },
                ]}
              />
              {d.sync.failed_events > 0 && (
                <p className="mt-2 text-sm">
                  {d.sync.failed_events} failed CRM event(s) —{" "}
                  <Link to="/admin/crm-sync" className="underline">
                    open CRM sync to retry
                  </Link>
                  .
                </p>
              )}
            </Section>

            <Section title="Provisioning exceptions">
              <DataTable
                caption="Provisioning"
                rows={d.provisioning.items}
                empty="No provisioning exception is open."
                getKey={(p) => `${p.source}-${p.source_id}`}
                cols={[
                  { h: "ID", c: (p) => p.reference },
                  { h: "Item", c: (p) => p.detail ?? p.title },
                  { h: "Issue", c: (p) => p.title },
                  { h: "State", c: (p) => <StatusBadge>{p.state}</StatusBadge> },
                ]}
              />
            </Section>

            <Section title="AI status">
              <p className="text-sm">
                Ask Nipuna: <StatusBadge>{d.ai.state}</StatusBadge> · Student {d.ai.student_daily_limit} / Staff {d.ai.staff_daily_limit} responses per IST day
                ·{" "}
                {d.ai.monthly_ceiling.state === "Configured" ? (
                  <>monthly rupee ceiling ₹{d.ai.monthly_ceiling.amount_inr.toLocaleString("en-IN")}</>
                ) : (
                  <>
                    monthly rupee ceiling not yet approved (<StatusBadge>Configuration Pending</StatusBadge>)
                  </>
                )}
                .
              </p>
            </Section>

            <QuickLinks title="Go to" links={LINKS} />
            <Note>Readiness views only — no live administration. Server/API permissions remain production Pending Verification.</Note>
          </>
        )}
      </QueryView>
    </div>
  );
}
