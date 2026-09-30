import { useQuery } from "@tanstack/react-query";
import { assessmentsApi } from "@/api/assessments";
import { DataTable, Note, PageHead, QueryView, StatusBadge } from "@/components/lms/ui";
import { formatIst } from "@/lib/format";
import { useT } from "@/lib/i18n";

export function Results() {
  const t = useT();
  const query = useQuery({ queryKey: ["results", "mine"], queryFn: assessmentsApi.myResults });
  return (
    <div className="mx-auto max-w-4xl">
      <PageHead title={t("results")} description="Published academic results, distinguished from provisional and pending work." />
      <QueryView query={query} isEmpty={(rows) => rows.length === 0} empty="No assessed work yet.">
        {(rows) => (
          <DataTable
            caption="Results"
            rows={rows}
            getKey={(r) => r.key}
            cols={[
              { h: "Assessment", c: (r) => r.item },
              { h: "Type", c: (r) => r.type },
              { h: "Score", c: (r) => r.score ?? (r.state === "Published" ? "—" : "Withheld until publication") },
              { h: "State", c: (r) => <StatusBadge>{r.state}</StatusBadge> },
              { h: "Result", c: (r) => (r.pass_status ? <StatusBadge>{r.pass_status}</StatusBadge> : "—") },
              { h: "Published", c: (r) => formatIst(r.published_at) },
            ]}
          />
        )}
      </QueryView>
      <div className="mt-4">
        <Note>Only Published results are final. Provisional marks are not shown as scores.</Note>
      </div>
    </div>
  );
}
