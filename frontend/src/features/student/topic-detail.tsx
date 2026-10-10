import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { EmptyState } from "@/components/lms/empty-state";
import { deliveryApi } from "@/api/delivery";
import { PageHead, QueryView, Section, StatusBadge, Tag } from "@/components/lms/ui";
import { fmtRange } from "@/features/shared/delivery-ui";

export function TopicDetail() {
  const { topicId } = useParams({ strict: false }) as { topicId: string };
  const query = useQuery({ queryKey: ["delivery", "topic", topicId], queryFn: () => deliveryApi.topic(Number(topicId)) });
  return (
    <div className="mx-auto max-w-5xl">
      <QueryView query={query}>
        {(t) => (
          <>
            <Breadcrumbs items={[{ label: t.module.title, to: `/modules/${t.module.module_id}` }, { label: t.title }]} />
            <PageHead
              title={t.title}
              description="Topic"
              actions={<Tag tone={t.is_required ? "info" : "neutral"}>{t.is_required ? "Required" : "Optional"}</Tag>}
            />
            <Section title="Class sessions">
              {t.sessions.length === 0 ? (
                <EmptyState reason="No class covers this topic yet. Classes appear here once your branch schedules them." />
              ) : (
                <ul className="divide-y">
                  {t.sessions.map((s) => (
                    <li key={s.session_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                      <Link to="/sessions/$sessionId" params={{ sessionId: String(s.session_id) }} className="text-primary underline">
                        {s.title}
                      </Link>
                      <span className="text-sm text-muted-foreground">{fmtRange(s.starts_at, s.ends_at)}</span>
                      <StatusBadge domain="session" code={s.state} />
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          </>
        )}
      </QueryView>
    </div>
  );
}
