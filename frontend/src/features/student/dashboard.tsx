import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { Award, CalendarClock, ClipboardList, LifeBuoy, PlayCircle, Radio, Sparkles, TrendingUp, Wallet, type LucideIcon } from "lucide-react";
import { deliveryApi } from "@/api/delivery";
import { useMyHome, type HomeBatchChange, type StudentHome, type UpNext } from "@/api/dashboards";
import { EmptyState } from "@/components/lms/empty-state";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { GettingStartedCard } from "@/components/lms/getting-started";
import { PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Meter } from "@/features/shared/attendance-parts";
import { CardGap } from "@/features/shared/dashboard-parts";
import { fmtDate, fmtDateTime, fmtRange } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { useLanguage, useLocalised, useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { SlotPreferenceCard } from "./batch-changes";

type T = ReturnType<typeof useT>;

// ---------------------------------------------------------------- Up next

/** The one thing to do now: a live class, work due today, or the next topic. One sentence and one button. */
function UpNextHero({ up }: { up: UpNext }) {
  const t = useT();
  const pick = useLocalised();
  const frame = (icon: LucideIcon, eyebrow: string, title: string, detail: ReactNode, action: ReactNode, urgent = false) => {
    const Icon = icon;
    return (
      <section
        aria-label={t("upNext")}
        className={cn(
          "flex flex-col gap-4 rounded-2xl border p-5 shadow-sm sm:flex-row sm:items-center",
          urgent ? "border-primary/40 bg-primary/5" : "bg-card",
        )}
      >
        <span className="grid size-12 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground">
          <Icon className="size-6" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t("upNext")} · {eyebrow}
          </p>
          <h2 className="mt-0.5 text-xl font-semibold leading-snug">{title}</h2>
          <div className="mt-1 text-sm text-muted-foreground">{detail}</div>
        </div>
        <div className="shrink-0">{action}</div>
      </section>
    );
  };

  switch (up.kind) {
    case "live_class": {
      const { join } = up;
      return frame(
        Radio,
        up.live ? t("upNextLiveNow") : t("upNextClassSoon"),
        up.title,
        <>
          {fmtDate(up.starts_at)} · {fmtRange(up.starts_at, up.ends_at)} · {up.mode}
          {up.room ? ` · ${up.room}` : ""}
          {!join.enabled && join.reason && <span className="block">{join.reason}</span>}
        </>,
        join.enabled && join.url ? (
          <Button asChild size="lg" className="tap">
            <a href={join.url} target="_blank" rel="noreferrer">
              {t("joinClass")}
            </a>
          </Button>
        ) : (
          <Button asChild size="lg" variant="outline" className="tap">
            <Link to="/sessions/$sessionId" params={{ sessionId: String(up.session_id) }}>
              {t("viewClass")}
            </Link>
          </Button>
        ),
        true,
      );
    }
    case "work_due": {
      const overdue = up.work.state === "Overdue";
      return frame(
        ClipboardList,
        overdue ? t("upNextWorkOverdue") : t("upNextWorkDue"),
        up.title,
        <>
          {overdue ? t("overdueSince", { when: fmtDateTime(up.due_at) }) : t("dueAt", { when: fmtDateTime(up.due_at) })}
          {up.count > 1 && <span className="block">{t("upNextWorkMore", { n: up.count })}</span>}
        </>,
        up.work.kind === "assignment" ? (
          <Button asChild size="lg" className="tap">
            <Link to="/assignments/$id" params={{ id: String(up.work.id) }}>
              {t("openTask")}
            </Link>
          </Button>
        ) : (
          <Button asChild size="lg" className="tap">
            <Link to="/tests/$id" params={{ id: String(up.work.id) }}>
              {t("openTest")}
            </Link>
          </Button>
        ),
        true,
      );
    }
    case "continue_topic":
      return frame(
        PlayCircle,
        t("upNextContinue"),
        pick(up.title, up.title_te),
        pick(up.module.title, up.module.title_te),
        <Button asChild size="lg" className="tap">
          <Link to="/topics/$topicId" params={{ topicId: String(up.topic_id) }}>
            {t("openTopic")}
          </Link>
        </Button>,
      );
    case "next_class":
      return frame(
        CalendarClock,
        t("upNextNextClass"),
        up.title,
        t("startsAt", { when: `${fmtDate(up.starts_at)}, ${fmtRange(up.starts_at, up.ends_at)}` }),
        <Button asChild size="lg" variant="outline" className="tap">
          <Link to="/sessions/$sessionId" params={{ sessionId: String(up.session_id) }}>
            {t("viewClass")}
          </Link>
        </Button>,
      );
    default:
      return frame(Sparkles, t("upNextNothing"), t("upNextNothing"), t("upNextNothingHelp"), null);
  }
}

// ---------------------------------------------------------------- batch change banner

function BatchChangeBanner({ change }: { change: HomeBatchChange }) {
  const t = useT();
  const respond = useApiMutation((response: "Agreed" | "Declined") => deliveryApi.respondToChange(change.change_id, { response }), {
    success: t("answerRecorded"),
    invalidate: [
      ["me", "home"],
      ["delivery", "my-material-changes"],
    ],
  });
  return (
    <section aria-label={t("batchChangeTitle")} className="rounded-xl border border-warning/40 bg-warning-soft p-4">
      <h2 className="font-semibold">{t("batchChangeTitle")}</h2>
      <dl className="mt-2 space-y-0.5 text-sm">
        <div>
          <dt className="inline text-muted-foreground">{t("batchNow")}: </dt>
          <dd className="inline">{change.current_plan ?? "—"}</dd>
        </div>
        <div>
          <dt className="inline text-muted-foreground">{t("batchProposed")}: </dt>
          <dd className="inline font-medium">{change.proposed_plan}</dd>
        </div>
        <div>
          <dt className="inline text-muted-foreground">{t("batchWhy")}: </dt>
          <dd className="inline">{change.reason}</dd>
        </div>
      </dl>
      {change.reply_by && <p className="mt-2 text-sm font-medium">{t("batchReplyBy", { when: fmtDate(change.reply_by) })}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        <ConfirmDialog
          title={t("agreeTitle")}
          consequence={t("agreeConsequence")}
          confirmLabel={t("agree")}
          cancelLabel={t("cancel")}
          onConfirm={() => respond.mutateAsync("Agreed")}
        >
          <Button className="tap">{t("agree")}</Button>
        </ConfirmDialog>
        <ConfirmDialog
          title={t("declineTitle")}
          consequence={t("declineConsequence")}
          confirmLabel={t("decline")}
          cancelLabel={t("cancel")}
          onConfirm={() => respond.mutateAsync("Declined")}
        >
          <Button variant="outline" className="tap">
            {t("decline")}
          </Button>
        </ConfirmDialog>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- the four cards

function HomeCard({ title, children }: { title: string; children: ReactNode }) {
  return <Section title={title}>{children}</Section>;
}

function DueWorkCard({ card }: { card: StudentHome["due_work"] }) {
  const t = useT();
  return (
    <HomeCard title={t("dueWork")}>
      {card.state === "Ready" ? (
        <div className="space-y-2">
          <p className="text-sm">
            {card.assignments > 0 && t("openAssignments", { n: card.assignments })}
            {card.assignments > 0 && card.tests > 0 && " · "}
            {card.tests > 0 && t("openTests", { n: card.tests })}
          </p>
          {card.nearest && (
            <p className="text-sm text-muted-foreground">
              {card.nearest.title} · {t("dueAt", { when: fmtDateTime(card.nearest.due_at) })}
            </p>
          )}
        </div>
      ) : card.state === "Empty" ? (
        <p className="text-sm text-muted-foreground">{t("nothingDue")}</p>
      ) : (
        <CardGap card={card} />
      )}
      <Link to="/tasks" className="tap mt-2 inline-flex items-center text-sm font-medium text-primary underline">
        {t("allWork")}
      </Link>
    </HomeCard>
  );
}

function ContinueCard({ card, progress }: { card: StudentHome["continue_learning"]; progress: StudentHome["course_progress"] }) {
  const t = useT();
  const pick = useLocalised();
  return (
    <HomeCard title={t("continueLearning")}>
      {card.state === "Ready" ? (
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">{pick(card.module.title, card.module.title_te)}</p>
          <p className="font-medium">{pick(card.topic.title, card.topic.title_te)}</p>
          <Button asChild size="sm" className="tap">
            <Link to="/topics/$topicId" params={{ topicId: String(card.topic.topic_id) }}>
              {t("openTopic")}
            </Link>
          </Button>
        </div>
      ) : (
        <CardGap card={card} />
      )}
      {progress.state !== "Unavailable" && "topics" in progress && progress.topics && progress.topics.total > 0 && (
        <div className="mt-3">
          <Meter value={progress.topics.percent} label={t("topicsDone", { done: progress.topics.done, total: progress.topics.total })} />
        </div>
      )}
    </HomeCard>
  );
}

function RecordingCard({ card }: { card: StudentHome["latest_recording"] }) {
  const t = useT();
  return (
    <HomeCard title={t("latestRecording")}>
      {card.state === "Ready" ? (
        <div className="space-y-2">
          <p className="text-sm">
            <span className="font-medium">{card.title}</span> · {fmtDate(card.class_date)}
          </p>
          <StatusBadge domain="recording" code={card.status} />
          <div>
            <Button asChild size="sm" variant="outline" className="tap">
              <Link to="/materials">{t("watchNow")}</Link>
            </Button>
          </div>
        </div>
      ) : card.state === "Empty" ? (
        <p className="text-sm text-muted-foreground">{t("recordingNone")}</p>
      ) : (
        <CardGap card={card} />
      )}
      <Link to="/materials" className="tap mt-2 inline-flex items-center text-sm font-medium text-primary underline">
        {t("allRecordings")}
      </Link>
    </HomeCard>
  );
}

function AttendanceCard({ card }: { card: StudentHome["attendance_alert"] }) {
  const t = useT();
  return (
    <HomeCard title={t("attendanceAlert")}>
      {card.state === "Ready" ? (
        card.latest_absence && !card.latest_absence.recovery && card.latest_absence.can_request_recovery ? (
          <div className="space-y-2">
            <StatusNote tone={card.alert ? "danger" : "warning"}>
              {t("attendanceMissed", { when: fmtDate(card.latest_absence.starts_at) })}
              {card.alert && ` ${t("attendanceLow", { n: card.alert_threshold })}`}
            </StatusNote>
            <Button asChild size="sm" className="tap">
              <Link to="/progress" search={{ tab: "attendance" }}>
                {t("askRecovery")}
              </Link>
            </Button>
          </div>
        ) : card.alert ? (
          <StatusNote tone="danger">{t("attendanceLow", { n: card.alert_threshold })}</StatusNote>
        ) : (
          <p className="text-sm text-muted-foreground">{t("attendanceOnTrack")}</p>
        )
      ) : card.state === "Empty" ? (
        <p className="text-sm text-muted-foreground">{t("attendanceNotStarted")}</p>
      ) : (
        <CardGap card={card} />
      )}
      <Link to="/progress" search={{ tab: "attendance" }} className="tap mt-2 inline-flex items-center text-sm font-medium text-primary underline">
        {t("seeAttendance")}
      </Link>
    </HomeCard>
  );
}

// ---------------------------------------------------------------- the screen

/** One tap from Home to the places a phone's bottom bar has no room for: Progress, Certificates, Support, and fees and receipts. */
function QuickLinks() {
  const t = useT();
  const links = [
    { to: "/progress", label: t("myProgress"), icon: TrendingUp },
    { to: "/certificates", label: t("certificates"), icon: Award },
    { to: "/support", label: t("support"), icon: LifeBuoy },
    { to: "/my-account", search: { tab: "fees" }, label: t("feesAndReceipts"), icon: Wallet },
  ] as const;
  return (
    <section aria-label={t("quickLinks")}>
      <h2 className="mb-2 text-base font-semibold">{t("quickLinks")}</h2>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {links.map(({ to, label, icon: Icon, ...rest }) => (
          <Link
            key={to}
            to={to}
            {...("search" in rest ? { search: rest.search } : {})}
            className="tap flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm hover:bg-accent"
          >
            <Icon className="size-4 shrink-0" aria-hidden /> {label}
          </Link>
        ))}
      </div>
    </section>
  );
}

export function StudentHome() {
  const query = useMyHome();
  const { lang } = useLanguage();
  const t = useT();
  return (
    <div className="mx-auto max-w-5xl">
      <QueryView query={query}>
        {(home) => (
          <>
            <PageHead
              title={lang === "te" ? `నమస్తే, ${home.student.name_te ?? home.student.full_name}` : `Welcome, ${home.student.full_name}`}
              description={`${home.student.student_code} · ${home.student.service_branch.branch_name}`}
            />
            <div className="space-y-4">
              <GettingStartedCard
                labels={{
                  title: t("gettingStarted"),
                  dismiss: t("dismiss"),
                  go: t("go"),
                  steps: { activate: t("stepActivate"), batch: t("stepBatch"), class: t("stepClass"), task: t("stepTask") },
                }}
              />
              {home.batch_changes.state === "Ready" && home.batch_changes.items.map((change) => <BatchChangeBanner key={change.change_id} change={change} />)}
              <UpNextHero up={home.up_next} />
              <QuickLinks />
              <div className="grid gap-4 md:grid-cols-2">
                <DueWorkCard card={home.due_work} />
                <ContinueCard card={home.continue_learning} progress={home.course_progress} />
                <RecordingCard card={home.latest_recording} />
                <AttendanceCard card={home.attendance_alert} />
              </div>
              {home.needs_batch && <SlotPreferenceCard />}
              {home.primary_enrolment === null && <EmptyState reason={t("noEnrolments")} />}
            </div>
          </>
        )}
      </QueryView>
    </div>
  );
}
