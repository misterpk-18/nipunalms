import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { deliveryApi, type TopicHub } from "@/api/delivery";
import { Breadcrumbs, type Crumb } from "@/components/lms/breadcrumbs";
import { EmptyState } from "@/components/lms/empty-state";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, QueryView, Section, StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { fmtDateTime, fmtRange } from "@/features/shared/format";
import { useLocalised, useT } from "@/lib/i18n";

/** What the topic's status means for this student, and what to do about it. */
function ProgressNote({ progress }: { progress: NonNullable<TopicHub["progress"]> }) {
  const t = useT();
  if (progress.status === "Done") return <StatusNote tone="success">{t("topicDoneNote")}</StatusNote>;
  if (progress.status === "Work to hand in") return <StatusNote tone="warning">{t("topicWorkNote")}</StatusNote>;
  return <StatusNote tone="info">{t("topicStartNote")}</StatusNote>;
}

function Part({ title, children }: { title: string; children: ReactNode }) {
  return <Section title={title}>{children}</Section>;
}

export function TopicDetail() {
  const t = useT();
  const pick = useLocalised();
  const { topicId } = useParams({ strict: false }) as { topicId: string };
  const query = useQuery({ queryKey: ["delivery", "topic-hub", topicId], queryFn: () => deliveryApi.topicHub(Number(topicId)) });
  return (
    <div className="mx-auto max-w-4xl">
      <QueryView query={query}>
        {(hub) => {
          const crumbs: Crumb[] = [
            { label: t("breadcrumbMyLearning"), to: "/my-courses" },
            { label: hub.enrolment.course.course_code, to: `/courses/${hub.enrolment.enrolment_id}` },
            { label: pick(hub.module.title, hub.module.title_te), to: `/modules/${hub.module.module_id}` },
            { label: pick(hub.topic.title, hub.topic.title_te) },
          ];
          return (
            <>
              <Breadcrumbs items={crumbs} />
              <PageHead
                title={pick(hub.topic.title, hub.topic.title_te)}
                description={hub.topic.outcome ?? undefined}
                actions={
                  <>
                    <Tag tone={hub.topic.is_required ? "info" : "neutral"}>{hub.topic.is_required ? t("required") : t("optional")}</Tag>
                    {hub.progress && <StatusBadge domain="topic" code={hub.progress.status} />}
                  </>
                }
              />
              <div className="space-y-4">
                {hub.progress && <ProgressNote progress={hub.progress} />}

                <Part title={t("topicClasses")}>
                  {hub.sessions.length === 0 ? (
                    <EmptyState reason={t("topicNoClass")} />
                  ) : (
                    <ul className="divide-y">
                      {hub.sessions.map((s) => (
                        <li key={s.session_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                          <div>
                            <Link to="/sessions/$sessionId" params={{ sessionId: String(s.session_id) }} className="text-primary underline">
                              {s.title}
                            </Link>
                            <p className="text-xs text-muted-foreground">
                              {fmtRange(s.starts_at, s.ends_at)} · {s.mode}
                              {s.state === "Delivered" && !s.attendance && ` · ${t("notMarkedYet")}`}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            {s.attendance && <StatusBadge domain="attendance" code={s.attendance} />}
                            <StatusBadge domain="session" code={s.state_label ?? s.state} />
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </Part>

                <Part title={t("topicRecording")}>
                  {hub.recordings.length === 0 ? (
                    <EmptyState reason={t("topicNoRecording")} />
                  ) : (
                    <ul className="divide-y">
                      {hub.recordings.map((r) => (
                        <li key={r.recording_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                          <span className="text-sm">
                            {r.session.title} · {fmtDateTime(r.session.starts_at)}
                          </span>
                          <div className="flex items-center gap-2">
                            <StatusBadge domain="recording" code={r.status} />
                            {r.playable && (
                              <Button asChild size="sm" variant="outline">
                                <Link to="/recordings">{t("watchNow")}</Link>
                              </Button>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </Part>

                <Part title={t("topicMaterials")}>
                  {hub.materials.length === 0 ? (
                    <EmptyState reason={t("topicNoMaterials")} />
                  ) : (
                    <ul className="divide-y">
                      {hub.materials.map((m) => (
                        <li key={m.content_item_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                          <Link to="/resources" className="text-primary underline">
                            {m.title}
                          </Link>
                          <Tag>{m.content_type}</Tag>
                        </li>
                      ))}
                    </ul>
                  )}
                </Part>

                <Part title={t("topicWork")}>
                  {hub.assignments.length === 0 && hub.tests.length === 0 ? (
                    <EmptyState reason={t("topicNoWork")} />
                  ) : (
                    <ul className="divide-y">
                      {hub.assignments.map((a) => (
                        <li key={`a${a.assignment_id}`} className="flex flex-wrap items-center justify-between gap-2 py-2">
                          <div>
                            <Link to="/assignments/$id" params={{ id: String(a.assignment_id) }} className="text-primary underline">
                              {a.title}
                            </Link>
                            <p className="text-xs text-muted-foreground">
                              {a.is_required ? t("required") : t("optional")} · {t("dueAt", { when: fmtDateTime(a.due_at) })}
                            </p>
                          </div>
                          <StatusBadge domain="work" code={a.my?.state} />
                        </li>
                      ))}
                      {hub.tests.map((test) => (
                        <li key={`t${test.test_id}`} className="flex flex-wrap items-center justify-between gap-2 py-2">
                          <div>
                            <Link to="/tests/$id" params={{ id: String(test.test_id) }} className="text-primary underline">
                              {test.title}
                            </Link>
                            <p className="text-xs text-muted-foreground">
                              {test.is_required ? t("required") : t("optional")}
                              {test.closes_at ? ` · ${t("dueAt", { when: fmtDateTime(test.closes_at) })}` : ""}
                            </p>
                          </div>
                          <StatusBadge domain="test" code={test.status} />
                        </li>
                      ))}
                    </ul>
                  )}
                </Part>

                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-4">
                  {hub.next_topic ? (
                    <>
                      <span className="text-sm text-muted-foreground">{t("nextTopic")}</span>
                      <Button asChild className="tap">
                        <Link to="/topics/$topicId" params={{ topicId: String(hub.next_topic.topic_id) }}>
                          {pick(hub.next_topic.title, hub.next_topic.title_te)} →
                        </Link>
                      </Button>
                    </>
                  ) : (
                    <span className="text-sm text-muted-foreground">{t("lastTopic")}</span>
                  )}
                </div>

                <HowThisWorks title={t("topicHowDone")}>
                  <p>{t("topicHowDoneText")}</p>
                </HowThisWorks>
              </div>
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
