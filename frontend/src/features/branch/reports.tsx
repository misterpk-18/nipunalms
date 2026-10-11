/** Reports: figures for a period, each a link to the records behind it; progress by batch; monthly trends; CSV downloads. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { Download } from "lucide-react";
import { toast } from "sonner";
import { branchReportsApi, type ReportPeriodKey, type ReportSection } from "@/api/branch-reports";
import { errorMessage } from "@/api/client";
import { useActing } from "@/auth/acting";
import { NativeSelect } from "@/components/lms/forms";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { DataTable, Grid, PageHead, QueryView, Section, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { fmtDate } from "@/features/shared/format";
import { StateBadge } from "@/features/shared/delivery-ui";
import { BranchPicker } from "./my-work";
import { FIGURE_GROUPS } from "./reports-groups";
import { FigureCard, TrendsChart } from "./reports-parts";

const PERIODS: { value: ReportPeriodKey; label: string }[] = [
  { value: "this_month", label: "This month" },
  { value: "last_month", label: "Last month" },
  { value: "last_90", label: "Last 90 days" },
  { value: "custom", label: "Custom dates" },
];
const EXPORTS: { section: ReportSection; label: string }[] = [
  { section: "figures", label: "Figures" },
  { section: "batches", label: "Batches" },
  { section: "trends", label: "Trends" },
  { section: "certificates", label: "Certificates issued" },
];
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const pct = (v: number | null) => (v === null ? "No data" : `${Math.round(v)}%`);

/** The period and its custom dates, kept in the address. */
function usePeriod() {
  const raw = useSearch({ strict: false }) as Record<string, unknown>;
  const navigate = useNavigate();
  const period = PERIODS.some((p) => p.value === raw["period"]) ? (raw["period"] as ReportPeriodKey) : "this_month";
  const from = typeof raw["from"] === "string" && DATE.test(raw["from"]) ? raw["from"] : "";
  const to = typeof raw["to"] === "string" && DATE.test(raw["to"]) ? raw["to"] : "";
  const set = (next: { period?: ReportPeriodKey; from?: string; to?: string }) => {
    const merged = { ...raw, ...next } as Record<string, unknown>;
    if (merged["period"] === "this_month") delete merged["period"];
    if (merged["period"] !== "custom") {
      delete merged["from"];
      delete merged["to"];
    }
    for (const k of Object.keys(merged)) if (merged[k] === "" || merged[k] === undefined) delete merged[k];
    void navigate({ to: ".", search: (() => merged) as never, replace: true });
  };
  return { period, from, to, set };
}

export function BranchReports() {
  const { branchId } = useActing("branch");
  const { period, from, to, set } = usePeriod();
  const custom = period === "custom";
  const backwards = custom && !!from && !!to && from > to;
  const ready = !custom || (!!from && !!to && !backwards);
  const range = custom ? { from, to } : {};
  const query = useQuery({
    queryKey: ["branch", "reports", period, range, branchId],
    queryFn: () => branchReportsApi.report({ period, ...range, branch_id: branchId }),
    enabled: ready,
  });
  const [exporting, setExporting] = useState(false);
  const download = async (section: ReportSection) => {
    setExporting(true);
    try {
      await branchReportsApi.exportCsv(section, { period, ...range, branch_id: branchId });
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHead
        title="Reports"
        description="How the branch is doing in the period you pick. Press any figure to see the records behind it."
        actions={<BranchPicker />}
      />
      <Section>
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-full sm:w-52">
            <label htmlFor="rep-period" className="mb-1.5 block text-sm font-medium">
              Period
            </label>
            <NativeSelect id="rep-period" options={PERIODS} value={period} onChange={(e) => set({ period: e.target.value as ReportPeriodKey })} />
          </div>
          {custom && (
            <>
              <div className="w-full sm:w-44">
                <label htmlFor="rep-from" className="mb-1.5 block text-sm font-medium">
                  From
                </label>
                <Input id="rep-from" type="date" value={from} max={to || undefined} onChange={(e) => set({ period, from: e.target.value, to })} />
              </div>
              <div className="w-full sm:w-44">
                <label htmlFor="rep-to" className="mb-1.5 block text-sm font-medium">
                  To
                </label>
                <Input id="rep-to" type="date" value={to} min={from || undefined} onChange={(e) => set({ period, from, to: e.target.value })} />
              </div>
            </>
          )}
          <div className="sm:ml-auto">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" disabled={!ready || exporting}>
                  <Download className="size-4" aria-hidden /> Download CSV
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {EXPORTS.map((e) => (
                  <DropdownMenuItem key={e.section} onSelect={() => void download(e.section)}>
                    {e.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">Each download is one table as a CSV file. It opens in Excel.</p>
        {backwards && (
          <div className="mt-3">
            <StatusNote tone="warning">The From date cannot be after the To date.</StatusNote>
          </div>
        )}
      </Section>

      {!ready ? (
        <StatusNote tone="info">{backwards ? "Fix the dates to see the figures." : "Choose a From and a To date to see the figures."}</StatusNote>
      ) : (
        <QueryView query={query} skeleton="cards">
          {(report) => (
            <>
              <p className="text-sm text-muted-foreground">
                Showing <strong className="font-medium text-foreground">{report.period.label}</strong>: {fmtDate(report.period.from)} to{" "}
                {fmtDate(report.period.to)}.
              </p>
              {FIGURE_GROUPS.map((group) => {
                const figures = group.keys.flatMap((k) => report.figures.filter((f) => f.key === k));
                if (figures.length === 0) return null;
                return (
                  <Section key={group.title} title={group.title}>
                    <Grid cols={4}>
                      {figures.map((f) => (
                        <FigureCard key={f.key} figure={f} />
                      ))}
                    </Grid>
                  </Section>
                );
              })}

              <Section title="Progress by batch">
                <DataTable
                  caption="Progress by batch"
                  rows={report.batches}
                  getKey={(b) => b.batch.batch_id}
                  empty="No batch has students yet."
                  emptyAction={
                    <Button asChild size="sm" variant="outline">
                      <Link to="/branch/batches">Open Batches</Link>
                    </Button>
                  }
                  cols={[
                    {
                      h: "Batch",
                      c: (b) => (
                        <Link
                          to={b.drill.to}
                          {...(b.drill.search && Object.keys(b.drill.search).length ? { search: b.drill.search as never } : {})}
                          className="font-medium text-primary underline-offset-2 hover:underline"
                        >
                          {b.batch.display_name ?? b.batch.batch_code}
                          {b.batch.course_code ? ` (${b.batch.course_code})` : ""}
                        </Link>
                      ),
                    },
                    { h: "State", c: (b) => <StateBadge label={b.state} /> },
                    { h: "Students", c: (b) => b.students },
                    { h: "Classes delivered", c: (b) => pct(b.avg_delivery) },
                    { h: "Attendance", c: (b) => pct(b.avg_attendance) },
                    { h: "Required learning", c: (b) => pct(b.avg_required_learning) },
                    {
                      h: "Below attendance alert",
                      c: (b) => (b.alerts > 0 ? <Tag tone="danger">{`${b.alerts} ${b.alerts === 1 ? "student" : "students"}`}</Tag> : "None"),
                    },
                  ]}
                />
              </Section>

              <Section title="Last six months">
                <TrendsChart trends={report.trends} />
              </Section>
            </>
          )}
        </QueryView>
      )}

      <HowThisWorks>
        <p>Each progress measure (classes delivered, attendance, required learning) is averaged on its own. There is no combined score.</p>
        <p>A figure that says No data has nothing to measure yet, which is different from zero.</p>
        <p>Certificates themselves are issued from Completion and certificates.</p>
      </HowThisWorks>
    </div>
  );
}
