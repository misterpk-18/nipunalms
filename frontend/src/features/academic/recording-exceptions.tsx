import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { list } from "@/api/client";
import { contentApi, formatDateTime, type Recording, type RecordingException } from "@/api/content";
import { DataTable, Note, PageHead, PillTabs, QueryView, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Field, NativeSelect } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";

const TABS = ["Exceptions", "Recordings"] as const;

export function AcademicRecordingExceptions() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Exceptions");
  return (
    <div className="mx-auto max-w-6xl">
      <PageHead
        title="Recording Exception Queue"
        description="Recordings that are partial, held, unavailable or blocked by an integration, each with a named owner."
      />
      <StatusNote state="Integration Unavailable">
        Google Drive and Meet are not connected yet: recordings are registered by hand and playback is not verified.
      </StatusNote>
      <div className="mt-4">
        <PillTabs label="Recording views" tabs={TABS} value={tab} onChange={setTab} />
        {tab === "Exceptions" ? <Exceptions /> : <Recordings />}
      </div>
    </div>
  );
}

function Exceptions() {
  const [status, setStatus] = useState("");
  const query = useQuery({ queryKey: ["recording-exceptions", status], queryFn: () => contentApi.exceptions({ status, per_page: 100 }) });
  const [resolving, setResolving] = useState<RecordingException | null>(null);
  const start = useApiMutation((id: number) => contentApi.startException(id), { success: "Exception taken on", invalidate: [["recording-exceptions"]] });
  return (
    <>
      <div className="mb-3 max-w-48">
        <NativeSelect
          aria-label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          placeholder="All statuses"
          options={["Open", "In Progress", "Resolved"].map((s) => ({ value: s, label: s }))}
        />
      </div>
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No recording exceptions.">
        {(page) => (
          <DataTable
            caption="Recording exceptions"
            rows={page.data}
            getKey={(e) => e.exception_id}
            cols={[
              { h: "ID", c: (e) => e.exception_code },
              {
                h: "Session",
                c: (e) => (
                  <>
                    <div>{e.session.title}</div>
                    <div className="font-mono text-xs text-muted-foreground">{e.session.session_code}</div>
                  </>
                ),
              },
              { h: "Batch", c: (e) => <span className="font-mono text-xs">{e.batch.batch_code}</span> },
              {
                h: "Issue",
                c: (e) => (
                  <>
                    {e.issue}
                    {e.resolution_note && <div className="text-xs text-muted-foreground">Resolved: {e.resolution_note}</div>}
                  </>
                ),
              },
              {
                h: "Status",
                c: (e) => (
                  <>
                    <StatusBadge>{e.issue_type}</StatusBadge> <StatusBadge>{e.status}</StatusBadge>
                    {e.escalation && (
                      <div className="mt-1 text-xs text-warning">
                        Escalation: {e.escalation} ({e.age_hours} h)
                      </div>
                    )}
                  </>
                ),
              },
              { h: "Owner", c: (e) => e.owner_user?.full_name ?? e.owner },
              {
                h: "Action",
                c: (e) =>
                  e.status === "Resolved" ? null : (
                    <div className="flex flex-wrap gap-2">
                      {e.status === "Open" && (
                        <Button size="sm" variant="outline" onClick={() => start.mutate(e.exception_id)}>
                          Start
                        </Button>
                      )}
                      <Button size="sm" variant="outline" onClick={() => setResolving(e)}>
                        Resolve
                      </Button>
                    </div>
                  ),
              },
            ]}
          />
        )}
      </QueryView>
      {resolving && <ResolveDialog exception={resolving} onClose={() => setResolving(null)} />}
    </>
  );
}

function ResolveDialog({ exception, onClose }: { exception: RecordingException; onClose: () => void }) {
  const [note, setNote] = useState("");
  const resolve = useApiMutation(() => contentApi.resolveException(exception.exception_id, note.trim()), {
    success: "Exception resolved",
    invalidate: [["recording-exceptions"]],
    onSuccess: onClose,
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Resolve {exception.exception_code}</DialogTitle>
          <DialogDescription>{exception.issue}</DialogDescription>
        </DialogHeader>
        <Field label="Resolution note" htmlFor="resolution-note">
          <Textarea
            id="resolution-note"
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="What was done, and where the student can now watch it"
          />
        </Field>
        <DialogFooter>
          <Button disabled={!note.trim() || resolve.isPending} onClick={() => resolve.mutate()}>
            Resolve
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type RecordingAction = { recording: Recording; mode: "hold" | "partial" | "unavailable" | "media" };

function Recordings() {
  const query = useQuery({ queryKey: ["recordings", "staff"], queryFn: () => contentApi.staffRecordings({ per_page: 100 }) });
  const [acting, setActing] = useState<RecordingAction | null>(null);
  const [registering, setRegistering] = useState(false);
  const release = useApiMutation((id: number) => contentApi.recordingAction(id, "release"), {
    success: "Recording released to the batch",
    invalidate: [["recordings"], ["recording-exceptions"]],
  });
  return (
    <>
      <div className="mb-3 flex justify-end">
        <Button variant="outline" onClick={() => setRegistering(true)}>
          Register recording
        </Button>
      </div>
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No recordings registered yet.">
        {(page) => (
          <DataTable
            caption="Recordings"
            rows={page.data}
            getKey={(r) => r.recording_id}
            cols={[
              { h: "Recording", c: (r) => `${r.recording_code}${r.part_no > 1 ? ` · part ${r.part_no}` : ""}` },
              {
                h: "Session",
                c: (r) => (
                  <>
                    <div>{r.session.title}</div>
                    <div className="text-xs text-muted-foreground">
                      {r.session.session_code} · {formatDateTime(r.session.starts_at)}
                    </div>
                  </>
                ),
              },
              { h: "Batch", c: (r) => <span className="font-mono text-xs">{r.session.batch.batch_code}</span> },
              {
                h: "Status",
                c: (r) => (
                  <>
                    <StatusBadge>{r.status}</StatusBadge>
                    <div className="text-xs text-muted-foreground">
                      {r.hold_reason ?? r.partial_note ?? (r.media_ref ? `${r.source} · ${r.media_ref}` : "No media reference")}
                    </div>
                  </>
                ),
              },
              {
                h: "Action",
                c: (r) => (
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="ghost" onClick={() => setActing({ recording: r, mode: "media" })}>
                      Media
                    </Button>
                    {r.status !== "Released" && r.status !== "Expired" && (
                      <Button size="sm" onClick={() => release.mutate(r.recording_id)}>
                        Release
                      </Button>
                    )}
                    {r.status !== "Held" && (
                      <Button size="sm" variant="outline" onClick={() => setActing({ recording: r, mode: "hold" })}>
                        Hold
                      </Button>
                    )}
                    {r.status !== "Partial" && (
                      <Button size="sm" variant="outline" onClick={() => setActing({ recording: r, mode: "partial" })}>
                        Mark partial
                      </Button>
                    )}
                    {r.status !== "Unavailable" && (
                      <Button size="sm" variant="ghost" onClick={() => setActing({ recording: r, mode: "unavailable" })}>
                        Unavailable
                      </Button>
                    )}
                  </div>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <div className="mt-4">
        <Note>
          Students see a recording only for sessions of batches they are allocated to, until their access window closes. Hold and partial marks raise an
          exception automatically.
        </Note>
      </div>
      {acting && <ActionDialog {...acting} onClose={() => setActing(null)} />}
      {registering && <RegisterDialog onClose={() => setRegistering(false)} />}
    </>
  );
}

const ACTION_TEXT = {
  hold: { title: "Hold recording", label: "Reason for the hold", action: "Hold", field: "reason" },
  partial: { title: "Mark recording partial", label: "What was and was not captured", action: "Mark partial", field: "note" },
  unavailable: { title: "Mark recording unavailable", label: "Reason", action: "Mark unavailable", field: "reason" },
} as const;

function ActionDialog({ recording, mode, onClose }: RecordingAction & { onClose: () => void }) {
  const [text, setText] = useState("");
  const [mediaRef, setMediaRef] = useState(recording.media_ref ?? "");
  const [duration, setDuration] = useState(recording.duration_minutes ? String(recording.duration_minutes) : "");
  const [download, setDownload] = useState(recording.download_allowed);
  const done = { invalidate: [["recordings"], ["recording-exceptions"]], onSuccess: onClose };
  const act = useApiMutation((body: Record<string, unknown>) => contentApi.recordingAction(recording.recording_id, mode as "hold", body), {
    success: "Recording updated",
    ...done,
  });
  const media = useApiMutation((body: Record<string, unknown>) => contentApi.updateRecording(recording.recording_id, body), {
    success: "Media details saved",
    ...done,
  });

  if (mode === "media") {
    return (
      <Dialog open onOpenChange={(open) => !open && onClose()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Media for {recording.recording_code}</DialogTitle>
            <DialogDescription>Record where the media lives. A stable Drive file id is stored, never a public link.</DialogDescription>
          </DialogHeader>
          <Field label="Drive file reference" htmlFor="media-ref">
            <Input id="media-ref" value={mediaRef} onChange={(e) => setMediaRef(e.target.value)} />
          </Field>
          <Field label="Duration (minutes)" htmlFor="media-duration">
            <Input id="media-duration" inputMode="numeric" value={duration} onChange={(e) => setDuration(e.target.value)} />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={download} onChange={(e) => setDownload(e.target.checked)} /> Download permitted (documented exception only)
          </label>
          <DialogFooter>
            <Button
              disabled={media.isPending}
              onClick={() =>
                media.mutate({ media_ref: mediaRef.trim() || null, duration_minutes: duration ? Number(duration) : null, download_allowed: download })
              }
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }
  const copy = ACTION_TEXT[mode];
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{copy.title}</DialogTitle>
          <DialogDescription>
            {recording.session.title} · {recording.recording_code}
          </DialogDescription>
        </DialogHeader>
        <Field label={copy.label} htmlFor="action-text">
          <Textarea id="action-text" rows={3} value={text} onChange={(e) => setText(e.target.value)} />
        </Field>
        <DialogFooter>
          <Button disabled={!text.trim() || act.isPending} onClick={() => act.mutate({ [copy.field]: text.trim() })}>
            {copy.action}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function RegisterDialog({ onClose }: { onClose: () => void }) {
  const sessions = useQuery({
    queryKey: ["class-sessions", "delivered"],
    queryFn: () => list<{ session_id: number; session_code: string; title: string; state: string }>("/class-sessions", { per_page: 100 }),
  });
  const [sessionId, setSessionId] = useState("");
  const [mediaRef, setMediaRef] = useState("");
  const [duration, setDuration] = useState("");
  const register = useApiMutation((body: Record<string, unknown>) => contentApi.registerRecording(body), {
    success: "Recording registered",
    invalidate: [["recordings"]],
    onSuccess: onClose,
  });
  const delivered = (sessions.data?.data ?? []).filter((s) => s.state === "Delivered" || s.state === "Live");
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Register recording</DialogTitle>
          <DialogDescription>A recording must belong to an actual, delivered class session.</DialogDescription>
        </DialogHeader>
        <Field label="Class session" htmlFor="register-session">
          <NativeSelect
            id="register-session"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="Choose a session"
            options={delivered.map((s) => ({ value: s.session_id, label: `${s.session_code} · ${s.title}` }))}
          />
        </Field>
        <Field label="Drive file reference" htmlFor="register-media">
          <Input id="register-media" value={mediaRef} onChange={(e) => setMediaRef(e.target.value)} />
        </Field>
        <Field label="Duration (minutes)" htmlFor="register-duration">
          <Input id="register-duration" inputMode="numeric" value={duration} onChange={(e) => setDuration(e.target.value)} />
        </Field>
        <DialogFooter>
          <Button
            disabled={!sessionId || register.isPending}
            onClick={() =>
              register.mutate({
                session_id: Number(sessionId),
                ...(mediaRef.trim() && { media_ref: mediaRef.trim() }),
                ...(duration && { duration_minutes: Number(duration) }),
              })
            }
          >
            Register
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
