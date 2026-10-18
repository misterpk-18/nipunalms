import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { deliveryApi, type ModuleRow } from "@/api/delivery";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { EmptyState } from "@/components/lms/empty-state";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { KeyValue, PageHead, QueryView, Section, StatusBadge, Tag } from "@/components/lms/ui";
import { Meter } from "@/features/shared/attendance-parts";
import { fmtDay, fmtRange, mono } from "@/features/shared/delivery-ui";
import { useLocalised, useT } from "@/lib/i18n";
import { ContinueButton, StatusExplanation, useKindLabel } from "./my-courses";

export function ModuleList({ modules, empty }: { modules: ModuleRow[]; empty: string }) {
  const t = useT();
  const pick = useLocalised();
  if (modules.length === 0) return <EmptyState reason={empty} />;
  return (
    <ul className="space-y-3">
      {modules.map((m) => (
        <li key={m.module_id} className="rounded-lg border p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Link to="/modules/$moduleId" params={{ moduleId: String(m.module_id) }} className="font-semibold text-primary underline">
              {pick(m.title, m.title_te)}
            </Link>
            <StatusBadge domain="session" code={m.status} />
          </div>
          <div className="mt-2">
            <Meter value={m.percent} label={t("moduleTopicsDone", { done: m.topics_done, total: m.topic_count })} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function CourseDetail() {
  const t = useT();
  const kindLabel = useKindLabel();
  const { enrolmentId } = useParams({ strict: false }) as { enrolmentId: string };
  const query = useQuery({ queryKey: ["delivery", "my-enrolment", enrolmentId], queryFn: () => deliveryApi.myEnrolment(Number(enrolmentId)) });
  return (
    <div className="mx-auto max-w-5xl">
      <QueryView query={query}>
        {(e) => (
          <>
            <Breadcrumbs items={[{ label: t("breadcrumbMyLearning"), to: "/my-courses" }, { label: e.course.course_code }]} />
            <PageHead title={e.course.title} description={`${e.course.course_code} · ${kindLabel(e.kind)}`} actions={<ContinueButton enrolment={e} />} />
            <div className="mb-4 space-y-3">
              <StatusExplanation enrolment={e} />
              {e.topics && e.topics.total > 0 && <Meter value={e.topics.percent} label={t("topicsDone", { done: e.topics.done, total: e.topics.total })} />}
            </div>

            <Section className="mb-4" title={t("yourBatch")}>
              {e.batch && e.timetable ? (
                <KeyValue
                  items={[
                    [t("batchLabel"), mono(e.batch.batch_code)],
                    [t("trainersLabel"), e.trainers.length ? e.trainers.map((tr) => tr.full_name).join(", ") : t("notAssigned")],
                    [t("roomLabel"), e.timetable.location ?? t("notSet")],
                    [
                      t("timetableLabel"),
                      [e.timetable.schedule_days.join(", "), e.timetable.start_time && e.timetable.end_time ? `${e.timetable.start_time}–${e.timetable.end_time} IST` : ""]
                        .filter(Boolean)
                        .join(" · ") || t("notSet"),
                    ],
                    [t("deliveryMode"), e.timetable.mode],
                  ]}
                />
              ) : (
                <EmptyState reason={t("notAllocated")} />
              )}
            </Section>

            {e.tracks.length > 0 && (
              <Section className="mb-4" title={t("tracksTitle")}>
                <ul className="grid gap-3 md:grid-cols-2">
                  {e.tracks.map((tr) => (
                    <li key={tr.enrolment_track_id} className="rounded-lg border p-3">
                      <div className="flex flex-wrap gap-2">
                        <Tag tone={tr.role === "Included booster" ? "neutral" : "info"}>{tr.role}</Tag>
                      </div>
                      <p className="mt-1 font-medium">{tr.track_name}</p>
                      {tr.topics && tr.topics.total > 0 && (
                        <div className="mt-2">
                          <Meter value={tr.topics.percent} label={t("topicsDone", { done: tr.topics.done, total: tr.topics.total })} />
                        </div>
                      )}
                      <Link
                        to="/courses/$enrolmentId/tracks/$trackId"
                        params={{ enrolmentId: String(e.enrolment_id), trackId: String(tr.enrolment_track_id) }}
                        className="tap mt-1 inline-flex items-center text-sm text-primary underline"
                      >
                        {t("openTrack")}
                      </Link>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            <Section className="mb-4" title={e.tracks.length ? t("programmeModules") : t("modulesTitle")}>
              <ModuleList modules={e.modules} empty={t("noModulesYet")} />
            </Section>

            {e.next_sessions.length > 0 && (
              <Section className="mb-4" title={t("comingUp")}>
                <ul className="divide-y text-sm">
                  {e.next_sessions.map((s) => (
                    <li key={s.session_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                      <Link to="/sessions/$sessionId" params={{ sessionId: String(s.session_id) }} className="text-primary underline">
                        {s.title}
                      </Link>
                      <span className="text-muted-foreground">
                        {fmtRange(s.starts_at, s.ends_at)} · {s.mode} · {s.trainer}{s.room ? ` · ${s.room}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            <HowThisWorks title={t("courseInfo")}>
              <p>{t("courseInfoHelp")}</p>
              <KeyValue
                items={[
                  [t("serviceBranch"), e.service_branch.branch_name],
                  [t("batchLabel"), e.batch ? mono(e.batch.batch_code) : t("notAllocated")],
                  [t("trainersLabel"), e.trainers.length ? e.trainers.map((tr) => tr.full_name).join(", ") : t("notAssigned")],
                  [t("deliveryMode"), e.mode],
                  [t("joiningDate"), e.joining_date ? fmtDay(e.joining_date) : t("joiningPending")],
                  [t("accessUntil"), e.joining_date ? (e.access_end ? fmtDay(e.access_end) : "—") : t("accessPending")],
                  [t("certificateLabel"), <StatusBadge key="c" domain="certificate" code={e.certificate_status} />],
                  [
                    t("classesDelivered"),
                    e.delivery.percent === null ? t("noClassesPlanned") : t("classesHeld", { done: e.delivery.delivered, total: e.delivery.planned }),
                  ],
                  ...(e.finance
                    ? [
                        [t("feeSummary"), t("feeLine", { total: e.finance.fee_total, paid: e.finance.verified_paid, due: e.finance.balance })] as [
                          string,
                          string,
                        ],
                      ]
                    : []),
                ]}
              />
              <Link to="/my-account" search={{ tab: "fees" }} className="text-primary underline">
                {t("feesAndReceipts")}
              </Link>
            </HowThisWorks>
          </>
        )}
      </QueryView>
    </div>
  );
}
