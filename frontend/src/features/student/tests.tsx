import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { assessmentsApi, type TestItem } from "@/api/assessments";
import { Note, PageHead, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { formatIst } from "@/lib/format";
import { useT } from "@/lib/i18n";

/** The student's state for a test: their booking or attempt first, otherwise whether the test is open. */
export function MyTestStatus({ test }: { test: TestItem }) {
  const mine = test.my?.my_status;
  if (mine) {
    if (mine.startsWith("Submitted")) return <StatusBadge domain="work" code="Submitted" label={mine} />;
    if (mine === "In progress") return <StatusBadge domain="test" code="In progress" />;
    return <StatusBadge domain="slot" code={mine} />;
  }
  if (test.status === "Scheduled") return <StatusBadge domain="test" code="Scheduled" label={`Scheduled ${formatIst(test.opens_at)}`} />;
  return <StatusBadge domain="test" code={test.status === "Available" ? "Released" : test.status} />;
}

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
                  <Tag tone="info">{test.kind}</Tag>
                  <MyTestStatus test={test} />
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
