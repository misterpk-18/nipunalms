/** What the student schedule and the class page share: a ticking clock, the day groups, the countdown and the Join button. */
import { useEffect, useState } from "react";
import type { ClassSession } from "@/api/delivery";
import { Button } from "@/components/ui/button";
import { fmtTime } from "@/features/shared/delivery-ui";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/** The Join button shows this long before a class starts (the API opens joining at the same time). */
export const JOIN_OPENS_MINUTES = 15;
/** A countdown ("Starts in 2 h") replaces the clock time when a class is this close. */
const COUNTDOWN_HOURS = 24;

type T = ReturnType<typeof useT>;

/** The current time in ms, refreshed every `every` ms so countdowns and the Join button stay right without a reload. */
export function useNow(every = 30_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), every);
    return () => window.clearInterval(timer);
  }, [every]);
  return now;
}

const dayKey = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" });

/** Whole IST calendar days from today to the day of `iso`: 0 today, 1 tomorrow, negative in the past. */
export function daysFromToday(iso: string, now: number): number {
  const day = (ms: number) => Date.parse(`${dayKey.format(new Date(ms))}T00:00:00Z`);
  return Math.round((day(Date.parse(iso)) - day(now)) / 86_400_000);
}

export type DayGroup = "today" | "tomorrow" | "week" | "later";

/** Today / Tomorrow / This week (the next five days) / Later. A class still running past its end counts as today. */
export function dayGroup(session: Pick<ClassSession, "starts_at" | "state">, now: number): DayGroup {
  const days = session.state === "Live" ? 0 : daysFromToday(session.starts_at, now);
  return days <= 0 ? "today" : days === 1 ? "tomorrow" : days <= 6 ? "week" : "later";
}

/** "2 h", "1 h 30 min", "25 min". */
export function durationText(t: T, ms: number): string {
  const minutes = Math.max(Math.ceil(ms / 60_000), 1);
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return t("unitMinutes", { n: m });
  return m === 0 ? t("unitHours", { n: h }) : `${t("unitHours", { n: h })} ${t("unitMinutes", { n: m })}`;
}

/** "Live now", "Starts in 2 h" (within a day) or "Starts 10:00"; null once the class is over. */
export function startsText(t: T, session: Pick<ClassSession, "starts_at" | "ends_at" | "state">, now: number): string | null {
  if (session.state === "Live") return t("liveNow");
  const start = Date.parse(session.starts_at);
  if (now > Date.parse(session.ends_at)) return null;
  if (now >= start) return t("liveNow");
  return start - now <= COUNTDOWN_HOURS * 3_600_000 ? t("startsIn", { when: durationText(t, start - now) }) : t("startsAtTime", { time: fmtTime(session.starts_at) });
}

/** The Join Class button. Hidden until it opens, 15 minutes before the class; highlighted while the class is live. */
export function JoinButton({ session }: { session: ClassSession }) {
  const t = useT();
  const now = useNow();
  if (session.mode === "Classroom") {
    return <p className="text-sm text-muted-foreground">{session.room ? t("inPersonAt", { room: session.room }) : t("inPerson")}</p>;
  }
  if (session.state === "Cancelled" || session.state === "Delivered") return null;
  const live = session.state === "Live";
  const start = Date.parse(session.starts_at);
  if (!live && now > Date.parse(session.ends_at)) return null;
  if (!live && now < start - JOIN_OPENS_MINUTES * 60_000) {
    return (
      <p className="text-sm text-muted-foreground">{t("joinNotReady")}</p>
    );
  }
  const url = session.join?.enabled ? session.join.url : null;
  if (url) {
    return (
      <Button asChild size="lg" className={cn("tap", live && "shadow-md ring-2 ring-primary ring-offset-2")}>
        <a href={url} target="_blank" rel="noreferrer">
          {live ? t("joinNow") : t("joinClass")}
        </a>
      </Button>
    );
  }
  return (
    <div>
      <Button disabled>{t("joinClass")}</Button>
      <p className="mt-1 text-xs text-muted-foreground">{t("joinWaitingLink")}</p>
    </div>
  );
}
