/** Recordings: pick a class by date and batch, then release its recording or report a problem with it. */
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { contentApi, type Recording, type RecordingClass, type RecordingException } from "@/api/content";
import { deliveryApi } from "@/api/delivery";
import { useActing } from "@/auth/acting";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { EmptyState } from "@/components/lms/empty-state";
import { NativeSelect } from "@/components/lms/forms";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fmtDate, fmtRange } from "@/features/shared/delivery-ui";
import { ReasonDialog } from "@/features/shared/reason-dialog";
import { todayIso } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";
import { problemText } from "./recordings-choices";
import { MediaDialog, ProblemDialog } from "./recordings-dialogs";
import { BranchPicker } from "./my-work";

const DAY_MS = 86_400_000;
const istDay = (iso: string) => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date(iso));
const yesterdayIso = () => new Date(new Date(`${todayIso()}T12:00:00+05:30`).getTime() - DAY_MS).toISOString().slice(0, 10);
const batchLabel = (b: { display_name?: string | null; batch_code: string }) => b.display_name ?? b.batch_code;
const KEYS = [["recordings"], ["recording-exceptions"], ["issues"]];

type Params = { date?: string; batch?: number; exception?: number };

/** The date, the batch and a deep-linked problem, kept in the address. */
function useRecordingParams() {
  const raw = useSearch({ strict: false }) as Record<string, unknown>;
  const navigate = useNavigate();
  const params: Params = {
    ...(typeof raw["date"] === "string" && /^\d{4}-\d{2}-\d{2}$/.test(raw["date"]) ? { date: raw["date"] } : {}),
    ...(Number(raw["batch"]) > 0 ? { batch: Number(raw["batch"]) } : {}),
    ...(Number(raw["exception"]) > 0 ? { exception: Number(raw["exception"]) } : {}),
  };
  const set = (next: { [K in keyof Params]: Params[K] | undefined }) => {
    const merged = { ...raw, ...next } as Record<string, unknown>;
    for (const k of Object.keys(merged)) if (merged[k] === undefined || merged[k] === "") delete merged[k];
    void navigate({ to: ".", search: (() => merged) as never, replace: true });
  };
  return { params, set };
}

// ---------------------------------------------------------------- one recording

function RecordingRow({ recording, batchName }: { recording: Recording; batchName: string }) {
  const [dialog, setDialog] = useState<"media" | "problem" | null>(null);
  const release = useApiMutation(() => contentApi.recordingAction(recording.recording_id, "release"), {
    success: "Recording released",
    next: `Students of ${batchName} are told and can watch it now.`,
    invalidate: KEYS,
  });
  const releasable = recording.status !== "Released" && recording.status !== "Expired";
  const hasMedia = !!recording.media_ref;
  return (
    <li className="space-y-2 rounded-lg border bg-background p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">
          {recording.recording_code}
          {recording.part_no > 1 ? ` · part ${recording.part_no}` : ""}
        </span>
        <StatusBadge domain="recording" code={recording.status} />
      </div>
      {recording.problem && <p className="text-sm text-warning">{problemText(recording.problem)}</p>}
      <p className="break-all text-xs text-muted-foreground">
        {hasMedia ? `Drive file id: ${recording.media_ref}` : "No Drive file id yet"}
        {recording.duration_minutes ? ` · ${recording.duration_minutes} min` : ""}
      </p>
      <div className="flex flex-wrap gap-2">
        {releasable &&
          (hasMedia ? (
            <ConfirmDialog
              title="Release this recording?"
              consequence={`Students of ${batchName} will be told and can watch it now.`}
              confirmLabel="Release"
              onConfirm={() => release.mutateAsync()}
            >
              <Button size="sm" disabled={release.isPending}>
                Release
              </Button>
            </ConfirmDialog>
          ) : (
            <Button size="sm" onClick={() => setDialog("media")}>
              Release
            </Button>
          ))}
        {recording.status !== "Released" && (
          <Button size="sm" variant="outline" onClick={() => setDialog("problem")}>
            Report a problem
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => setDialog("media")}>
          Media
        </Button>
      </div>
      {dialog === "media" && (
        <MediaDialog
          open
          recording={recording}
          onClose={() => setDialog(null)}
          intro={hasMedia ? undefined : "This recording needs its Drive file id before it can be released. Save it here, then press Release."}
        />
      )}
      {dialog === "problem" && <ProblemDialog open recording={recording} onClose={() => setDialog(null)} />}
    </li>
  );
}

function ClassCard({ item }: { item: RecordingClass }) {
  const [adding, setAdding] = useState(false);
  const name = batchLabel(item.batch);
  return (
    <li className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="break-words text-sm font-semibold">{item.title}</h3>
          <p className="text-xs text-muted-foreground">
            {name} · {fmtRange(item.starts_at, item.ends_at)}
          </p>
        </div>
        {item.recordings.length === 0 && (
          <Button size="sm" onClick={() => setAdding(true)}>
            Add recording
          </Button>
        )}
      </div>
      {item.recordings.length === 0 ? (
        <p className="text-sm text-muted-foreground">This class has no recording yet. Students cannot watch it until you add one and release it.</p>
      ) : (
        <ul className="space-y-2" aria-label={`Recordings of ${item.title}`}>
          {item.recordings.map((r) => (
            <RecordingRow key={r.recording_id} recording={r} batchName={name} />
          ))}
        </ul>
      )}
      {adding && <MediaDialog open sessionId={item.session_id} onClose={() => setAdding(false)} />}
    </li>
  );
}

// ---------------------------------------------------------------- open problems

function OpenProblems({ onOpen }: { onOpen: (e: RecordingException) => void }) {
  const { branchId } = useActing("branch");
  const query = useQuery({
    queryKey: ["recording-exceptions", "open", branchId],
    queryFn: () => contentApi.exceptions({ status: "Open", per_page: 50, branch_id: branchId }),
  });
  const handled = useApiMutation((v: { id: number; note: string }) => contentApi.resolveException(v.id, v.note), {
    success: "Marked as handled",
    invalidate: KEYS,
  });
  if (query.isPending || query.isError) return null;
  const rows = query.data.data;
  if (rows.length === 0) return null;
  const total = query.data.meta.total;
  return (
    <Section title={`Open problems (${total})`}>
      <p className="mb-2 text-xs text-muted-foreground">A problem closes by itself when its recording is released.</p>
      <ul className="divide-y">
        {rows.slice(0, 5).map((e) => (
          <li key={e.exception_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <div className="min-w-0">
              <p className="break-words text-sm font-medium">
                {e.session.title} · {batchLabel(e.batch)}
              </p>
              <p className="break-words text-xs text-muted-foreground">
                {e.issue} · {fmtDate(e.session.starts_at)}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => onOpen(e)}>
                Open
              </Button>
              <ReasonDialog
                trigger={
                  <Button size="sm" variant="outline">
                    Mark as handled
                  </Button>
                }
                title="Mark as handled"
                description="Use this only when there is no recording left to release. Say what was done."
                label="What was done"
                confirmLabel="Mark as handled"
                busy={handled.isPending}
                onSubmit={(note) => handled.mutateAsync({ id: e.exception_id, note })}
              />
            </div>
          </li>
        ))}
      </ul>
      {total > 5 && <p className="mt-2 text-xs text-muted-foreground">Showing 5 of {total}. Handle these and the next ones appear.</p>}
    </Section>
  );
}

// ---------------------------------------------------------------- the screen

export function BranchRecordings() {
  const { branchId } = useActing("branch");
  const { params, set } = useRecordingParams();
  const date = params.date ?? todayIso();
  const batchId = params.batch;

  // An Issues deep link names a problem: jump to its class's date and batch, once.
  const linked = useQuery({
    queryKey: ["recording-exceptions", "one", params.exception],
    queryFn: () => contentApi.exception(params.exception as number),
    enabled: !!params.exception,
  });
  const jumped = useRef<number | null>(null);
  useEffect(() => {
    if (linked.data && jumped.current !== linked.data.exception_id) {
      jumped.current = linked.data.exception_id;
      set({ date: istDay(linked.data.session.starts_at), batch: linked.data.batch.batch_id, exception: undefined });
    }
  });

  const batches = useQuery({ queryKey: ["delivery", "batches", "recordings", branchId], queryFn: () => deliveryApi.batches({ branch_id: branchId }) });
  const classes = useQuery({
    queryKey: ["recordings", "classes", date, batchId ?? null, branchId],
    queryFn: () => contentApi.recordingClasses({ date, batch_id: batchId }),
  });
  const openProblem = (e: RecordingException) => set({ date: istDay(e.session.starts_at), batch: e.batch.batch_id, exception: undefined });

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead
        title="Recordings"
        description="Pick the class by date and batch, then release its recording to students or report a problem with it."
        actions={<BranchPicker />}
      />
      <StatusNote tone="info">
        Google Drive is not connected yet. The LMS stores each recording's Drive file id but cannot check that the video plays.
      </StatusNote>
      <OpenProblems onOpen={openProblem} />

      <Section title="Find the class">
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-full sm:w-48">
            <label htmlFor="rec-date" className="mb-1.5 block text-sm font-medium">
              Date
            </label>
            <Input id="rec-date" type="date" value={date} onChange={(e) => e.target.value && set({ date: e.target.value, exception: undefined })} />
          </div>
          <div className="flex gap-2">
            <Button variant={date === todayIso() ? "default" : "outline"} onClick={() => set({ date: undefined })}>
              Today
            </Button>
            <Button variant={date === yesterdayIso() ? "default" : "outline"} onClick={() => set({ date: yesterdayIso() })}>
              Yesterday
            </Button>
          </div>
          <div className="w-full sm:w-72">
            <label htmlFor="rec-batch" className="mb-1.5 block text-sm font-medium">
              Batch
            </label>
            <NativeSelect
              id="rec-batch"
              placeholder="All batches"
              value={batchId ?? ""}
              onChange={(e) => set({ batch: e.target.value ? Number(e.target.value) : undefined })}
              options={(batches.data?.data ?? []).map((b) => ({ value: b.batch_id, label: `${batchLabel(b)} — ${b.course.course_code}` }))}
            />
          </div>
        </div>
      </Section>

      <QueryView
        query={classes}
        skeleton="cards"
        isEmpty={(rows) => rows.length === 0}
        empty={`No class was held on ${fmtDate(date)}${batchId ? " for this batch" : ""}. Only classes that have run can have a recording; try another date.`}
        emptyAction={
          <>
            <Button size="sm" variant="outline" onClick={() => set({ date: yesterdayIso() })}>
              Show yesterday
            </Button>
            {batchId && (
              <Button size="sm" variant="outline" onClick={() => set({ batch: undefined })}>
                Show all batches
              </Button>
            )}
          </>
        }
      >
        {(rows) => (
          <ul className="space-y-3" aria-label={`Classes on ${fmtDate(date)}`}>
            {rows.map((c) => (
              <ClassCard key={c.session_id} item={c} />
            ))}
          </ul>
        )}
      </QueryView>
      {linked.isError && <EmptyState reason="That recording problem could not be found. It may already be closed." />}

      <HowThisWorks>
        <p>Students of a batch see a recording only after you release it, and only until their access ends.</p>
        <p>
          Report a problem when the recording cannot be released yet. Students are told it is not available, and the problem stays on the open list until the
          recording is released.
        </p>
      </HowThisWorks>
    </div>
  );
}
