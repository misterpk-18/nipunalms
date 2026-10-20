/** One student, read-only, for the Branch Manager: who they are, their courses and batches, and where each admission stands. */
import { Link, useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { branchApi } from "@/api/branch";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { DataTable, KeyValue, PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { batchName } from "@/features/shared/waiting-student";
import { fmtDate } from "@/features/shared/format";

export function BranchStudentPage() {
  const { id } = useParams({ strict: false }) as { id: string };
  const query = useQuery({ queryKey: ["branch", "student", Number(id)], queryFn: () => branchApi.student(Number(id)) });
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <QueryView query={query} skeleton="detail">
        {(s) => (
          <>
            <Breadcrumbs items={[{ label: "Waiting for a batch", to: "/branch/waiting" }, { label: s.full_name }]} />
            <PageHead title={s.full_name} description={`${s.student_code} · ${s.service_branch.branch_name}`} />

            <Section title="Student">
              <KeyValue
                items={[
                  [
                    "Student ID",
                    <span key="id" className="font-mono">
                      {s.student_code}
                    </span>,
                  ],
                  ["Mobile", s.mobile ?? "None on record"],
                  ["Email", s.email ?? "None on record"],
                  ["Account", <StatusBadge key="a" domain="account" code={s.activation_status} />],
                  ["Service branch", s.service_branch.branch_name],
                  ...(s.original_branch.branch_id !== s.service_branch.branch_id ? [["Admitted at", s.original_branch.branch_name] as [string, string]] : []),
                ]}
              />
            </Section>

            <Section title="Courses">
              <DataTable
                caption="Courses and batches"
                rows={s.enrolments}
                getKey={(e) => e.enrolment_id}
                empty="No courses at your branch yet."
                cols={[
                  { h: "Course", c: (e) => e.course.title },
                  { h: "Mode", c: (e) => e.mode },
                  { h: "Status", c: (e) => <StatusBadge domain="enrolment" code={e.status} /> },
                  {
                    h: "Batch",
                    c: (e) =>
                      e.batch ? (
                        <Link to="/branch/batches/$id" params={{ id: String(e.batch.batch_id) }} className="text-primary underline-offset-2 hover:underline">
                          {batchName(e.batch)}
                        </Link>
                      ) : e.status === "Allocation Pending" ? (
                        <Button asChild size="sm" variant="outline">
                          <Link to="/branch/waiting" search={{ q: s.student_code }}>
                            Allocate
                          </Link>
                        </Button>
                      ) : (
                        "No batch"
                      ),
                  },
                  { h: "Joined", c: (e) => (e.joining_date ? fmtDate(e.joining_date) : "Not yet") },
                ]}
              />
            </Section>

            <Section title="Admissions">
              <DataTable
                caption="Admissions"
                rows={s.admissions}
                getKey={(a) => a.admission_id}
                empty="No admissions at your branch."
                cols={[
                  { h: "Admission", c: (a) => <span className="font-mono">{a.admission_code}</span> },
                  { h: "Course", c: (a) => a.course.title },
                  { h: "Admitted", c: (a) => fmtDate(a.admission_date) },
                  { h: "Planned start", c: (a) => fmtDate(a.planned_start_date) },
                  { h: "Preferred batch", c: (a) => a.preferred_batch_code ?? "None" },
                ]}
              />
            </Section>
          </>
        )}
      </QueryView>
    </div>
  );
}
