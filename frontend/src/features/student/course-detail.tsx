import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { deliveryApi, type ModuleRow } from "@/api/delivery";
import { KeyValue, Note, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { DeliveryBar, fmtDay, fmtRange, mono } from "@/features/shared/delivery-ui";
import { StatusExplanation, kindLabel } from "./my-courses";

export function ModuleList({ modules, empty }: { modules: ModuleRow[]; empty: string }) {
  if (modules.length === 0) return <StatusNote state="Empty">{empty}</StatusNote>;
  return (
    <ul className="space-y-3">
      {modules.map((m) => (
        <li key={m.module_id} className="rounded-lg border p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Link to="/modules/$moduleId" params={{ moduleId: String(m.module_id) }} className="font-semibold text-primary underline">
              {m.title}
            </Link>
            <StatusBadge>{m.status}</StatusBadge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {m.topic_count} topic(s), {m.required_topic_count} required · {m.session_count} class session(s), {m.delivered_count} delivered
          </p>
        </li>
      ))}
    </ul>
  );
}

export function CourseDetail() {
  const { enrolmentId } = useParams({ strict: false }) as { enrolmentId: string };
  const query = useQuery({ queryKey: ["delivery", "my-enrolment", enrolmentId], queryFn: () => deliveryApi.myEnrolment(Number(enrolmentId)) });
  return (
    <div className="mx-auto max-w-6xl">
      <QueryView query={query}>
        {(e) => (
          <>
            <nav aria-label="Breadcrumb" className="mb-2 text-sm">
              <Link to="/my-courses" className="text-primary underline">
                My Courses
              </Link>{" "}
              / {e.course.course_code}
            </nav>
            <PageHead title={e.course.title} description={`${e.course.course_code} · ${kindLabel(e.kind)}`} />
            <div className="grid gap-4 lg:grid-cols-3">
              <Section title="Enrolment details" className="lg:col-span-2">
                <KeyValue
                  items={[
                    [
                      "Admission reference (CRM)",
                      `${e.linked_admission_code ? `Linked to ${e.linked_admission_code} (qualifying paid Admission)` : `${e.admission.admission_code} (CRM)`}`,
                    ],
                    ["Service branch", e.service_branch.branch_name],
                    ["Collecting branch (CRM)", e.collecting_branch.branch_name],
                    ["Batch", e.batch ? mono(e.batch.batch_code) : "Not allocated"],
                    ["Trainer(s)", e.trainers.length ? e.trainers.map((t) => `${t.full_name} (${t.role})`).join(", ") : "Not assigned"],
                    ["Curriculum version", e.curriculum_version?.version_label ?? "Curriculum Mapping Pending"],
                    ["Delivery mode", e.mode],
                    ["Joining Date", e.joining_date ? fmtDay(e.joining_date) : "Pending — first confirmed regular class"],
                    [
                      "Recording / material access until",
                      e.joining_date ? (e.access_end ? fmtDay(e.access_end) : "Set from your Joining Date") : "Pending — starts from confirmed Joining Date",
                    ],
                    ["Certificate status", <StatusBadge key="c">{e.certificate_status}</StatusBadge>],
                    ["Support", `Academic Coordinator — ${e.service_branch.branch_name}`],
                  ]}
                />
                <div className="mt-3">
                  <StatusExplanation enrolment={e} />
                </div>
              </Section>
              <div className="space-y-4">
                <Section title="Delivery">
                  <DeliveryBar delivery={e.delivery} label="Curriculum delivered" />
                  <p className="mt-2 text-xs text-muted-foreground">
                    {e.delivery.upcoming} upcoming · {e.delivery.cancelled} cancelled. Attendance, required-learning and engagement measures appear on{" "}
                    <Link to="/progress" className="underline">
                      Progress
                    </Link>
                    .
                  </p>
                </Section>
                <Section title="Finance summary (read-only)">
                  {e.finance ? (
                    <p className="text-sm">
                      Admission fee: ₹ {e.finance.fee_total} · Verified receipts: ₹ {e.finance.verified_paid} · Due: ₹ {e.finance.balance}
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">No finance summary from the CRM yet.</p>
                  )}
                  <p className="mt-1 text-xs text-muted-foreground">Shown only where permitted. CRM is authoritative.</p>
                  <Link to="/finance" className="text-sm text-primary underline">
                    Fees & receipts
                  </Link>
                </Section>
              </div>
            </div>

            {e.tracks.length > 0 && (
              <Section className="mt-4" title="Combo programme — one paid Admission · 3 main tracks + included booster">
                <ul className="grid gap-3 md:grid-cols-2">
                  {e.tracks.map((t) => (
                    <li key={t.enrolment_track_id} className="rounded-lg border p-3">
                      <div className="flex flex-wrap gap-2">
                        <StatusBadge tone={t.role === "Included booster" ? "neutral" : "info"}>{t.role}</StatusBadge>
                        {mono(t.track_code)}
                      </div>
                      <p className="mt-1 font-medium">{t.track_name}</p>
                      <p className="text-xs text-muted-foreground">{t.curriculum_version?.version_label ?? "Curriculum Mapping Pending"}</p>
                      <div className="mt-2">
                        <DeliveryBar delivery={t.delivery} label="Delivered" />
                      </div>
                      <Link
                        to="/courses/$enrolmentId/tracks/$trackId"
                        params={{ enrolmentId: String(e.enrolment_id), trackId: String(t.enrolment_track_id) }}
                        className="tap mt-1 inline-flex items-center text-sm text-primary underline"
                      >
                        Open track
                      </Link>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {e.modules.length > 0 && (
              <Section className="mt-4" title={e.tracks.length ? "Programme modules" : "Modules"}>
                <ModuleList modules={e.modules} empty="No modules released yet." />
              </Section>
            )}

            {e.next_sessions.length > 0 && (
              <Section className="mt-4" title="Coming up">
                <ul className="divide-y text-sm">
                  {e.next_sessions.map((s) => (
                    <li key={s.session_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                      <Link to="/sessions/$sessionId" params={{ sessionId: String(s.session_id) }} className="text-primary underline">
                        {s.title}
                      </Link>
                      <span className="text-muted-foreground">
                        {fmtRange(s.starts_at, s.ends_at)} · {s.mode} · {s.trainer}
                      </span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {!e.curriculum_version && (
              <div className="mt-4">
                <StatusNote state="Pending Verification">
                  Curriculum Mapping Pending — Recovery Owner: Academic Coordinator — {e.service_branch.branch_name}.
                </StatusNote>
              </div>
            )}
            <div className="mt-4">
              <Note>Hierarchy: My Course / Combo → Track → Module → Topic → Class session.</Note>
            </div>
          </>
        )}
      </QueryView>
    </div>
  );
}
