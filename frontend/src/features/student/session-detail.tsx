import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { attendanceApi } from "@/api/attendance";
import { deliveryApi, type ClassSession } from "@/api/delivery";
import { KeyValue, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { useApiMutation } from "@/lib/mutation";
import { fmtDate, fmtTime } from "@/features/shared/delivery-ui";
import { useT } from "@/lib/i18n";
import { JoinButton, startsText, useNow } from "./class-time";

/** "I attended" on an online class. The trainer marks the register; this only lets them see who says they were there. */
function AttendedConfirm({ session }: { session: ClassSession }) {
  const t = useT();
  const claim = session.attendance_claim;
  const confirm = useApiMutation(() => attendanceApi.confirmAttended(session.session_id), {
    success: t("attendedSent"),
    invalidate: [["delivery", "session", String(session.session_id)], ["attendance"]],
  });
  if (!claim || !["Live", "Delivered"].includes(session.state)) return null;
  if (claim.claimed_at) return <StatusNote tone="success">{t("attendedDone")}</StatusNote>;
  if (!claim.can_confirm) return claim.reason ? <p className="mt-3 text-sm text-muted-foreground">{claim.reason}</p> : null;
  return (
    <div className="mt-4 space-y-2" data-testid="attended-confirm">
      <p className="text-sm text-muted-foreground">{t("attendedHelp")}</p>
      <Button variant="outline" disabled={confirm.isPending} onClick={() => confirm.mutate(undefined)}>
        {t("attendedConfirm")}
      </Button>
    </div>
  );
}

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
                  <AttendedConfirm session={s} />
                </div>
                <KeyValue
                  items={[
                    [t("whenLabel"), `${fmtDate(s.starts_at)} · ${fmtTime(s.starts_at)}–${fmtTime(s.ends_at)} IST`],
                    [t("deliveryMode"), s.mode + (s.room ? ` · ${s.room}` : "")],
                    [t("trainerLabel"), s.trainer.full_name],
                    [t("serviceBranch"), s.branch.branch_name],
                    [
                      t("batchLabel"),
                      <span key="b" className="font-mono text-xs">
                        {s.batch.batch_code}
                      </span>,
                    ],
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
