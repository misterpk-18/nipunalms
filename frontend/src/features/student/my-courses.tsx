import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { deliveryApi, type MyEnrolment } from "@/api/delivery";
import { Note, PageHead, QueryView, StatusBadge, StatusNote } from "@/components/lms/ui";
import { useT } from "@/lib/i18n";
import { DeliveryBar, mono } from "@/features/shared/delivery-ui";

const KIND_LABEL: Record<string, string> = {
  Combo: "Combo (3 + 1)",
  Standalone: "Standalone",
  "Separately purchased": "Separately purchased",
  Complimentary: "Complimentary (promotional)",
};

export const kindLabel = (kind: string) => KIND_LABEL[kind] ?? kind;

/** The status explanation as the prototype words it: a Pending Verification note while the curriculum is being mapped. */
export function StatusExplanation({ enrolment }: { enrolment: MyEnrolment }) {
  if (enrolment.status === "Curriculum Mapping Pending") return <StatusNote state="Pending Verification">{enrolment.explanation}</StatusNote>;
  return <p className="text-sm text-muted-foreground">{enrolment.explanation}</p>;
}

export function MyCourses() {
  const t = useT();
  const query = useQuery({ queryKey: ["delivery", "my-enrolments"], queryFn: deliveryApi.myEnrolments });
  return (
    <div className="mx-auto max-w-6xl">
      <PageHead title={t("myCourses")} description="One Student Master · multiple Admissions and Course Enrolments" />
      <QueryView query={query} isEmpty={(rows) => rows.length === 0} empty="You have no course enrolments yet.">
        {(rows) => (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {rows.map((e) => (
              <section key={e.enrolment_id} className="flex flex-col rounded-xl border bg-card p-4 shadow-sm" aria-label={e.course.title}>
                <div className="flex flex-wrap gap-2">
                  <StatusBadge tone="info">{kindLabel(e.kind)}</StatusBadge>
                  <StatusBadge>{e.status}</StatusBadge>
                </div>
                <p className="mt-3">{mono(e.course.course_code)}</p>
                <h2 className="font-semibold">{e.course.title}</h2>
                <dl className="mt-2 space-y-1 text-sm">
                  <div>
                    <dt className="inline text-muted-foreground">Service branch: </dt>
                    <dd className="inline">{e.service_branch.branch_name}</dd>
                  </div>
                  <div>
                    <dt className="inline text-muted-foreground">Batch: </dt>
                    <dd className="inline">{e.batch ? mono(e.batch.batch_code) : "Not allocated"}</dd>
                  </div>
                  {e.linked_admission_code && (
                    <div className="text-xs text-muted-foreground">
                      Promotional complimentary — linked to qualifying paid Admission {e.linked_admission_code}
                    </div>
                  )}
                </dl>
                <div className="mt-3">
                  <DeliveryBar delivery={e.delivery} label="Curriculum delivered" />
                </div>
                <div className="mt-3">
                  <StatusExplanation enrolment={e} />
                </div>
                <Link
                  to="/courses/$enrolmentId"
                  params={{ enrolmentId: String(e.enrolment_id) }}
                  className="tap mt-auto inline-flex items-center pt-3 text-sm font-medium text-primary underline"
                >
                  Open course
                </Link>
              </section>
            ))}
          </div>
        )}
      </QueryView>
      <div className="mt-4">
        <Note>Your second course reuses the same student identity. Admission and finance records remain in the CRM.</Note>
      </div>
    </div>
  );
}
