/** My Progress, Results tab: marked work and tests. A row opens the assignment or test, where the feedback is. */
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { assessmentsApi, type MyResult } from "@/api/assessments";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { DataTable, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { fmtDate } from "@/features/shared/format";
import { useT } from "@/lib/i18n";

/** The API sends a plain sentence for each state; this picks the dictionary entry that sets its colour and its translation. */
function stateOf(state: string): { domain: "result" | "work"; code: string } {
  if (state.startsWith("Provisional")) return { domain: "result", code: "Provisional" };
  if (state === "Resubmission requested") return { domain: "work", code: "Resubmission Requested" };
  if (state === "Pending review") return { domain: "work", code: "Under Review" };
  return { domain: "result", code: state };
}

function OpenLink({ row, children, className }: { row: MyResult; children: React.ReactNode; className?: string }) {
  const params = { id: String(row.item_id) };
  return row.kind === "Assignment" ? (
    <Link to="/assignments/$id" params={params} className={className}>
      {children}
    </Link>
  ) : (
    <Link to="/tests/$id" params={params} className={className}>
      {children}
    </Link>
  );
}

export function ResultsTab() {
  const t = useT();
  const query = useQuery({ queryKey: ["results", "mine"], queryFn: assessmentsApi.myResults });
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">{t("resultsHelp")}</p>
      <QueryView query={query} isEmpty={(rows) => rows.length === 0} empty={t("noResults")}>
        {(rows) => (
          <DataTable
            caption={t("results")}
            rows={rows}
            getKey={(r) => r.key}
            cols={[
              {
                h: t("colAssessment"),
                c: (r) => (
                  <div className="space-y-1">
                    <OpenLink row={r} className="font-medium text-primary underline">
                      {r.item}
                    </OpenLink>
                    <div>
                      <Tag>{r.kind === "Assignment" ? t("typeAssignment") : t("typeTest")}</Tag>
                    </div>
                  </div>
                ),
              },
              { h: t("colScore"), c: (r) => r.score ?? (r.state === "Published" ? "—" : t("scoreAfterPublish")) },
              { h: t("colStatus"), c: (r) => <StatusBadge domain={stateOf(r.state).domain} code={stateOf(r.state).code} /> },
              { h: t("colOutcome"), c: (r) => (r.pass_status ? <StatusBadge domain="result" code={r.pass_status === "Passed" ? "Pass" : "Fail"} /> : "—") },
              { h: t("colPublished"), c: (r) => (r.published_at ? fmtDate(r.published_at) : "—") },
              {
                h: t("colActions"),
                c: (r) => (
                  <Button asChild size="sm" variant="outline" className="tap">
                    <OpenLink row={r}>{t("seeFeedback")}</OpenLink>
                  </Button>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <HowThisWorks title={t("howResultsWork")}>
        <ul className="list-disc space-y-1 pl-5">
          <li>{t("resultsRule1")}</li>
          <li>{t("resultsRule2")}</li>
        </ul>
      </HowThisWorks>
    </div>
  );
}
