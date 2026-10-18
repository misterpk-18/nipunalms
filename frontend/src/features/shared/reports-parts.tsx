/** Pieces of the Reports screen: the clickable figure cards and the monthly trends chart with its table. */
import { Link } from "@tanstack/react-router";
import { Bar, CartesianGrid, ComposedChart, Line, XAxis, YAxis } from "recharts";
import type { ReportFigure, ReportTrend } from "@/api/branch-reports";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { DataTable } from "@/components/lms/ui";

const shown = (f: ReportFigure) =>
  f.value === null ? null : f.unit === "%" ? `${Math.round(f.value)}%` : `${f.value.toLocaleString("en-IN")}${f.unit ? ` ${f.unit}` : ""}`;

/** One figure; the whole card opens the screen that holds the records behind it. A missing value says "No data", never 0. */
export function FigureCard({ figure }: { figure: ReportFigure }) {
  const value = shown(figure);
  const body = (
    <>
      <p className="text-xs text-muted-foreground">{figure.label}</p>
      {value === null ? (
        <p className="mt-1 text-lg font-semibold text-muted-foreground">No data</p>
      ) : (
        <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      )}
      {figure.hint && <p className="mt-1 text-xs text-muted-foreground">{figure.hint}</p>}
    </>
  );
  const drill = figure.drill;
  if (!drill) return <div className="block min-w-0 rounded-xl border bg-card p-4 shadow-sm">{body}</div>;
  return (
    <Link
      to={drill.to}
      {...(drill.search && Object.keys(drill.search).length ? { search: drill.search as never } : {})}
      className="block min-w-0 rounded-xl border bg-card p-4 shadow-sm hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      {body}
      <p className="mt-2 text-xs font-medium text-primary">See the records</p>
    </Link>
  );
}

const CONFIG = {
  classes_held: { label: "Classes held", color: "var(--chart-1)" },
  attendance_rate: { label: "Attendance rate (%)", color: "var(--chart-2)" },
} satisfies ChartConfig;

export function TrendsChart({ trends }: { trends: ReportTrend[] }) {
  return (
    <div className="space-y-4">
      <ChartContainer
        config={CONFIG}
        className="aspect-auto h-64 w-full"
        role="img"
        aria-label="Classes held and attendance rate for each of the last six months"
      >
        <ComposedChart data={trends} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="label" tickLine={false} axisLine={false} />
          <YAxis yAxisId="left" allowDecimals={false} tickLine={false} axisLine={false} width={32} />
          <YAxis yAxisId="right" orientation="right" domain={[0, 100]} tickLine={false} axisLine={false} width={36} unit="%" />
          <ChartTooltip content={<ChartTooltipContent />} />
          <ChartLegend content={<ChartLegendContent />} />
          <Bar yAxisId="left" dataKey="classes_held" fill="var(--color-classes_held)" radius={[4, 4, 0, 0]} />
          <Line yAxisId="right" dataKey="attendance_rate" stroke="var(--color-attendance_rate)" strokeWidth={2} dot={{ r: 3 }} connectNulls />
        </ComposedChart>
      </ChartContainer>
      <DataTable
        caption="Month by month"
        rows={trends}
        getKey={(t) => t.month}
        cols={[
          { h: "Month", c: (t) => t.label },
          { h: "Classes held", c: (t) => t.classes_held },
          { h: "Attendance rate", c: (t) => (t.attendance_rate === null ? "No data" : `${Math.round(t.attendance_rate)}%`) },
          { h: "Courses marked complete", c: (t) => t.completed },
          { h: "Certificates issued", c: (t) => t.certificates },
          { h: "Support requests opened", c: (t) => t.support_opened },
        ]}
      />
    </div>
  );
}
