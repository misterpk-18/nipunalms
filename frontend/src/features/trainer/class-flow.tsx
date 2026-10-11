/**
 * Today's guided class flow, the only way a trainer runs a class: Start class → Join → Attendance → Class log.
 * Where the trainer is, and what they have typed in the class log, are kept on the server (`PUT /class-sessions/{id}/flow`),
 * so a refresh, or another device, picks up at the same step.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { attendanceKeys } from "@/api/attendance";
import { dashboardKeys, dashboardsApi, type ClassLogDraft, type ClassOutcome, type FlowStep, type TodaySession } from "@/api/dashboards";
import { deliveryApi } from "@/api/delivery";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { StepBar } from "@/components/lms/step-bar";
import { StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RegisterForm } from "@/features/trainer/attendance";
import { fmtDate, fmtRange } from "@/features/shared/format";
import { fmtTime } from "@/features/shared/delivery-ui";
import { fromIstInput, toIstInput } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";
import { cn } from "@/lib/utils";

const STEP_LABEL: Record<FlowStep, string> = { open: "Start class", join: "Join", attendance: "Attendance", log: "Class log" };
const OUTCOME_LABEL: Record<ClassOutcome, string> = { Held: "Held in full", "Partially Held": "Partly held" };

/** Refresh everything a class change touches: Today, the single-class view, the schedule, the badges and the registers. */
function useRefresh() {
  const queryClient = useQueryClient();
  return useCallback(async () => {
    await Promise.all(
      [dashboardKeys.today, ["trainer", "flow"], ["delivery"], ["nav"], attendanceKeys.all].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
    );
  }, [queryClient]);
}

/** The class log being typed: held here (not in the step) so it survives moving between steps, and saved to the server a moment after each change. */
function useDraft(session: TodaySession) {
  const [draft, setDraft] = useState<ClassLogDraft>(session.flow.draft);
  const pending = useRef<ClassLogDraft>({});
  const timer = useRef<number | undefined>(undefined);
  const id = session.session_id;
  const flush = useCallback(async () => {
    window.clearTimeout(timer.current);
    const body = pending.current;
    pending.current = {};
    if (Object.keys(body).length > 0) await dashboardsApi.saveClassFlow(id, { draft: body }).catch(() => undefined);
  }, [id]);
  const patch = (change: ClassLogDraft) => {
    setDraft((d) => ({ ...d, ...change }));
    pending.current = { ...pending.current, ...change };
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void flush(), 600);
  };
  useEffect(() => () => void flush(), [flush]);
  /** After the class is logged: whatever was still waiting to be saved is no longer wanted. */
  const discard = () => {
    window.clearTimeout(timer.current);
    pending.current = {};
  };
  return { draft, patch, flush, discard };
}

// ---------------------------------------------------------------- the steps

function OpenStep({ session, onStarted }: { session: TodaySession; onStarted: () => void }) {
  const start = useApiMutation(() => deliveryApi.startSession(session.session_id), {
    success: "Class started.",
    next: "Join the meeting, then mark attendance.",
    onSuccess: onStarted,
  });
  const { flow } = session;
  return (
    <div className="space-y-3">
      <p className="text-sm">Starting the class opens attendance and tells the system the class is on.</p>
      {flow.awaiting_approval && <StatusNote tone="warning">Your Branch Manager has not approved this class yet. You can start it once they have.</StatusNote>}
      <div className="flex flex-wrap items-center gap-3">
        <Button disabled={!flow.can_start || start.isPending} onClick={() => start.mutate(undefined)}>
          Start class
        </Button>
        {!flow.can_start && !flow.awaiting_approval && (
          <span className="text-sm text-muted-foreground">You can start from {fmtTime(flow.start_opens_at)} IST, an hour before the class.</span>
        )}
      </div>
    </div>
  );
}

function JoinStep({ session, onContinue, busy }: { session: TodaySession; onContinue: () => void; busy: boolean }) {
  const refresh = useRefresh();
  const ask = useApiMutation(() => dashboardsApi.askForMeetLink(session.session_id), {
    success: "Your Branch Manager has been asked for a link.",
    next: "You can carry on with the class meanwhile.",
    onSuccess: () => void refresh(),
  });
  const { meet } = session;
  return (
    <div className="space-y-3">
      {session.mode === "Classroom" ? (
        <p className="text-sm">Classroom class{session.room ? ` in ${session.room}` : ""}. There is no meeting to join.</p>
      ) : (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            {meet.link ? (
              <Button asChild>
                <a href={meet.link} target="_blank" rel="noreferrer">
                  Join Google Meet
                </a>
              </Button>
            ) : (
              <Button disabled>Join Google Meet</Button>
            )}
            <StatusBadge domain="meet" code={meet.status} label={meet.label} />
          </div>
          {!meet.link && (
            <StatusNote tone="warning" title="There is no Meet link for this class yet.">
              {meet.link_requested_at ? (
                <>Your Branch Manager was asked at {fmtTime(meet.link_requested_at)} IST. You can carry on with the class without it.</>
              ) : (
                <div className="flex flex-wrap items-center gap-3">
                  <span>Ask your Branch Manager to set one. You can carry on meanwhile.</span>
                  <Button size="sm" variant="outline" disabled={ask.isPending} onClick={() => ask.mutate(undefined)}>
                    Ask Branch Manager
                  </Button>
                </div>
              )}
            </StatusNote>
          )}
          {meet.link && meet.organizer_email && <p className="text-xs text-muted-foreground">The meeting is organised by {meet.organizer_email}.</p>}
        </div>
      )}
      <Button variant={meet.link || session.mode === "Classroom" ? "default" : "outline"} disabled={busy} onClick={onContinue}>
        Continue to attendance
      </Button>
    </div>
  );
}

function AttendanceStep({ session, onBack, onContinue, busy }: { session: TodaySession; onBack: () => void; onContinue: () => void; busy: boolean }) {
  const refresh = useRefresh();
  const left = session.attendance.not_yet_marked;
  return (
    <div className="space-y-3">
      <RegisterForm sessionId={session.session_id} heading={false} onSaved={() => void refresh()} />
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" disabled={busy} onClick={onBack}>
          Back
        </Button>
        <Button disabled={busy} onClick={onContinue}>
          Continue to class log
        </Button>
        {left > 0 && <span className="text-sm text-muted-foreground">{left} not marked yet. You can come back to this step before you finish.</span>}
      </div>
    </div>
  );
}

function minutesBetween(start: string, end: string, breaks: number): number {
  return Math.round((new Date(end).getTime() - new Date(start).getTime()) / 60000) - breaks;
}

function LogStep({
  session,
  draft,
  patch,
  flush,
  onBack,
  onFinished,
}: {
  session: TodaySession;
  draft: ClassLogDraft;
  patch: (change: ClassLogDraft) => void;
  flush: () => Promise<void>;
  onBack: () => void;
  onFinished: () => void;
}) {
  const late = !session.flow.steps.includes("open");
  // What the form shows before the trainer changes anything: from when the class was started to its end (or now, when finishing early)
  const defaults = useMemo(() => {
    const start = session.live_at ?? session.starts_at;
    const end = Math.max(Math.min(Date.now(), new Date(session.ends_at).getTime()), new Date(start).getTime() + 60_000);
    return { start: toIstInput(start), end: toIstInput(new Date(late ? session.ends_at : end).toISOString()) };
  }, [session.live_at, session.starts_at, session.ends_at, late]);

  const outcome: ClassOutcome = draft.outcome ?? "Held";
  const start = draft.actual_start ? toIstInput(draft.actual_start) : defaults.start;
  const end = draft.actual_end ? toIstInput(draft.actual_end) : defaults.end;
  const breaks = draft.break_minutes ?? 0;
  const topicIds = draft.topic_ids ?? (session.topic ? [session.topic.topic_id] : []);
  const minutes = minutesBetween(fromIstInput(start), fromIstInput(end), breaks);
  const notDelivered = (draft.unfulfilled_note ?? "").trim();

  const problems: string[] = [];
  if (!start || !end || minutes + breaks <= 0) problems.push("The class must end after it started.");
  else if (minutes < 0) problems.push("The break is longer than the class.");
  else if (new Date(fromIstInput(end)).getTime() > Date.now() + 5 * 60_000) problems.push("The end time cannot be in the future.");
  if (outcome === "Partially Held" && !notDelivered) problems.push("Say what was not covered.");

  const finish = useApiMutation(
    () =>
      deliveryApi.deliverSession(session.session_id, {
        outcome,
        actual_start: fromIstInput(start),
        actual_end: fromIstInput(end),
        break_minutes: breaks,
        ...(outcome === "Partially Held" ? { unfulfilled_note: notDelivered } : {}),
        topic_ids: topicIds,
        ...(draft.notes?.trim() ? { notes: draft.notes.trim() } : {}),
      }),
    {
      success: "Class log saved.",
      next: session.attendance.not_yet_marked > 0 ? "Some students are still not marked. Mark them from this class." : "The class now counts as taught.",
      onSuccess: onFinished,
    },
  );

  const modules = useMemo(() => {
    const groups = new Map<string, typeof session.flow.topic_options>();
    for (const option of session.flow.topic_options) groups.set(option.module, [...(groups.get(option.module) ?? []), option]);
    return [...groups.entries()];
  }, [session.flow.topic_options]);

  const toggle = (id: number, on: boolean) => patch({ topic_ids: on ? [...topicIds, id] : topicIds.filter((t) => t !== id) });
  const label = "text-sm font-medium";
  const fieldId = (name: string) => `log-${session.session_id}-${name}`;

  return (
    <div className="space-y-5">
      {late && <StatusNote tone="info">This class is over and has no log yet. Save the class log first; you can mark attendance straight after.</StatusNote>}
      <fieldset>
        <legend className={label}>How did the class go?</legend>
        <div className="mt-2 flex flex-wrap gap-2" role="radiogroup" aria-label="Outcome">
          {(Object.keys(OUTCOME_LABEL) as ClassOutcome[]).map((value) => (
            <label
              key={value}
              className={cn(
                "tap flex cursor-pointer items-center gap-2 rounded-lg border px-4 text-sm",
                outcome === value && "border-primary bg-accent font-semibold",
              )}
            >
              <input type="radio" className="sr-only" name={fieldId("outcome")} checked={outcome === value} onChange={() => patch({ outcome: value })} />
              {outcome === value ? "✓ " : ""}
              {OUTCOME_LABEL[value]}
            </label>
          ))}
        </div>
      </fieldset>

      {outcome === "Partially Held" && (
        <div className="space-y-1.5">
          <Label htmlFor={fieldId("unfulfilled")} className={label}>
            What was not covered
          </Label>
          <Textarea
            id={fieldId("unfulfilled")}
            rows={2}
            value={draft.unfulfilled_note ?? ""}
            onChange={(e) => patch({ unfulfilled_note: e.target.value })}
            onBlur={() => void flush()}
            placeholder="For example: ran out of time before the exercises"
          />
          <p className="text-xs text-muted-foreground">Your Branch Manager is told, so a make-up class can be planned.</p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor={fieldId("start")} className={label}>
            Started at (IST)
          </Label>
          <Input
            id={fieldId("start")}
            type="datetime-local"
            value={start}
            onChange={(e) => e.target.value && patch({ actual_start: fromIstInput(e.target.value) })}
            onBlur={() => void flush()}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={fieldId("end")} className={label}>
            Ended at (IST)
          </Label>
          <Input
            id={fieldId("end")}
            type="datetime-local"
            value={end}
            onChange={(e) => e.target.value && patch({ actual_end: fromIstInput(e.target.value) })}
            onBlur={() => void flush()}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={fieldId("break")} className={label}>
            Break (minutes)
          </Label>
          <Input
            id={fieldId("break")}
            type="number"
            min={0}
            max={600}
            value={breaks}
            onChange={(e) => patch({ break_minutes: Math.max(0, Math.min(600, Number(e.target.value) || 0)) })}
            onBlur={() => void flush()}
          />
        </div>
      </div>
      {problems.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {minutes} {minutes === 1 ? "minute" : "minutes"} taught of{" "}
          {session.log?.planned_minutes ?? Math.round((new Date(session.ends_at).getTime() - new Date(session.starts_at).getTime()) / 60000)} planned.
        </p>
      )}

      <fieldset>
        <legend className={label}>Topics covered</legend>
        {modules.length === 0 ? (
          <p className="mt-1 text-sm text-muted-foreground">No topics are set up for this batch yet. Say what you covered in the notes.</p>
        ) : (
          <div className="mt-2 max-h-64 space-y-3 overflow-y-auto rounded-lg border p-3">
            {modules.map(([module, options]) => (
              <div key={module}>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{module}</p>
                <ul className="space-y-1">
                  {options.map((option) => (
                    <li key={option.topic_id}>
                      <label className="tap flex cursor-pointer items-center gap-2 text-sm">
                        <input type="checkbox" checked={topicIds.includes(option.topic_id)} onChange={(e) => toggle(option.topic_id, e.target.checked)} />
                        {option.title}
                        {session.topic?.topic_id === option.topic_id && <Tag tone="info">Planned</Tag>}
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </fieldset>

      <div className="space-y-1.5">
        <Label htmlFor={fieldId("notes")} className={label}>
          Notes <span className="font-normal text-muted-foreground">(optional)</span>
        </Label>
        <Textarea
          id={fieldId("notes")}
          rows={3}
          value={draft.notes ?? ""}
          onChange={(e) => patch({ notes: e.target.value })}
          onBlur={() => void flush()}
          placeholder="Anything the next class, or your Branch Manager, should know"
        />
      </div>

      <div className="rounded-lg bg-muted/60 p-3 text-sm">
        Attendance: {session.attendance.marked} of {session.attendance.seats} students marked.
        {session.attendance.not_yet_marked > 0 && !late && (
          <>
            {" "}
            <button type="button" className="text-primary underline" onClick={() => void flush().then(onBack)}>
              Go back to mark the rest
            </button>
            .
          </>
        )}
      </div>

      {problems.length > 0 && <StatusNote tone="warning">{problems.join(" ")}</StatusNote>}
      <div className="flex flex-wrap items-center gap-3">
        {!late && (
          <Button variant="outline" onClick={() => void flush().then(onBack)}>
            Back
          </Button>
        )}
        <ConfirmDialog
          title="Save the class log?"
          consequence={`This class will count as taught (${Math.max(minutes, 0)} minutes, ${OUTCOME_LABEL[outcome].toLowerCase()}). You can still mark or correct attendance afterwards.`}
          confirmLabel="Save class log"
          onConfirm={() => finish.mutateAsync(undefined).catch(() => undefined)}
        >
          <Button disabled={problems.length > 0 || finish.isPending}>Finish class</Button>
        </ConfirmDialog>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- a finished class

/** What was saved for a class that is logged, with the attendance still to do. */
export function FinishedClass({ session }: { session: TodaySession }) {
  const refresh = useRefresh();
  const [marking, setMarking] = useState(false);
  const { log, attendance } = session;
  return (
    <div className="space-y-3">
      <StatusNote tone="success">
        <span className="font-medium">{log?.outcome ? OUTCOME_LABEL[log.outcome] : "Held"}</span>
        {log?.delivered_minutes != null && ` · ${log.delivered_minutes} of ${log.planned_minutes} minutes`}
        {log?.break_minutes ? ` · ${log.break_minutes} minute break` : ""}
        {log?.actual_start && log.actual_end ? ` · ${fmtRange(log.actual_start, log.actual_end)}` : ""}
      </StatusNote>
      {log?.unfulfilled_note && <p className="text-sm">Not covered: {log.unfulfilled_note}</p>}
      {log && log.topics.length > 0 && (
        <p className="text-sm">
          <span className="font-medium">Topics covered:</span> {log.topics.map((t) => t.title).join(", ")}
        </p>
      )}
      {session.notes && <p className="text-sm text-muted-foreground">Notes: {session.notes}</p>}
      <p className="text-sm">Recording: {session.recording.mapping === "Mapped" ? "matched to this class" : "not matched to this class yet"}.</p>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm">
          Attendance: {attendance.marked} of {attendance.seats} students marked.
        </span>
        <Button size="sm" variant={attendance.not_yet_marked > 0 ? "default" : "outline"} onClick={() => setMarking((v) => !v)}>
          {marking ? "Hide the register" : attendance.not_yet_marked > 0 ? "Mark attendance" : "Open the register"}
        </Button>
      </div>
      {marking && <RegisterForm sessionId={session.session_id} heading={false} onSaved={() => void refresh()} />}
    </div>
  );
}

// ---------------------------------------------------------------- the flow

/** One class, expanded: its steps, the current one open. */
export function ClassFlow({ session, label }: { session: TodaySession; label?: string }) {
  const refresh = useRefresh();
  const { draft, patch, flush, discard } = useDraft(session);
  const { flow } = session;
  const move = useApiMutation((step: FlowStep) => dashboardsApi.saveClassFlow(session.session_id, { step }), { onSuccess: () => void refresh() });
  const finished = flow.steps.length === 0 || flow.step === null;
  const go = (step: FlowStep) => void flush().then(() => move.mutate(step));
  const stepIndex = flow.step ? flow.steps.indexOf(flow.step) : -1;

  return (
    <section aria-label={`Class: ${session.title}`} className="rounded-xl border bg-card p-4 shadow-sm sm:p-5">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          {label && <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-primary">{label}</p>}
          <h2 className="text-lg font-semibold">{session.title}</h2>
          <p className="text-sm text-muted-foreground">
            {fmtDate(session.starts_at)} · {fmtRange(session.starts_at, session.ends_at)} ·{" "}
            <span className="font-mono text-xs">{session.batch.batch_code}</span> · {session.mode}
            {session.room ? ` · ${session.room}` : ""}
            {session.topic ? ` · ${session.topic.title}` : ""}
          </p>
        </div>
        <StatusBadge domain="session" code={session.state} />
      </div>

      {finished ? (
        <FinishedClass session={session} />
      ) : (
        <>
          {flow.steps.length > 1 && (
            <div className="mb-4">
              <StepBar steps={flow.steps.map((step, i) => ({ label: STEP_LABEL[step], done: i < stepIndex }))} />
            </div>
          )}
          {flow.step === "open" && <OpenStep session={session} onStarted={() => void refresh()} />}
          {flow.step === "join" && <JoinStep session={session} busy={move.isPending} onContinue={() => go("attendance")} />}
          {flow.step === "attendance" && <AttendanceStep session={session} busy={move.isPending} onBack={() => go("join")} onContinue={() => go("log")} />}
          {flow.step === "log" && (
            <LogStep
              session={session}
              draft={draft}
              patch={patch}
              flush={flush}
              onBack={() => go("attendance")}
              onFinished={() => {
                discard();
                void refresh();
              }}
            />
          )}
        </>
      )}
      {!finished && (
        <p className="mt-4 text-xs text-muted-foreground">
          Need a different time or day?{" "}
          <Link to="/trainer/sessions" className="text-primary underline">
            Ask for a reschedule from Sessions
          </Link>
          .
        </p>
      )}
    </section>
  );
}
