import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { deliveryApi } from "@/api/delivery";
import { PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { fmtRange } from "@/features/shared/delivery-ui";

export function TopicDetail() {
  const { topicId } = useParams({ strict: false }) as { topicId: string };
  const query = useQuery({ queryKey: ["delivery", "topic", topicId], queryFn: () => deliveryApi.topic(Number(topicId)) });
  return (
    <div className="mx-auto max-w-5xl">
      <QueryView query={query}>
        {(t) => (
          <>
            <nav aria-label="Breadcrumb" className="mb-2 text-sm">
              <Link to="/modules/$moduleId" params={{ moduleId: String(t.module.module_id) }} className="text-primary underline">
                {t.module.title}
              </Link>{" "}
              / {t.title}
            </nav>
            <PageHead
              title={t.title}
              description="Topic"
              actions={<StatusBadge tone={t.is_required ? "info" : "neutral"}>{t.is_required ? "Required" : "Optional"}</StatusBadge>}
            />
            <Section title="Class sessions">
              {t.sessions.length === 0 ? (
                <StatusNote state="Empty">No class session covers this topic yet.</StatusNote>
              ) : (
                <ul className="divide-y">
                  {t.sessions.map((s) => (
                    <li key={s.session_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                      <Link to="/sessions/$sessionId" params={{ sessionId: String(s.session_id) }} className="text-primary underline">
                        {s.title}
                      </Link>
                      <span className="text-sm text-muted-foreground">{fmtRange(s.starts_at, s.ends_at)}</span>
                      <StatusBadge>{s.state}</StatusBadge>
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
