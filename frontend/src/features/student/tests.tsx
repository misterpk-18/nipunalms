import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { assessmentsApi } from "@/api/assessments";
import { Note, PageHead, QueryView, StatusBadge } from "@/components/lms/ui";
import { formatIst } from "@/lib/format";
import { useT } from "@/lib/i18n";

export function Tests() {
  const t = useT();
  const query = useQuery({ queryKey: ["tests", "list", "student"], queryFn: () => assessmentsApi.tests() });
  return (
    <div className="mx-auto max-w-5xl">
      <PageHead title={t("tests")} description="Practice quizzes, module and final tests, coding exercises, mock tests and interviews." />
      <QueryView query={query} isEmpty={(p) => p.data.length === 0} empty="No tests for your batches yet.">
        {(page) => (
          <ul className="grid gap-3 md:grid-cols-2">
            {page.data.map((test) => (
              <li key={test.test_id} className="rounded-xl border bg-card p-4 shadow-sm">
                <div className="flex flex-wrap gap-2">
                  <StatusBadge tone="info">{test.kind}</StatusBadge>
                  <StatusBadge>{test.my?.my_status ?? (test.status === "Scheduled" ? `Scheduled ${formatIst(test.opens_at)}` : test.status)}</StatusBadge>
                </div>
                <Link to="/tests/$id" params={{ id: String(test.test_id) }} className="mt-2 block font-semibold text-primary underline">
                  {test.title}
                </Link>
                <p className="text-sm text-muted-foreground">{test.duration_minutes ? `Duration ${test.duration_minutes} min` : "Untimed"}</p>
              </li>
            ))}
          </ul>
        )}
      </QueryView>
      <div className="mt-4">
        <Note>Completing an assessment does not equal attendance, course completion or certificate issue.</Note>
      </div>
    </div>
  );
}
