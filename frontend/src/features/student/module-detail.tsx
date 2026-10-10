import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { Breadcrumbs, type Crumb } from "@/components/lms/breadcrumbs";
import { deliveryApi } from "@/api/delivery";
import { PageHead, QueryView, Section, StatusBadge, Tag } from "@/components/lms/ui";
import { Meter } from "@/features/shared/attendance-parts";
import { useLocalised, useT } from "@/lib/i18n";

export function ModuleDetail() {
  const t = useT();
  const pick = useLocalised();
  const { moduleId } = useParams({ strict: false }) as { moduleId: string };
  const query = useQuery({ queryKey: ["delivery", "module", moduleId], queryFn: () => deliveryApi.module(Number(moduleId)) });
  return (
    <div className="mx-auto max-w-5xl">
      <QueryView query={query}>
        {(m) => {
          const done = m.topics.filter((topic) => topic.progress?.is_done).length;
          return (
            <>
              <Breadcrumbs
                items={[
                  ...(m.context
                    ? ([
                        { label: t("breadcrumbMyLearning"), to: "/my-courses" },
                        { label: m.context.enrolment.course.course_code, to: `/courses/${m.context.enrolment.enrolment_id}` },
                        ...(m.context.track
                          ? [
                              {
                                label: m.context.track.track_name,
                                to: `/courses/${m.context.enrolment.enrolment_id}/tracks/${m.context.track.enrolment_track_id}`,
                              },
                            ]
                          : []),
                      ] satisfies Crumb[])
                    : []),
                  { label: pick(m.title, m.title_te) },
                ]}
              />
              <PageHead title={pick(m.title, m.title_te)} description={t("topicsCount", { n: m.topics.length })} />
              {m.context && m.topics.length > 0 && (
                <div className="mb-4">
                  <Meter value={Math.round((done * 100) / m.topics.length)} label={t("moduleTopicsDone", { done, total: m.topics.length })} />
                </div>
              )}
              <Section>
                <ul className="space-y-3">
                  {m.topics.map((topic) => (
                    <li key={topic.topic_id} className="rounded-lg border p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Link to="/topics/$topicId" params={{ topicId: String(topic.topic_id) }} className="font-semibold text-primary underline">
                          {pick(topic.title, topic.title_te)}
                        </Link>
                        <div className="flex flex-wrap items-center gap-2">
                          <Tag tone={topic.is_required ? "info" : "neutral"}>{topic.is_required ? t("required") : t("optional")}</Tag>
                          {topic.progress && <StatusBadge domain="topic" code={topic.progress.status} />}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </Section>
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
