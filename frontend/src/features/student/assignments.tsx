import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { assessmentsApi, type AssignmentState } from "@/api/assessments";
import { PageHead, PillTabs, QueryView, StatusBadge, StatusNote } from "@/components/lms/ui";
import { useT } from "@/lib/i18n";
import { formatIst } from "@/lib/format";

const TABS: readonly AssignmentState[] = ["Upcoming", "Due", "Overdue", "Submitted", "Under Review", "Reviewed", "Resubmission Requested"];

export function Assignments() {
  const t = useT();
  const [tab, setTab] = useState<AssignmentState>("Due");
  const query = useQuery({ queryKey: ["assignments", "list", "student"], queryFn: () => assessmentsApi.assignments() });

  return (
    <div className="mx-auto max-w-5xl">
      <PageHead title={t("assignments")} description="Assignments and projects for the batches you are allocated to." />
      <PillTabs tabs={TABS} value={tab} onChange={setTab} label="Assignment views" />
      <QueryView query={query}>
        {(page) => {
          const rows = page.data.filter((a) => a.my?.state === tab);
          if (rows.length === 0) return <StatusNote state="Empty">No assignments in this view.</StatusNote>;
          return (
            <ul className="space-y-3">
              {rows.map((a) => (
                <li key={a.assignment_id} className="rounded-xl border bg-card p-4 shadow-sm">
                  <div className="flex flex-wrap gap-2">
                    <StatusBadge tone={a.is_required ? "info" : "neutral"}>{a.is_required ? "Required" : "Optional"}</StatusBadge>
                    <StatusBadge>{a.my?.state}</StatusBadge>
                    {a.my?.is_late && <StatusBadge tone="warning">Submitted late</StatusBadge>}
                  </div>
                  <Link to="/assignments/$id" params={{ id: String(a.assignment_id) }} className="mt-2 block font-semibold text-primary underline">
                    {a.title}
                  </Link>
                  <p className="text-sm text-muted-foreground">
                    {a.module?.title ?? a.kind}
                    {a.topic ? ` → ${a.topic.title}` : ""} · Due {formatIst(a.due_at)}
                  </p>
                </li>
              ))}
            </ul>
          );
        }}
      </QueryView>
    </div>
  );
}
