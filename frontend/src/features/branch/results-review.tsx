/** The review of one assignment or test in one batch: every student's marks, a way to change them, and Publish. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, resultsReviewApi, type Result, type ReviewQueueRow } from "@/api/assessments";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useApiMutation } from "@/lib/mutation";
import { countsText, marksText, plural, scopeOf } from "./results-text";

const REFRESH = [["results"], ["assessment-reviews"], ["branch"], ["nav"]];

function StudentRow({ result, canChange }: { result: Result; canChange: boolean }) {
  const [editing, setEditing] = useState(false);
  const [marks, setMarks] = useState("");
  const [reason, setReason] = useState("");
  const max = Number(result.max_marks);
  const value = Number(marks);
  const marksOk = marks.trim() !== "" && Number.isFinite(value) && value >= 0 && value <= max;
  const reasonOk = reason.trim().length >= 5;
  const save = useApiMutation(() => assessmentsApi.moderate(result.result_id, value, reason.trim()), {
    success: `Marks changed for ${result.student.full_name}`,
    next: "Students do not see them until you publish.",
    invalidate: REFRESH,
    onSuccess: () => {
      setEditing(false);
      setMarks("");
      setReason("");
    },
  });
  return (
    <li className="rounded-lg border p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <strong className="break-words">{result.student.full_name}</strong>
          <StatusBadge domain="result" code={result.status} />
        </div>
        {canChange && result.status !== "Published" && !editing && (
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
            Change marks
          </Button>
        )}
      </div>
      <p className="mt-1 text-muted-foreground">
        Trainer's marks {marksText(result.provisional_marks)} of {marksText(result.max_marks)}
        {result.moderated_marks !== null && ` · Your marks ${marksText(result.moderated_marks)}`}
        {result.final_marks !== null && ` · Published ${marksText(result.final_marks)}`}
      </p>
      {result.moderation_reason && <p className="mt-1 text-muted-foreground">Why they were changed: {result.moderation_reason}</p>}
      {editing && (
        <div className="mt-3 space-y-2 rounded-lg bg-muted/50 p-3">
          <div className="flex flex-wrap items-start gap-2">
            <div className="space-y-1">
              <Input
                aria-label={`New marks for ${result.student.full_name}`}
                className="w-32"
                inputMode="decimal"
                placeholder={`0 to ${marksText(result.max_marks)}`}
                value={marks}
                onChange={(e) => setMarks(e.target.value)}
              />
              {marks.trim() !== "" && !marksOk && <p className="text-xs text-destructive">Enter a number from 0 to {marksText(result.max_marks)}.</p>}
            </div>
            <div className="min-w-48 flex-1 space-y-1">
              <Input
                aria-label={`Why ${result.student.full_name}'s marks change`}
                placeholder="Why are the marks changing?"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
              {reason.trim() !== "" && !reasonOk && <p className="text-xs text-destructive">Write at least 5 characters.</p>}
            </div>
          </div>
          <div className="flex gap-2">
            <Button size="sm" disabled={!marksOk || !reasonOk || save.isPending} onClick={() => save.mutate(undefined)}>
              Save marks
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

/** Publish, asked first: the counts come from the API at the moment the confirm opens. */
function PublishButton({ row, onDone }: { row: ReviewQueueRow; onDone: () => void }) {
  const scope = scopeOf(row);
  const preview = useQuery({ queryKey: ["results", "publish-preview", scope], queryFn: () => resultsReviewApi.publishPreview(scope), staleTime: 0 });
  const publish = useApiMutation(() => resultsReviewApi.publishScope(scope), {
    success: (r) => `${plural(r.published, "result")} published`,
    next: "Students have been told.",
    view: { to: "/branch/results", label: "View marks & results" },
    invalidate: REFRESH,
    onSuccess: onDone,
  });
  const p = preview.data;
  if (!p) return <Button disabled>Publish results</Button>;
  if (p.to_publish === 0)
    return (
      <p className="text-sm text-muted-foreground">
        Nothing left to publish.{p.awaiting_grading > 0 ? ` ${plural(p.awaiting_grading, "attempt")} still being marked.` : ""}
      </p>
    );
  return (
    <ConfirmDialog
      title={`Publish ${plural(p.to_publish, "result")}?`}
      consequence={
        <>
          {p.unreviewed > 0 && <span className="block">{p.unreviewed} still unreviewed (the trainer's marks as they are).</span>}
          <span className="block">Students will see their marks now and cannot be shown a lower mark later.</span>
          {p.awaiting_grading > 0 && (
            <span className="block">
              {p.awaiting_grading === 1
                ? "1 attempt is still being marked and is not included."
                : `${p.awaiting_grading} attempts are still being marked and are not included.`}
            </span>
          )}
        </>
      }
      confirmLabel="Publish now"
      onConfirm={() => publish.mutateAsync(undefined)}
    >
      <Button onClick={() => void preview.refetch()}>Publish results</Button>
    </ConfirmDialog>
  );
}

export function ResultsReviewDialog({ row, onClose }: { row: ReviewQueueRow; onClose: () => void }) {
  const scope = scopeOf(row);
  const query = useQuery({ queryKey: ["results", "staff", scope], queryFn: () => assessmentsApi.results(scope) });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{row.title}</DialogTitle>
          <DialogDescription>
            {row.batch.batch_code} · {countsText(row.counts)}. Students see marks only after you publish them.
          </DialogDescription>
        </DialogHeader>
        <QueryView query={query} skeleton="cards" isEmpty={(p) => p.data.length === 0} empty="No marks have come in yet.">
          {(page) => (
            <>
              {page.meta.pages > 1 && (
                <p className="text-xs text-muted-foreground">
                  Showing the first {page.data.length} of {page.meta.total} students.
                </p>
              )}
              <ul className="space-y-2" aria-label="Marks by student">
                {page.data.map((r) => (
                  <StudentRow key={`${r.result_id}-${r.status}-${r.moderated_marks}`} result={r} canChange={row.can_moderate} />
                ))}
              </ul>
            </>
          )}
        </QueryView>
        {row.can_moderate && (
          <div className="flex flex-wrap items-center gap-3 border-t pt-3">
            <PublishButton row={row} onDone={onClose} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
