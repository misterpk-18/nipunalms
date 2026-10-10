import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { assessmentsApi, type MyWork, type WorkAction, type WorkItem, type WorkSection } from "@/api/assessments";
import { EmptyState } from "@/components/lms/empty-state";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, PillTabs, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { fmtDateTime } from "@/features/shared/format";
import { useT, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const TABS: readonly WorkSection[] = ["todo", "waiting", "done"];

const ACTION_KEY: Record<WorkAction, TranslationKey> = {
  Submit: "submit",
  Resubmit: "actionResubmit",
  "Start test": "actionStartTest",
  "Resume test": "actionResumeTest",
  "Try again": "actionTryAgain",
  "Book a slot": "actionBookSlot",
  View: "actionView",
};

type T = ReturnType<typeof useT>;

/** The one line about timing: when it is due, when it opens, or when the interview is. */
function whenLine(item: WorkItem, t: T): string | null {
  if (item.state_domain === "slot" && item.due_at) return t("interviewAt", { when: fmtDateTime(item.due_at) });
  if (item.section === "todo") {
    if (item.state === "Scheduled" && item.opens_at) return t("opensAt", { when: fmtDateTime(item.opens_at) });
    if (item.due_at) return item.overdue ? t("overdueSince", { when: fmtDateTime(item.due_at) }) : item.kind === "test" ? t("closesAt", { when: fmtDateTime(item.due_at) }) : t("dueAt", { when: fmtDateTime(item.due_at) });
  }
  return null;
}

function attemptsLine(item: WorkItem, t: T): string | null {
  if (item.kind !== "test" || item.section !== "todo" || item.attempts_remaining === null) return null;
  return item.attempts_remaining === 1 ? t("attemptLeftOne") : t("attemptsLeft", { n: item.attempts_remaining });
}

function WorkRow({ item }: { item: WorkItem }) {
  const t = useT();
  const to = item.kind === "assignment" ? { to: "/assignments/$id" as const } : { to: "/tests/$id" as const };
  const params = { id: String(item.id) };
  const details = [
    item.topic?.title ?? item.module?.title,
    whenLine(item, t),
    item.duration_minutes ? t("unitMinutes", { n: item.duration_minutes }) : null,
    attemptsLine(item, t),
    item.marks !== null && item.max_marks !== null ? t(item.kind === "test" ? "scoreLine" : "marksLine", { marks: item.marks, max: item.max_marks }) : null,
  ].filter(Boolean);
  const primary = item.section === "todo" && item.action !== "View";

  return (
    <li className={cn("flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-4 shadow-sm", item.overdue && "border-l-4 border-l-destructive")}>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap gap-2">
          <Tag>{item.kind === "assignment" ? t("typeAssignment") : t("typeTest")}</Tag>
          <Tag tone={item.is_required ? "info" : "neutral"}>{item.is_required ? t("required") : t("optional")}</Tag>
          <StatusBadge domain={item.state_domain} code={item.state} />
          {item.late && <Tag tone="warning">{t("submittedLate")}</Tag>}
        </div>
        <Link {...to} params={params} className="mt-2 block font-semibold text-primary underline">
          {item.title}
        </Link>
        {details.length > 0 && <p className={cn("mt-0.5 text-sm text-muted-foreground", item.overdue && "text-destructive")}>{details.join(" · ")}</p>}
      </div>
      <Button asChild variant={primary ? "default" : "outline"} className="tap shrink-0">
        <Link {...to} params={params}>
          {t(ACTION_KEY[item.action])}
        </Link>
      </Button>
    </li>
  );
}

function Empty({ section }: { section: WorkSection }) {
  const t = useT();
  if (section === "todo")
    return (
      <EmptyState
        reason={t("emptyTodo")}
        action={
          <Button asChild variant="outline">
            <Link to="/my-courses">{t("goMyLearning")}</Link>
          </Button>
        }
      />
    );
  return <EmptyState reason={section === "waiting" ? t("emptyWaiting") : t("emptyDone")} />;
}

function WorkTabs({ work }: { work: MyWork }) {
  const t = useT();
  const [picked, setPicked] = useState<WorkSection | null>(null);
  // Open on what needs the student: to do, else what is waiting, else what is done.
  const tab = picked ?? (work.counts.todo ? "todo" : work.counts.waiting ? "waiting" : "done");
  const rows = work[tab];
  const labels: Record<WorkSection, string> = { todo: t("tabTodo"), waiting: t("tabWaiting"), done: t("tabDone") };
  return (
    <>
      <PillTabs tabs={TABS} value={tab} onChange={setPicked} label={t("workViews")} counts={work.counts} labels={labels} />
      {tab === "todo" && work.counts.overdue > 0 && (
        <p className="mb-3 text-sm font-medium text-destructive" role="status">
          {t("overdueCount", { n: work.counts.overdue })}
        </p>
      )}
      {rows.length === 0 ? (
        <Empty section={tab} />
      ) : (
        <ul className="space-y-3">
          {rows.map((item) => (
            <WorkRow key={`${item.kind}-${item.id}`} item={item} />
          ))}
        </ul>
      )}
    </>
  );
}

/** Tasks & Tests: assignments and tests on one screen, what to do first. */
export function Tasks() {
  const t = useT();
  const query = useQuery({ queryKey: ["work", "mine"], queryFn: assessmentsApi.myWork });
  return (
    <div className="mx-auto max-w-4xl">
      <PageHead title={t("tasksAndTests")} description={t("tasksHelp")} />
      <QueryView query={query} skeleton="cards">
        {(work) => <WorkTabs work={work} />}
      </QueryView>
      <div className="mt-6">
        <HowThisWorks title={t("howMarksWork")}>
          <p>{t("howMarksText1")}</p>
          <p>{t("howMarksText2")}</p>
        </HowThisWorks>
      </div>
    </div>
  );
}
