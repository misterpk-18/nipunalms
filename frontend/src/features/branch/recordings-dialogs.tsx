/** The dialogs of the Recordings screen: add or edit a recording's media, and report a problem with one. */
import { useState, type ReactNode } from "react";
import { contentApi, type ProblemReason, type Recording } from "@/api/content";
import { Field } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";
import { DRIVE_HINT, PROBLEM_CHOICES } from "./recordings-choices";

const RECORDING_KEYS = [["recordings"], ["recording-exceptions"], ["issues"]];

/** Add a recording to a class, or change where an existing one lives. */
export function MediaDialog({
  open,
  onClose,
  sessionId,
  recording,
  intro,
}: {
  open: boolean;
  onClose: () => void;
  /** Set when adding a recording to a class that has none. */
  sessionId?: number;
  recording?: Recording;
  intro?: ReactNode;
}) {
  const [mediaRef, setMediaRef] = useState(recording?.media_ref ?? "");
  const [duration, setDuration] = useState(recording?.duration_minutes ? String(recording.duration_minutes) : "");
  const [download, setDownload] = useState(recording?.download_allowed ?? false);
  const adding = !recording;
  const save = useApiMutation(
    () =>
      recording
        ? contentApi.updateRecording(recording.recording_id, {
            media_ref: mediaRef.trim() || null,
            duration_minutes: duration ? Number(duration) : null,
            download_allowed: download,
          })
        : contentApi.registerRecording({
            session_id: sessionId,
            ...(mediaRef.trim() && { media_ref: mediaRef.trim() }),
            ...(duration && { duration_minutes: Number(duration) }),
          }),
    { success: adding ? "Recording added" : "Media details saved", invalidate: RECORDING_KEYS, onSuccess: onClose },
  );
  const durationOk = duration === "" || (Number(duration) > 0 && Number.isInteger(Number(duration)));
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{adding ? "Add recording" : "Media"}</DialogTitle>
          <DialogDescription>
            {intro ?? (adding ? "Add the recording of this class. You can release it afterwards." : "Where the video lives and how long it is.")}
          </DialogDescription>
        </DialogHeader>
        <Field label="Drive file id" htmlFor="media-ref" hint={DRIVE_HINT}>
          <Input id="media-ref" value={mediaRef} onChange={(e) => setMediaRef(e.target.value)} />
        </Field>
        <Field label="Length in minutes" htmlFor="media-duration" error={durationOk ? undefined : "Use a whole number of minutes."}>
          <Input id="media-duration" inputMode="numeric" value={duration} onChange={(e) => setDuration(e.target.value)} />
        </Field>
        {!adding && (
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-1" checked={download} onChange={(e) => setDownload(e.target.checked)} />
            <span>Let students download this recording (only when it has been agreed as an exception).</span>
          </label>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={save.isPending || !durationOk} onClick={() => save.mutate()}>
            {adding ? "Add recording" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Report a problem with a recording. No reason is chosen to begin with, so a problem is never reported by accident. */
export function ProblemDialog({ recording, open, onClose }: { recording: Recording; open: boolean; onClose: () => void }) {
  const [reason, setReason] = useState<ProblemReason | "">("");
  const [note, setNote] = useState("");
  const choice = PROBLEM_CHOICES.find((c) => c.value === reason);
  const report = useApiMutation(
    () => contentApi.reportProblem(recording.recording_id, { reason: reason as ProblemReason, ...(note.trim() && { note: note.trim() }) }),
    {
      success: "Problem reported",
      next: "It is on the open problems list until the recording is released.",
      invalidate: RECORDING_KEYS,
      onSuccess: onClose,
    },
  );
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Report a problem</DialogTitle>
          <DialogDescription>
            {recording.session.title} · {recording.recording_code}. Students will see that the recording is not available yet.
          </DialogDescription>
        </DialogHeader>
        <fieldset className="space-y-2">
          <legend className="mb-1 text-sm font-medium">What is wrong?</legend>
          {PROBLEM_CHOICES.map((c) => (
            <label key={c.value} className="flex items-center gap-2 text-sm">
              <input type="radio" name="problem-reason" value={c.value} checked={reason === c.value} onChange={() => setReason(c.value)} />
              {c.label}
            </label>
          ))}
        </fieldset>
        {choice && (
          <Field label={choice.noteLabel} htmlFor="problem-note">
            <Textarea id="problem-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!choice || (choice.needsNote && !note.trim()) || report.isPending} onClick={() => report.mutate()}>
            Report problem
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
