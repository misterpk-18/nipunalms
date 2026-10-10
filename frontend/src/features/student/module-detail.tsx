import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { Breadcrumbs, type Crumb } from "@/components/lms/breadcrumbs";
import { deliveryApi } from "@/api/delivery";
import { PageHead, QueryView, Section, StatusBadge, Tag } from "@/components/lms/ui";

export function ModuleDetail() {
  const { moduleId } = useParams({ strict: false }) as { moduleId: string };
  const query = useQuery({ queryKey: ["delivery", "module", moduleId], queryFn: () => deliveryApi.module(Number(moduleId)) });
  return (
    <div className="mx-auto max-w-5xl">
      <QueryView query={query}>
        {(m) => (
          <>
            <Breadcrumbs
              items={[
                ...(m.context
                  ? ([
                      { label: m.context.enrolment.course.course_code, to: `/courses/${m.context.enrolment.enrolment_id}` },
                      ...(m.context.track
                        ? [{ label: m.context.track.track_name, to: `/courses/${m.context.enrolment.enrolment_id}/tracks/${m.context.track.enrolment_track_id}` }]
                        : []),
                    ] satisfies Crumb[])
                  : []),
                { label: m.title },
              ]}
            />
            <PageHead
              title={m.title}
              description={`Module · ${m.curriculum_version.version_label}`}
              actions={m.status ? <StatusBadge domain="session" code={m.status} /> : undefined}
            />
            <Section>
              <ul className="space-y-3">
                {m.topics.map((t) => (
                  <li key={t.topic_id} className="rounded-lg border p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Link to="/topics/$topicId" params={{ topicId: String(t.topic_id) }} className="font-semibold text-primary underline">
                        {t.title}
                      </Link>
                      <Tag tone={t.is_required ? "info" : "neutral"}>{t.is_required ? "Required" : "Optional"}</Tag>
                    </div>
                    {m.context && <p className="mt-1 text-sm text-muted-foreground">{t.session_count} class session(s)</p>}
                  </li>
                ))}
              </ul>
            </Section>
          </>
        )}
      </QueryView>
    </div>
  );
}
