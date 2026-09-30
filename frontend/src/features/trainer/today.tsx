import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { dashboardKeys, dashboardsApi, useTrainerToday, type TodaySession, type TrainerToday } from "@/api/dashboards";
import { deliveryApi } from "@/api/delivery";
import { Grid, Note, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { CardGap, Tile } from "@/features/shared/dashboard-parts";
import { fmtDate, fmtDateTime, fmtRange } from "@/features/shared/format";
import { RegisterForm } from "@/features/trainer/attendance";
import { useApiMutation } from "@/lib/mutation";
import { cn } from "@/lib/utils";

const STEPS = ["Open today's session", "Join / Start Meet", "Record delivered topics", "Mark attendance", "Notes & closeout"] as const;

/** Where a session stands in the flow: from the class state, what is marked and whether notes exist. */
function stepOf(session: TodaySession, meetAcknowledged: boolean, attendanceAcknowledged: boolean): number {
  if (session.state === "Scheduled" || session.state === "Rescheduled") return 0;
  if (session.state === "Live") return meetAcknowledged ? 2 : 1;
  const a = session.attendance;
  if (a.seats > 0 && a.marked < a.seats && !attendanceAcknowledged) return 3;
  return session.notes ? 5 : 4;
}

function MeetStep({ session, onContinue }: { session: TodaySession; onContinue: () => void }) {
  const { meet } = session;
  return (
    <div className="space-y-2">
      {session.mode === "Classroom" ? (
        <p className="text-sm">Classroom session{session.room ? ` in ${session.room}` : ""} — no Meet needed.</p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {meet.link ? (
            <Button asChild>
              <a href={meet.link} target="_blank" rel="noreferrer">
                Join / Start Meet
              </a>
            </Button>
          ) : (
            <Button disabled>Join / Start Meet</Button>
          )}
          <StatusBadge>{meet.label}</StatusBadge>
          <span className="text-xs text-muted-foreground">
            {meet.link ? "Opens Google Meet as the branch organizer." : "The organizer link is not associated yet."}
            {meet.organizer_email && ` Meet organizer: ${meet.organizer_email}.`}
          </span>
        </div>
      )}
      <Button variant="outline" onClick={onContinue}>
        Continue (class started)
      </Button>
    </div>
  );
}

function NotesStep({ session, onSaved }: { session: TodaySession; onSaved: () => void }) {
  const [notes, setNotes] = useState(session.notes ?? "");
  const save = useApiMutation((value: string) => dashboardsApi.saveSessionNotes(session.session_id, value), {
    success: "Close-out saved. Recording mapping stays Pending Verification.",
    onSuccess: onSaved,
  });
  return (
    <div className="space-y-2">
      <label htmlFor={`notes-${session.session_id}`} className="block text-sm font-medium">
        Session notes
      </label>
      <Textarea id={`notes-${session.session_id}`} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
      <Button disabled={!notes.trim() || save.isPending} onClick={() => save.mutate(notes.trim())}>
        Close out session
      </Button>
    </div>
  );
}

function SessionFlow({ session }: { session: TodaySession }) {
  const queryClient = useQueryClient();
  const [meetAcknowledged, setMeetAcknowledged] = useState(false);
  const [attendanceAcknowledged, setAttendanceAcknowledged] = useState(false);
  const [topicChecked, setTopicChecked] = useState(false);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: dashboardKeys.today });
  const start = useApiMutation(() => deliveryApi.startSession(session.session_id), { success: "Session opened.", onSuccess: refresh });
  const deliver = useApiMutation(() => deliveryApi.deliverSession(session.session_id), { success: "Delivered topics saved.", onSuccess: refresh });
  const step = stepOf(session, meetAcknowledged, attendanceAcknowledged);

  return (
    <Section className="mt-6" title={`Today's flow — ${session.title}`}>
      <p className="mb-3 text-sm text-muted-foreground">
        {fmtDate(session.starts_at)} · {fmtRange(session.starts_at, session.ends_at)} · <span className="font-mono text-xs">{session.batch.batch_code}</span> ·{" "}
        {session.mode}
        {session.room ? ` · ${session.room}` : ""} <StatusBadge>{session.state}</StatusBadge>
      </p>
      <ol className="mb-4 grid gap-2 sm:grid-cols-5" aria-label="Session flow">
        {STEPS.map((label, i) => (
          <li
            key={label}
            aria-current={i === step ? "step" : undefined}
            className={cn("rounded-lg border p-2 text-sm", i === step && "border-primary bg-accent font-semibold", i < step && "bg-success-soft")}
          >
            <span className="text-xs">{i < step ? "✓ Done" : `Step ${i + 1}`}</span>
            <br />
            {label}
          </li>
        ))}
      </ol>

      {step === 0 && (
        <div className="space-y-1">
          <Button disabled={start.isPending} onClick={() => start.mutate(undefined)}>
            Open session
          </Button>
          <p className="text-xs text-muted-foreground">A class can be opened up to 60 minutes before it begins.</p>
        </div>
      )}
      {step === 1 && <MeetStep session={session} onContinue={() => setMeetAcknowledged(true)} />}
      {step === 2 && (
        <fieldset>
          <legend className="mb-2 text-sm font-medium">Topics delivered in this actual Class Session</legend>
          {session.topic ? (
            <label className="tap flex items-center gap-2 text-sm">
              <input type="checkbox" checked={topicChecked} onChange={(e) => setTopicChecked(e.target.checked)} />
              {session.topic.title}
            </label>
          ) : (
            <p className="text-sm text-muted-foreground">This class has no curriculum topic attached. Saving records that the class was taught.</p>
          )}
          <Button className="mt-2" disabled={(session.topic !== null && !topicChecked) || deliver.isPending} onClick={() => deliver.mutate(undefined)}>
            Save delivered topics
          </Button>
        </fieldset>
      )}
      {step === 3 && (
        <div className="space-y-2">
          <p className="text-sm">
            Mark attendance below ({session.attendance.marked} of {session.attendance.seats} marked), or open the{" "}
            <Link to="/trainer/attendance" className="text-primary underline">
              attendance register
            </Link>
            .
          </p>
          <RegisterForm sessionId={session.session_id} onSaved={refresh} />
          <Button variant="outline" onClick={() => setAttendanceAcknowledged(true)}>
            Continue to notes (attendance not complete)
          </Button>
        </div>
      )}
      {step === 4 && <NotesStep session={session} onSaved={refresh} />}
      {step === 5 && (
        <StatusNote state="Saved">
          Session closed out. Recording mapping: {session.recording.mapping}.
          {session.notes && <span className="mt-1 block text-xs">Notes: {session.notes}</span>}
        </StatusNote>
      )}
    </Section>
  );
}

function Tiles({ tiles }: { tiles: TrainerToday["tiles"] }) {
  const { sessions, reviews, support_flags: flags } = tiles;
  return (
    <Grid cols={3}>
      <Tile
        rank={1}
        label="Assigned sessions scheduled"
        value={sessions.state === "Ready" ? sessions.count : "Unavailable"}
        hint={
          sessions.state === "Ready" ? (
            `Next ${sessions.window_days} days${sessions.next_starts_at ? ` · next ${fmtDateTime(sessions.next_starts_at)}` : ""}`
          ) : (
            <CardGap card={sessions} />
          )
        }
      />
      <Tile
        rank={2}
        label="Submissions awaiting my review"
        value={reviews.state === "Ready" ? reviews.count : "Unavailable"}
        hint={
          reviews.state !== "Ready" ? (
            <CardGap card={reviews} />
          ) : reviews.oldest_age_days === null ? (
            "Nothing waiting"
          ) : (
            <>
              Oldest: {reviews.oldest_age_days} day{reviews.oldest_age_days === 1 ? "" : "s"} ·{" "}
              <Link to="/trainer/reviews" className="text-primary underline">
                Open reviews
              </Link>
            </>
          )
        }
      />
      <Tile
        rank={3}
        label="Assigned students with open support flags"
        value={flags.state === "Ready" ? flags.count : "Unavailable"}
        hint={
          flags.state === "Ready" ? (
            <>
              of {flags.assigned_students} assigned ·{" "}
              <Link to="/trainer/support" className="text-primary underline">
                Open support
              </Link>
            </>
          ) : (
            <CardGap card={flags} />
          )
        }
      />
    </Grid>
  );
}

export function TrainerToday() {
  const query = useTrainerToday();
  return (
    <div className="mx-auto max-w-6xl">
      <PageHead title="Today" description="Trainer · scope: assigned batches & students only" />
      <QueryView query={query}>
        {(data) => (
          <>
            <Tiles tiles={data.tiles} />
            {data.today.state === "Ready" ? (
              data.today.sessions.map((session) => <SessionFlow key={session.session_id} session={session} />)
            ) : (
              <div className="mt-6">
                {data.today.state === "Empty" ? <StatusNote state="Empty">No assigned session scheduled today.</StatusNote> : <CardGap card={data.today} />}
              </div>
            )}
            <div className="mt-4">
              <Note>{data.scope_note}</Note>
            </div>
          </>
        )}
      </QueryView>
    </div>
  );
}
