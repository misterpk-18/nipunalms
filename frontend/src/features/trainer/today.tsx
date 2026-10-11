import { useState } from "react";
import { Link, useSearch } from "@tanstack/react-router";
import { useClassFlow, useTrainerToday, type CompactSession, type TodaySession, type TrainerToday } from "@/api/dashboards";
import { EmptyState } from "@/components/lms/empty-state";
import { GettingStartedCard } from "@/components/lms/getting-started";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { NeedsYouList, type NeedsYouItem } from "@/components/lms/needs-you-list";
import { PageHead, QueryView, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { ClassFlow, FinishedClass } from "@/features/trainer/class-flow";
import { fmtDate, fmtRange } from "@/features/shared/format";
import { cn } from "@/lib/utils";

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** A class in a plain list: when, what, which batch and its state. */
function CompactRow({ session }: { session: CompactSession }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-2.5">
      <div className="min-w-0">
        <p className="text-sm font-medium">
          {fmtRange(session.starts_at, session.ends_at)} · {session.title}
        </p>
        <p className="text-xs text-muted-foreground">
          {session.batch.batch_code} · {session.mode}
          {session.room ? ` · ${session.room}` : ""}
          {session.topic ? ` · ${session.topic.title}` : ""}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <StatusBadge domain="session" code={session.state} />
      </div>
    </li>
  );
}

function OtherClasses({ sessions }: { sessions: TodaySession[] }) {
  if (sessions.length === 0) return null;
  return (
    <section aria-label="Later today" className="rounded-xl border bg-card p-4 shadow-sm sm:p-5">
      <h2 className="mb-1 text-base font-semibold">Also today</h2>
      <ul className="divide-y">
        {sessions.map((s) => (
          <li key={s.session_id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
            <div className="min-w-0">
              <p className="text-sm font-medium">
                {fmtRange(s.starts_at, s.ends_at)} · {s.title}
              </p>
              <p className="text-xs text-muted-foreground">
                {s.batch.batch_code} · {s.mode}
                {s.room ? ` · ${s.room}` : ""}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge domain="session" code={s.state} />
              <Button asChild size="sm" variant="outline">
                <Link to="/trainer" search={{ session: s.session_id }}>
                  Open class
                </Link>
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function FinishedClasses({ sessions }: { sessions: TodaySession[] }) {
  const [openId, setOpenId] = useState<number | null>(null);
  if (sessions.length === 0) return null;
  return (
    <details className="rounded-xl border bg-card p-4 shadow-sm sm:p-5">
      <summary className="cursor-pointer text-base font-semibold">Finished today ({sessions.length})</summary>
      <ul className="mt-2 divide-y">
        {sessions.map((s) => (
          <li key={s.session_id} className="py-2.5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium">
                  {fmtRange(s.starts_at, s.ends_at)} · {s.title}
                </p>
                <p className="text-xs text-muted-foreground">
                  {s.batch.batch_code} · attendance {s.attendance.marked} of {s.attendance.seats} marked
                </p>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge domain="session" code={s.state} />
                <Button
                  size="sm"
                  variant="outline"
                  aria-expanded={openId === s.session_id}
                  onClick={() => setOpenId(openId === s.session_id ? null : s.session_id)}
                >
                  {openId === s.session_id ? "Hide" : "View"}
                </Button>
              </div>
            </div>
            {openId === s.session_id && (
              <div className="mt-3">
                <FinishedClass session={s} />
              </div>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}

function Tomorrow({ tomorrow }: { tomorrow: Extract<TrainerToday["tomorrow"], { sessions: CompactSession[] }> }) {
  return (
    <section aria-label="Tomorrow" className="rounded-xl border bg-card p-4 shadow-sm sm:p-5">
      <h2 className="mb-1 text-base font-semibold">Tomorrow · {fmtDate(tomorrow.date)}</h2>
      {tomorrow.sessions.length === 0 ? (
        <p className="text-sm text-muted-foreground">No class is scheduled for tomorrow either.</p>
      ) : (
        <ul className="divide-y">
          {tomorrow.sessions.map((s) => (
            <CompactRow key={s.session_id} session={s} />
          ))}
        </ul>
      )}
    </section>
  );
}

function todoItems(todo: Extract<TrainerToday["todo"], { assignments: number }>): NeedsYouItem[] {
  const items: NeedsYouItem[] = [];
  for (const session of todo.class_logs.sessions)
    items.push({
      id: `log-${session.session_id}`,
      what: `Class log missing: ${session.title}`,
      where: `${session.batch.batch_code} · ${fmtDate(session.starts_at)}`,
      to: "/trainer",
      search: { session: session.session_id },
      action: "Add class log",
    });
  if (todo.class_logs.count > todo.class_logs.sessions.length)
    items.push({
      id: "log-more",
      what: `${plural(todo.class_logs.count - todo.class_logs.sessions.length, "more class")} without a log`,
      to: "/trainer/sessions",
      search: {},
      action: "Open Sessions",
    });
  if (todo.assignments > 0)
    items.push({ id: "assignments", what: `${plural(todo.assignments, "assignment")} to review`, to: "/trainer/to-grade", action: "Grade" });
  if (todo.attempts > 0)
    items.push({
      id: "attempts",
      what: `${plural(todo.attempts, "test attempt")} to mark`,
      to: "/trainer/to-grade",
      action: "Grade",
    });
  const { classes, corrections, recoveries } = todo.attendance;
  if (classes > 0)
    items.push({
      id: "attendance",
      what: `Attendance is not complete for ${plural(classes, "class", "classes")}`,
      to: "/trainer/attendance",
      action: "Mark attendance",
    });
  if (corrections > 0)
    items.push({
      id: "corrections",
      what: `${plural(corrections, "attendance correction")} waiting for a decision`,
      to: "/trainer/attendance",
      action: "See corrections",
    });
  if (recoveries > 0)
    items.push({
      id: "recoveries",
      what: `${plural(recoveries, "recovery", "recoveries")} for you to check`,
      to: "/trainer/attendance",
      action: "Check recoveries",
    });
  return items;
}

function Todo({ todo }: { todo: TrainerToday["todo"] }) {
  if (!("assignments" in todo)) return <StatusNote tone="warning">The to-do list could not be loaded just now.</StatusNote>;
  return (
    <NeedsYouList
      title="To do"
      items={todoItems(todo)}
      empty="You are all caught up: no work to review, no missing class logs and no attendance left to mark."
    />
  );
}

/** The class the trainer is working on: today's next-up class, or the one opened with `?session=`. */
function Focus({ session, nextUp, today }: { session: number | undefined; nextUp: number | null; today: TodaySession[] }) {
  const focusId = session ?? nextUp;
  const inList = today.find((s) => s.session_id === focusId);
  // A class that is not one of today's (Run class from Sessions, or a missing log from an earlier day)
  const extra = useClassFlow(focusId !== null && !inList ? focusId : null);
  if (focusId === null) return null;
  const focused = inList ?? extra.data;
  if (!focused)
    return (
      <QueryView query={extra} skeleton="detail">
        {() => null}
      </QueryView>
    );
  const label = !inList ? "Opened from your list" : focused.state === "Live" ? "On now" : focusId === nextUp ? "Next up" : "Class";
  return (
    <>
      {!inList && session && (
        <p className="text-sm">
          <Link to="/trainer" className="text-primary underline">
            Back to today
          </Link>
        </p>
      )}
      <ClassFlow key={focused.session_id} session={focused} label={label} />
    </>
  );
}

export function TrainerToday() {
  const { session } = useSearch({ from: "/trainer/" });
  const query = useTrainerToday();
  return (
    <div className={cn("mx-auto max-w-4xl")}>
      <PageHead title="Today" description="Run today's classes and see what needs you." />
      <div className="mb-4">
        <GettingStartedCard workspace="trainer" />
      </div>
      <QueryView query={query} skeleton="detail">
        {(data) => {
          const ready = data.today.state === "Ready" ? data.today : null;
          const sessions = ready?.sessions ?? [];
          const focusId = session ?? ready?.next_up ?? null;
          const others = sessions.filter((s) => s.session_id !== focusId && s.state !== "Delivered");
          const finished = sessions.filter((s) => s.session_id !== focusId && s.state === "Delivered");
          const tomorrow = data.tomorrow && "sessions" in data.tomorrow ? data.tomorrow : null;
          return (
            <div className="space-y-4">
              {data.today.state === "Unavailable" && (
                <StatusNote tone="warning">Today's classes could not be loaded just now. Try again in a moment.</StatusNote>
              )}
              {data.today.state === "Empty" && !session && (
                <EmptyState
                  reason="No class is scheduled for you today."
                  action={
                    <Button asChild size="sm" variant="outline">
                      <Link to="/trainer/sessions">See your schedule</Link>
                    </Button>
                  }
                />
              )}
              <Focus session={session} nextUp={ready?.next_up ?? null} today={sessions} />
              <OtherClasses sessions={others} />
              <FinishedClasses sessions={finished} />
              {tomorrow && !session && <Tomorrow tomorrow={tomorrow} />}
              <Todo todo={data.todo} />
              <HowThisWorks>
                <p>
                  Today is where you run a class: start it, join the meeting, mark attendance and save the class log. Your place is kept, so you can refresh or
                  switch device and carry on.
                </p>
                <p>{data.scope_note}</p>
              </HowThisWorks>
            </div>
          );
        }}
      </QueryView>
    </div>
  );
}
