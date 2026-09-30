import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { useMyHome, type StudentHome } from "@/api/dashboards";
import { Grid, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Meter } from "@/features/shared/attendance-parts";
import { CardGap, Tile } from "@/features/shared/dashboard-parts";
import { fmtDate, fmtDateTime, fmtRange } from "@/features/shared/format";
import { useLanguage, useT } from "@/lib/i18n";

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

function NextClassTile({ card }: { card: StudentHome["next_class"] }) {
  const t = useT();
  if (card.state !== "Ready") return <Tile rank={1} label={t("nextClass")} value="Nothing scheduled" hint={<CardGap card={card} />} />;
  return (
    <Tile
      rank={1}
      label={t("nextClass")}
      value={card.title}
      hint={`${fmtDate(card.starts_at)} · ${fmtRange(card.starts_at, card.ends_at)} · ${card.mode} · Trainer ${card.trainer.full_name}`}
    />
  );
}

function DueWorkTile({ card }: { card: StudentHome["due_work"] }) {
  const t = useT();
  if (card.state === "Unavailable") return <Tile rank={2} label={t("dueWork")} value="Unavailable" hint={<CardGap card={card} />} />;
  if (card.state !== "Ready") return <Tile rank={2} label={t("dueWork")} value="Nothing due" hint={card.message} />;
  const value = card.required_assignments > 0 ? plural(card.required_assignments, "required assignment") : plural(card.assignments, "assignment");
  return (
    <Tile
      rank={2}
      label={t("dueWork")}
      value={card.assignments > 0 ? value : plural(card.tests, "test")}
      hint={
        <>
          {card.nearest && `${card.nearest.title} · due ${fmtDateTime(card.nearest.due_at)}`}
          {card.nearest && card.tests > 0 && " · "}
          {card.assignments > 0 && card.tests > 0 && plural(card.tests, "open test")}
        </>
      }
    />
  );
}

function ProgressTile({ card }: { card: StudentHome["course_progress"] }) {
  const t = useT();
  return (
    <Tile rank={3} label={t("courseProgress")}>
      <div className="mt-2 space-y-2">
        {card.state === "Ready" ? (
          <Meter value={card.percent} label={`Curriculum delivered (${card.enrolment.course.course_code})`} />
        ) : (
          <CardGap card={card} />
        )}
        <p className="text-xs text-muted-foreground">Separate from attendance and required learning — see Progress.</p>
      </div>
    </Tile>
  );
}

function JoinClass({ card }: { card: StudentHome["next_class"] }) {
  const t = useT();
  if (card.state !== "Ready") return null;
  const { join } = card;
  return (
    <div className="mt-2 space-y-1">
      {join.enabled && join.url ? (
        <Button asChild>
          <a href={join.url} target="_blank" rel="noreferrer">
            {t("joinClass")}
          </a>
        </Button>
      ) : (
        <Button disabled>{t("joinClass")}</Button>
      )}
      <p className="text-xs text-muted-foreground">
        {card.mode === "Classroom"
          ? join.reason
          : `${join.reason ?? ""} Join Class opens Google Meet in production${card.organizer_email ? `. Meet organizer: ${card.organizer_email}` : ""} — ${card.meet_status_label}.`}
      </p>
    </div>
  );
}

function HomeCard({ title, className, children }: { title: string; className?: string; children: ReactNode }) {
  return (
    <Section title={title} className={className}>
      {children}
    </Section>
  );
}

function Cards({ home }: { home: StudentHome }) {
  const t = useT();
  const cl = home.continue_learning;
  const rec = home.latest_recording;
  const up = home.upcoming_work;
  const att = home.attendance_alert;
  const cert = home.certificate;
  const career = home.career;
  const support = home.support;
  const ai = home.ask_nipuna;
  return (
    <div className="mt-6 grid gap-4 lg:grid-cols-3">
      <HomeCard title={t("continueLearning")} className="lg:col-span-2">
        {cl.state === "Ready" ? (
          <p className="text-sm">
            {cl.track ? `${cl.track.track_name} → ` : ""}
            {cl.module.title} →{" "}
            <Link to="/topics/$topicId" params={{ topicId: String(cl.topic.topic_id) }} className="text-primary underline">
              {cl.topic.title}
            </Link>
            <span className="ml-2 text-xs text-muted-foreground">({cl.basis})</span>
          </p>
        ) : (
          <CardGap card={cl} />
        )}
      </HomeCard>
      <HomeCard title={t("latestRecording")}>
        {rec.state === "Ready" ? (
          <>
            <p className="text-sm">
              <Link to="/recordings" className="text-primary underline">
                {rec.title}
              </Link>{" "}
              · {fmtDate(rec.class_date)}
            </p>
            <div className="mt-2">
              <StatusBadge>{rec.status}</StatusBadge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {rec.access_until ? `Access until ${fmtDate(rec.access_until)}` : "Access window pending — set once your Joining Date is confirmed"}
            </p>
          </>
        ) : (
          <CardGap card={rec} />
        )}
      </HomeCard>
      <HomeCard title={t("upcomingWork")}>
        {up.state === "Ready" ? (
          <>
            <p className="text-sm">
              {up.title} · {up.closes_at ? `closes ${fmtDate(up.closes_at)}` : up.opens_at ? `opens ${fmtDate(up.opens_at)}` : up.status}
            </p>
            <Link to="/tests" className="text-sm text-primary underline">
              {t("viewAll")}
            </Link>
          </>
        ) : (
          <CardGap card={up} />
        )}
      </HomeCard>
      <HomeCard title={t("attendanceAlert")}>
        {att.state === "Ready" ? (
          att.latest_absence ? (
            <StatusNote state={att.latest_absence.recovery ? "Pending Verification" : att.alert ? "Error" : "Not Submitted"}>
              {att.latest_absence.recovery
                ? `Absence on ${fmtDate(att.latest_absence.starts_at)} has a recovery reference (${att.latest_absence.recovery.recovery_code}, ${att.latest_absence.recovery.status}).`
                : `Absence on ${fmtDate(att.latest_absence.starts_at)} has no recovery request yet.`}
              {att.alert && ` Attendance is below ${att.alert_threshold}%.`}
            </StatusNote>
          ) : att.alert ? (
            <StatusNote state="Error">Attendance is below {att.alert_threshold}%.</StatusNote>
          ) : (
            <p className="text-sm text-muted-foreground">No absence to recover. Attendance is on track.</p>
          )
        ) : (
          <CardGap card={att} />
        )}
      </HomeCard>
      <HomeCard title={t("certStatus")}>
        {cert.state === "Ready" ? (
          <>
            <StatusBadge>{cert.status}</StatusBadge>
            <p className="mt-1 text-xs text-muted-foreground">From LMS Certificate Register.</p>
          </>
        ) : (
          <CardGap card={cert} />
        )}
      </HomeCard>
      <HomeCard title={t("careerSupport")}>
        {career.state === "Ready" ? (
          <>
            <p className="text-sm">{career.opted_in ? `Opted in · Profile ${career.profile_percent}% complete` : "Not opted in yet"}</p>
            <p className="mt-1 text-xs">{t("noGuarantee")}</p>
          </>
        ) : (
          <CardGap card={career} />
        )}
      </HomeCard>
      <HomeCard title={t("support")}>
        {support.state === "Ready" ? (
          <p className="text-sm">
            {plural(support.open_count, "open request")} · Owner: {support.requests[0]?.owner}
          </p>
        ) : support.state === "Empty" ? (
          <p className="text-sm text-muted-foreground">No open request.</p>
        ) : (
          <CardGap card={support} />
        )}
        <Link to="/support" className="text-sm text-primary underline">
          {t("raiseRequest")}
        </Link>
      </HomeCard>
      <HomeCard title={t("askNipuna")}>
        {ai.state === "Ready" ? (
          <>
            <StatusBadge>{ai.mode === "ai" ? ai.status : `${ai.status} (rule-based)`}</StatusBadge>
            <p className="mt-1 text-xs text-muted-foreground">
              {ai.used} of {ai.limit} daily responses used (IST).
            </p>
          </>
        ) : (
          <CardGap card={ai} />
        )}
      </HomeCard>
    </div>
  );
}

function Freshness({ engagement }: { engagement: StudentHome["engagement"] }) {
  if (engagement.state === "Stale") return <StatusNote state="Stale">{engagement.message} Shown as Stale rather than as zero.</StatusNote>;
  if (engagement.state === "Fresh") return <StatusNote state="Saved">Engagement data last refreshed {fmtDateTime(engagement.refreshed_at)}.</StatusNote>;
  if (engagement.state === "Unavailable") return <StatusNote state="Error">{engagement.message ?? "Engagement data could not be loaded."}</StatusNote>;
  return <StatusNote state="Empty">{engagement.message}</StatusNote>;
}

export function StudentHome() {
  const query = useMyHome();
  const { lang } = useLanguage();
  return (
    <div className="mx-auto max-w-6xl">
      <QueryView query={query}>
        {(home) => (
          <>
            <PageHead
              title={lang === "te" ? `నమస్తే, ${home.student.name_te ?? home.student.full_name}` : `Welcome, ${home.student.full_name}`}
              description={`${home.student.student_code} · Service branch: ${home.student.service_branch.branch_name}`}
            />
            <Grid cols={3}>
              <NextClassTile card={home.next_class} />
              <DueWorkTile card={home.due_work} />
              <ProgressTile card={home.course_progress} />
            </Grid>
            <JoinClass card={home.next_class} />
            <Cards home={home} />
            <div className="mt-6">
              <Freshness engagement={home.engagement} />
            </div>
          </>
        )}
      </QueryView>
    </div>
  );
}
