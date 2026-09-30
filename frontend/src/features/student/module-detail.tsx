import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { deliveryApi } from "@/api/delivery";
import { PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";

export function ModuleDetail() {
  const { moduleId } = useParams({ strict: false }) as { moduleId: string };
  const query = useQuery({ queryKey: ["delivery", "module", moduleId], queryFn: () => deliveryApi.module(Number(moduleId)) });
  return (
    <div className="mx-auto max-w-5xl">
      <QueryView query={query}>
        {(m) => (
          <>
            <nav aria-label="Breadcrumb" className="mb-2 text-sm">
              {m.context ? (
                <>
                  <Link to="/courses/$enrolmentId" params={{ enrolmentId: String(m.context.enrolment.enrolment_id) }} className="text-primary underline">
                    {m.context.enrolment.course.course_code}
                  </Link>
                  {m.context.track && (
                    <>
                      {" / "}
                      <Link
                        to="/courses/$enrolmentId/tracks/$trackId"
                        params={{ enrolmentId: String(m.context.enrolment.enrolment_id), trackId: String(m.context.track.enrolment_track_id) }}
                        className="text-primary underline"
                      >
                        {m.context.track.track_name}
                      </Link>
                    </>
                  )}
                  {" / "}
                </>
              ) : null}
              {m.title}
            </nav>
            <PageHead
              title={m.title}
              description={`Module · ${m.curriculum_version.version_label}`}
              actions={m.status ? <StatusBadge>{m.status}</StatusBadge> : undefined}
            />
            <Section>
              <ul className="space-y-3">
                {m.topics.map((t) => (
                  <li key={t.topic_id} className="rounded-lg border p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Link to="/topics/$topicId" params={{ topicId: String(t.topic_id) }} className="font-semibold text-primary underline">
                        {t.title}
                      </Link>
                      <StatusBadge tone={t.is_required ? "info" : "neutral"}>{t.is_required ? "Required" : "Optional"}</StatusBadge>
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
