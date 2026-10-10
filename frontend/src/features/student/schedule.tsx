import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { deliveryApi, type ClassSession } from "@/api/delivery";
import { NativeSelect } from "@/components/lms/forms";
import { PageHead, PillTabs, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { fmtDate, fmtTime, mono } from "@/features/shared/delivery-ui";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { JoinButton, dayGroup, startsText, useNow, type DayGroup } from "./class-time";

type View = "coming" | "past";
const VIEWS: readonly View[] = ["coming", "past"];
const GROUPS: readonly DayGroup[] = ["today", "tomorrow", "week", "later"];

type T = ReturnType<typeof useT>;

const groupLabel = (t: T, group: DayGroup) => ({ today: t("groupToday"), tomorrow: t("groupTomorrow"), week: t("groupThisWeek"), later: t("groupLater") })[group];

/** "Mon, 12 Oct" without the year, for the groups that span several days. */
const shortDate = (iso: string) => fmtDate(iso).replace(/,? \d{4}$/, "");

/** Live now, Starts in 2 h, Starts 10:00, Cancelled, Moved: one plain state per class. */
function StateChips({ session, now }: { session: ClassSession; now: number }) {
  const t = useT();
  if (session.state === "Cancelled") return <StatusBadge domain="session" code="Cancelled" />;
  const text = startsText(t, session, now);
  const live = session.state === "Live" || (now >= Date.parse(session.starts_at) && now <= Date.parse(session.ends_at));
  return (
    <>
      {session.state === "Rescheduled" && <StatusBadge domain="session" code="Rescheduled" />}
      {text && <Tag tone={live ? "success" : "info"}>{text}</Tag>}
      {session.mode !== "Classroom" && session.meet_status !== "Linked" && <StatusBadge domain="meet" code={session.meet_status_label} />}
    </>
  );
}

function ComingRow({ session, group, now }: { session: ClassSession; group: DayGroup; now: number }) {
  const t = useT();
  const live = session.state === "Live";
  return (
    <li className={cn("rounded-xl border bg-card p-4 shadow-sm", live && "border-primary bg-primary/5", session.state === "Cancelled" && "opacity-80")}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-primary">
            {(group === "week" || group === "later") && `${shortDate(session.starts_at)} · `}
            {fmtTime(session.starts_at)}–{fmtTime(session.ends_at)} IST
          </p>
          <Link to="/sessions/$sessionId" params={{ sessionId: String(session.session_id) }} className="font-semibold underline">
            {session.title}
          </Link>
          <p className="text-sm text-muted-foreground">
            {session.mode} · {session.trainer.full_name} · {session.branch.branch_name} · {mono(session.batch.batch_code)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StateChips session={session} now={now} />
        </div>
      </div>
      <div className="mt-3">
        {session.state === "Cancelled" ? <p className="text-sm text-muted-foreground">{t("cancelledNote")}</p> : <JoinButton session={session} />}
      </div>
    </li>
  );
}

function Coming({ sessions }: { sessions: ClassSession[] }) {
  const t = useT();
  const now = useNow();
  const grouped = useMemo(() => {
    const map = new Map<DayGroup, ClassSession[]>();
    for (const s of sessions) map.set(dayGroup(s, now), [...(map.get(dayGroup(s, now)) ?? []), s]);
    return map;
  }, [sessions, now]);
  return (
    <div className="space-y-6">
      {GROUPS.filter((g) => grouped.has(g)).map((g) => (
        <section key={g} aria-label={groupLabel(t, g)}>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            {groupLabel(t, g)}
            {(g === "today" || g === "tomorrow") && ` · ${shortDate(grouped.get(g)![0]!.starts_at)}`}
          </h2>
          <ul className="space-y-3">
            {grouped.get(g)!.map((s) => (
              <ComingRow key={s.session_id} session={s} group={g} now={now} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function PastRow({ session }: { session: ClassSession }) {
  const t = useT();
  const recording = session.recording;
  return (
    <li className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-primary">
            {fmtDate(session.starts_at)} · {fmtTime(session.starts_at)}–{fmtTime(session.ends_at)} IST
          </p>
          <Link to="/sessions/$sessionId" params={{ sessionId: String(session.session_id) }} className="font-semibold underline">
            {session.title}
          </Link>
          <p className="text-sm text-muted-foreground">
            {session.mode} · {session.trainer.full_name} · {mono(session.batch.batch_code)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {session.state === "Delivered" || session.state === "Cancelled" ? (
            <StatusBadge domain="session" code={session.state_label} />
          ) : (
            <Tag>{t("classNotRecorded")}</Tag>
          )}
          {session.attendance ? <StatusBadge domain="attendance" code={session.attendance} /> : session.state === "Delivered" && <Tag>{t("notMarkedYet")}</Tag>}
        </div>
      </div>
      {session.state !== "Cancelled" && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {recording?.playable ? (
            <Button asChild size="sm" variant="outline">
              <Link to="/materials">{t("watchNow")}</Link>
            </Button>
          ) : recording ? (
            <StatusBadge domain="recording" code={recording.status} />
          ) : (
            <span className="text-sm text-muted-foreground">{t("noRecordingShort")}</span>
          )}
        </div>
      )}
    </li>
  );
}

export function Schedule() {
  const t = useT();
  const [view, setView] = useState<View>("coming");
  const [course, setCourse] = useState("");
  const courses = useQuery({ queryKey: ["delivery", "my-enrolments"], queryFn: deliveryApi.myEnrolments });
  const query = useQuery({
    queryKey: ["delivery", "my-schedule", view, course],
    queryFn: () => deliveryApi.mySchedule({ course_id: course || undefined, past: view === "past" ? 1 : undefined }),
    // the Join link appears 15 minutes before a class: pick it up without a reload
    refetchInterval: view === "coming" ? 30_000 : false,
  });
  const options = [...new Map((courses.data ?? []).map((e) => [e.course.course_id, e.course])).values()].map((c) => ({
    value: c.course_id,
    label: `${c.course_code} — ${c.title}`,
  }));
  const labels: Record<View, string> = { coming: t("tabComing"), past: t("tabPast") };

  return (
    <div className="mx-auto max-w-4xl">
      <PageHead title={t("schedule")} description={t("scheduleHelp")} />
      <PillTabs tabs={VIEWS} value={view} onChange={setView} label={t("scheduleViews")} labels={labels} />
      {options.length > 1 && (
        <div className="mb-4 max-w-md">
          <NativeSelect aria-label={t("filterCourse")} placeholder={t("allCourses")} options={options} value={course} onChange={(e) => setCourse(e.target.value)} />
        </div>
      )}
      <QueryView
        query={query}
        skeleton="cards"
        isEmpty={(page) => page.data.length === 0}
        empty={view === "coming" ? t("noUpcoming") : t("noPast")}
        emptyAction={
          view === "coming" ? (
            <Button asChild variant="outline">
              <Link to="/my-courses">{t("goMyLearning")}</Link>
            </Button>
          ) : undefined
        }
      >
        {(page) => (view === "coming" ? <Coming sessions={page.data} /> : <ul className="space-y-3">{page.data.map((s) => <PastRow key={s.session_id} session={s} />)}</ul>)}
      </QueryView>
    </div>
  );
}
