import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { deliveryApi, type ClassSession } from "@/api/delivery";
import { Button } from "@/components/ui/button";
import { KeyValue, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { useT } from "@/lib/i18n";
import { MeetBadge, fmtDate, fmtTime } from "@/features/shared/delivery-ui";

/** The Join Class button: enabled only while the class is Live or about to start and Meet is Associated. */
export function JoinButton({ session }: { session: ClassSession }) {
  const t = useT();
  const join = session.join;
  if (session.mode === "Classroom") return <p className="text-sm text-muted-foreground">{join?.reason ?? "Classroom session"}</p>;
  return (
    <div>
      {join?.enabled && join.url ? (
        <Button asChild>
          <a href={join.url} target="_blank" rel="noreferrer">
            {t("joinClass")}
          </a>
        </Button>
      ) : (
        <Button disabled>{t("joinClass")}</Button>
      )}
      {!join?.enabled && join?.reason && <p className="mt-1 text-xs text-muted-foreground">{join.reason}</p>}
    </div>
  );
}

export function SessionDetail() {
  const { sessionId } = useParams({ strict: false }) as { sessionId: string };
  const query = useQuery({ queryKey: ["delivery", "session", sessionId], queryFn: () => deliveryApi.session(Number(sessionId)) });
  return (
    <div className="mx-auto max-w-5xl">
      <QueryView query={query}>
        {(s) => (
          <>
            <nav aria-label="Breadcrumb" className="mb-2 text-sm">
              {s.topic_path ? (
                <Link to="/topics/$topicId" params={{ topicId: String(s.topic_path.topic_id) }} className="text-primary underline">
                  {s.topic_path.title}
                </Link>
              ) : (
                <Link to="/schedule" className="text-primary underline">
                  Schedule
                </Link>
              )}{" "}
              / {s.title}
            </nav>
            <PageHead title={s.title} description={`Actual Class Session · ${s.session_code}`} actions={<StatusBadge>{s.state}</StatusBadge>} />
            <Section>
              <KeyValue
                items={[
                  ["Date / time", `${fmtDate(s.starts_at)} · ${fmtTime(s.starts_at)}–${fmtTime(s.ends_at)} IST`],
                  ["Mode", s.mode + (s.room ? ` · ${s.room}` : "")],
                  ["Trainer", s.trainer.full_name],
                  ["Branch", s.branch.branch_name],
                  [
                    "Batch",
                    <span key="b" className="font-mono text-xs">
                      {s.batch.batch_code}
                    </span>,
                  ],
                  ["Meet organizer (label)", s.organizer_email ? `${s.organizer_email} — ${s.meet_status_label}` : "Not needed for a classroom session"],
                  ["Meet", <MeetBadge key="m" session={s} />],
                ]}
              />
              <div className="mt-4">
                <JoinButton session={s} />
              </div>
            </Section>
            {s.mode !== "Classroom" && s.meet_status !== "Linked" && (
              <div className="mt-4">
                <StatusNote state="Pending Verification">
                  The Meet link for this class is not associated yet. It appears here once your branch has confirmed it — nothing is assumed from the class
                  time.
                </StatusNote>
              </div>
            )}
          </>
        )}
      </QueryView>
    </div>
  );
}
