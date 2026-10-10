import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { deliveryApi } from "@/api/delivery";
import { KeyValue, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { fmtDate, fmtTime } from "@/features/shared/delivery-ui";
import { useT } from "@/lib/i18n";
import { JoinButton, startsText, useNow } from "./class-time";

export function SessionDetail() {
  const t = useT();
  const now = useNow();
  const { sessionId } = useParams({ strict: false }) as { sessionId: string };
  const query = useQuery({
    queryKey: ["delivery", "session", sessionId],
    queryFn: () => deliveryApi.session(Number(sessionId)),
    // the Join link appears 15 minutes before the class
    refetchInterval: 30_000,
  });
  return (
    <div className="mx-auto max-w-4xl">
      <QueryView query={query} skeleton="detail">
        {(s) => {
          const countdown = s.state === "Cancelled" ? null : startsText(t, s, now);
          return (
            <>
              <Breadcrumbs
                items={[
                  s.topic_path ? { label: s.topic_path.title, to: `/topics/${s.topic_path.topic_id}` } : { label: t("schedule"), to: "/schedule" },
                  { label: s.title },
                ]}
              />
              <PageHead
                title={s.title}
                description={t("classCode", { code: s.session_code })}
                actions={
                  <>
                    <StatusBadge domain="session" code={s.state_label} />
                    {s.mode !== "Classroom" && s.meet_status !== "Linked" && <StatusBadge domain="meet" code={s.meet_status_label} />}
                  </>
                }
              />
              <Section>
                <div className="mb-4">
                  {countdown && s.state !== "Cancelled" && <p className="mb-2 text-lg font-semibold">{countdown}</p>}
                  {s.state === "Cancelled" ? <StatusNote tone="warning">{t("cancelledNote")}</StatusNote> : <JoinButton session={s} />}
                </div>
                <KeyValue
                  items={[
                    [t("whenLabel"), `${fmtDate(s.starts_at)} · ${fmtTime(s.starts_at)}–${fmtTime(s.ends_at)} IST`],
                    [t("deliveryMode"), s.mode + (s.room ? ` · ${s.room}` : "")],
                    [t("trainerLabel"), s.trainer.full_name],
                    [t("serviceBranch"), s.branch.branch_name],
                    [t("batchLabel"), <span key="b" className="font-mono text-xs">{s.batch.batch_code}</span>],
                    ...(s.topic_path
                      ? ([
                          [
                            t("topicLabel"),
                            <Link key="t" to="/topics/$topicId" params={{ topicId: String(s.topic_path.topic_id) }} className="text-primary underline">
                              {s.topic_path.title}
                            </Link>,
                          ],
                        ] as [string, ReactNode][])
                      : []),
                  ]}
                />
              </Section>
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
