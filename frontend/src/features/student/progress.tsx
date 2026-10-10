/** My Progress: Overview (what to do next and four separate measures), Attendance and Results. */
import { useState, type ReactNode } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { ArrowRight, CircleCheck } from "lucide-react";
import { useMyProgress, useNextSteps, type Measures, type NextStep, type ProgressBlock } from "@/api/attendance";
import { EmptyState } from "@/components/lms/empty-state";
import { Grid, PageHead, PillTabs, QueryView, Section, StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { fmtDate, fmtDateTime, percent } from "@/features/shared/format";
import { formatMoney } from "@/lib/format";
import { useT, type TranslationKey } from "@/lib/i18n";
import { AttendanceTab } from "./attendance";
import { ResultsTab } from "./results";

const TABS = ["overview", "attendance", "results"] as const;
type Tab = (typeof TABS)[number];
type T = ReturnType<typeof useT>;

// ---------------------------------------------------------------- what to do next

const WHAT: Record<string, TranslationKey> = { recordings: "whatRecordings", materials: "whatFiles", both: "whatBoth" };

/** One sentence and one button for each kind of step. The server sends the kind and the numbers; the words are here, so they translate. */
function describe(step: NextStep, t: T): { text: string; action: ReactNode } {
  const p = step.params;
  const course = step.course?.title ?? "";
  const go = (to: "/tasks" | "/finance" | "/certificates" | "/my-courses" | "/materials", label: string) => (
    <Button asChild size="sm" className="tap">
      <Link to={to}>
        {label}
        <ArrowRight aria-hidden />
      </Link>
    </Button>
  );
  const goTab = (tab: "attendance", label: string) => (
    <Button asChild size="sm" className="tap">
      <Link to="/progress" search={{ tab }}>
        {label}
        <ArrowRight aria-hidden />
      </Link>
    </Button>
  );
  switch (step.kind) {
    case "work_overdue":
      return { text: t("stepWorkOverdue", { n: Number(p["n"]) }), action: go("/tasks", t("tasksAndTests")) };
    case "work_todo":
      return { text: t("stepWorkTodo", { n: Number(p["n"]) }), action: go("/tasks", t("tasksAndTests")) };
    case "recovery":
      return {
        text:
          Number(p["n"]) === 1
            ? t("stepRecoveryOne", { session: String(p["session"]) })
            : t("stepRecoveryMany", { n: Number(p["n"]), session: String(p["session"]) }),
        action: goTab("attendance", t("requestRecovery")),
      };
    case "attendance_low":
      return {
        text: t("stepAttendanceLow", { percent: Number(p["percent"]), threshold: Number(p["threshold"]) }),
        action: goTab("attendance", t("attendance")),
      };
    case "access_ended":
    case "access_ending": {
      const what = t(WHAT[String(p["what"])] ?? "whatBoth");
      const label = p["can_request"] ? t("requestExtension") : t("classMaterials");
      const text =
        step.kind === "access_ended" ? t("stepAccessEnded", { what, course }) : t("stepAccessEnding", { what, course, date: fmtDate(String(p["until"])) });
      return { text, action: go("/materials", label) };
    }
    case "certificate_fee":
      return { text: t("stepCertFee", { course, balance: formatMoney(String(p["balance"])) }), action: go("/finance", t("finance")) };
    case "certificate_ready":
      return { text: t("stepCertReady", { course }), action: go("/certificates", t("certificates")) };
    case "topics_left":
      return { text: t("stepTopicsLeft", { n: Number(p["n"]), course }), action: go("/my-courses", t("myLearning")) };
    case "inactive":
      return { text: t("stepInactive", { days: Number(p["days"]) }), action: go("/my-courses", t("myLearning")) };
  }
}

function NextSteps() {
  const t = useT();
  const query = useNextSteps();
  return (
    <Section title={t("whatNext")}>
      <QueryView query={query} skeleton="cards">
        {(steps) =>
          steps.length === 0 ? (
            <EmptyState icon={CircleCheck} reason={t("allCaughtUp")} />
          ) : (
            <ol className="space-y-2">
              {steps.map((step, index) => {
                const { text, action } = describe(step, t);
                return (
                  <li
                    key={`${step.kind}-${step.course?.course_code ?? ""}-${index}`}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-card p-3"
                  >
                    <p className="min-w-0 flex-1 text-sm">{text}</p>
                    {action}
                  </li>
                );
              })}
            </ol>
          )
        }
      </QueryView>
    </Section>
  );
}

// ---------------------------------------------------------------- the four measures

function Meter({ value, label }: { value: number | null; label: string }) {
  const t = useT();
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-3xl font-semibold tabular-nums">{value === null ? "—" : `${Math.round(value)}%`}</span>
        <span className="text-right text-xs text-muted-foreground">{label}</span>
      </div>
      <div
        className="mt-2 h-2 overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={`${label}: ${value === null ? t("notYetCalculable") : `${Math.round(value)}%`}`}
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${value ?? 0}%` }} />
      </div>
    </div>
  );
}

const ENGAGEMENT: Record<Measures["engagement"]["level"], { key: TranslationKey; tone: "success" | "info" | "warning" | "neutral" }> = {
  High: { key: "engHigh", tone: "success" },
  Medium: { key: "engMedium", tone: "info" },
  Low: { key: "engLow", tone: "warning" },
  "Not started": { key: "engNone", tone: "neutral" },
};

function MeasureCards({ measures }: { measures: Measures }) {
  const t = useT();
  const { delivery, attendance, required_learning: learning, engagement } = measures;
  const level = ENGAGEMENT[engagement.level];
  return (
    <Grid cols={2}>
      <Section title={`1 · ${t("measureTaught")}`}>
        <Meter value={delivery.percent} label={t("taughtLine", { done: delivery.delivered_sessions, planned: delivery.planned_sessions })} />
        <p className="mt-2 text-xs text-muted-foreground">{t("taughtNote")}</p>
      </Section>
      <Section title={`2 · ${t("measureAttendance")}`}>
        {attendance.state === "Not started" ? (
          <EmptyState reason={t("attendanceNotStarted")} />
        ) : (
          <>
            <Meter value={attendance.percent} label={t("attendedLine", { n: attendance.present + attendance.late, marked: attendance.marked })} />
            <p className="mt-2 text-xs text-muted-foreground">
              {t("attendanceBreakdown", { p: attendance.present, l: attendance.late, a: attendance.absent, e: attendance.excused })}
              {attendance.recovered > 0 && ` · ${t("recoveredLine", { n: attendance.recovered })}`}
            </p>
            {attendance.state === "Partial Data" && (
              <div className="mt-2">
                <StatusNote tone="warning">{t("attendancePartial", { n: attendance.unmarked })}</StatusNote>
              </div>
            )}
            {attendance.alert && (
              <div className="mt-2">
                <StatusNote tone="danger">{t("attendanceAlertLine", { n: attendance.alert_threshold })}</StatusNote>
              </div>
            )}
          </>
        )}
      </Section>
      <Section title={`3 · ${t("measureRequired")}`}>
        <Meter value={learning.percent} label={t("requiredLine", { n: learning.covered_topics, total: learning.required_topics })} />
      </Section>
      <Section title={`4 · ${t("measureEngagement")}`}>
        <div className="flex items-center gap-2">
          <Tag tone={level.tone}>{t(level.key)}</Tag>
          <span className="text-sm text-muted-foreground">
            {t("engagementLine", { n: engagement.events_in_window, days: engagement.window_days, when: fmtDateTime(engagement.last_activity_at) })}
          </span>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">{t("infoOnly")}</p>
      </Section>
    </Grid>
  );
}

function CourseMeasures({ blocks }: { blocks: ProgressBlock[] }) {
  const t = useT();
  const [selected, setSelected] = useState<string | null>(null);
  const labels = blocks.map((b) => b.enrolment.course.course_code);
  const active = blocks.find((b) => b.enrolment.course.course_code === (selected ?? labels[0])) ?? blocks[0]!;
  return (
    <div className="space-y-4">
      {blocks.length > 1 && <PillTabs label={t("courseLabel")} tabs={labels} value={active.enrolment.course.course_code} onChange={setSelected} />}
      <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span>
          {active.enrolment.course.course_code} · {active.enrolment.course.title}
          {active.batch && ` · ${active.batch.batch_code}`}
        </span>
        <StatusBadge domain="enrolment" code={active.enrolment.status} />
      </p>
      <p className="text-sm text-muted-foreground">{t("fourMeasures")}</p>
      <MeasureCards measures={active} />
      <p className="text-sm text-muted-foreground">{t("completionNote")}</p>
    </div>
  );
}

function Overview() {
  const t = useT();
  const query = useMyProgress();
  return (
    <div className="space-y-6">
      <NextSteps />
      <QueryView query={query} skeleton="cards" isEmpty={(blocks) => blocks.length === 0} empty={t("noProgress")}>
        {(blocks) => <CourseMeasures blocks={blocks} />}
      </QueryView>
    </div>
  );
}

// ---------------------------------------------------------------- the screen

export function Progress() {
  const t = useT();
  const { tab = "overview" } = useSearch({ from: "/progress" });
  const navigate = useNavigate({ from: "/progress" });
  const labels: Record<Tab, string> = { overview: t("tabOverview"), attendance: t("attendance"), results: t("results") };
  return (
    <div className="mx-auto max-w-5xl">
      <PageHead title={t("myProgress")} description={t("progressHelp")} />
      <PillTabs
        tabs={TABS}
        value={tab}
        label={t("progressViews")}
        labels={labels}
        onChange={(next) => void navigate({ search: next === "overview" ? {} : { tab: next }, replace: true })}
      />
      {tab === "overview" && <Overview />}
      {tab === "attendance" && <AttendanceTab />}
      {tab === "results" && <ResultsTab />}
    </div>
  );
}
