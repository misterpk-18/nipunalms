/**
 * The focused grading screen (UX plan U13): one hand-in or one test attempt at a time, with the review beside the work and
 * "Save & next" walking through the To grade list. Starting a review is an explicit button, not a side effect of typing.
 */
import { useState } from "react";
import { Link, useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { assessmentsApi, type StaffAttempt, type Submission } from "@/api/assessments";
import { useToGrade, type GradeItem } from "@/api/trainer";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { EmptyState } from "@/components/lms/empty-state";
import { Field } from "@/components/lms/forms";
import { PageHead, QueryView, Section, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { fmtDate, fmtDateTime } from "@/features/shared/format";
import { fromIstInput, istInputIn } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";

const REFRESH = [["trainer"], ["submissions"], ["attempts"], ["results"], ["assignments"], ["tests"], ["nav", "counts"]];

/** Marks typed as text, checked against the maximum: the value when it is valid, else the reason it is not. */
export function checkMarks(text: string, max: number): { value: number | null; error: string | null } {
  if (text.trim() === "") return { value: null, error: null };
  const value = Number(text);
  if (Number.isNaN(value)) return { value: null, error: "Enter a number." };
  if (value < 0 || value > max) return { value: null, error: `Marks must be between 0 and ${max}.` };
  return { value, error: null };
}

type Advance = { advance: boolean; to: GradeItem | undefined };

/** Where "Save & next" goes: the item after this one in the list, else the first one left, else back to the inbox. */
function useNextItem(current: string, batch: number | undefined) {
  const queue = useToGrade(batch);
  const navigate = useNavigate();
  const items = queue.data?.items ?? [];
  const index = items.findIndex((i) => i.key === current);
  const next: GradeItem | undefined = items[index + 1] ?? items.find((i) => i.key !== current);
  const go = (to: GradeItem | undefined) => {
    if (!to) {
      toast.success("All caught up. Nothing else is waiting for your marks.");
      void navigate({ to: "/trainer/to-grade", search: batch ? { batch } : {} });
      return;
    }
    void navigate({ to: "/trainer/to-grade/$kind/$id", params: { kind: to.kind, id: String(to.id) }, search: batch ? { batch } : {} });
  };
  return { ready: !queue.isPending, next, position: index >= 0 ? index + 1 : null, total: items.length, go: () => go(next), goTo: go };
}

function Position({
  position,
  total,
  next,
  go,
  batch,
}: {
  position: number | null;
  total: number;
  next: GradeItem | undefined;
  go: () => void;
  batch?: number;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
      {position !== null && (
        <span>
          {position} of {total} waiting
        </span>
      )}
      {next && (
        <Button variant="ghost" size="sm" onClick={go}>
          Skip to the next
        </Button>
      )}
      <Button asChild variant="ghost" size="sm">
        <Link to="/trainer/to-grade" search={batch ? { batch } : {}}>
          Back to the list
        </Link>
      </Button>
    </div>
  );
}

export function GradeScreen() {
  const { kind, id } = useParams({ from: "/trainer/to-grade/$kind/$id" });
  const { batch } = useSearch({ from: "/trainer/to-grade/$kind/$id" });
  const numeric = Number(id);
  if ((kind !== "submission" && kind !== "attempt") || !Number.isInteger(numeric) || numeric < 1) {
    return (
      <div className="mx-auto max-w-4xl">
        <PageHead title="To grade" />
        <EmptyState
          reason="That item does not exist."
          action={
            <Button asChild size="sm">
              <Link to="/trainer/to-grade">Back to To grade</Link>
            </Button>
          }
        />
      </div>
    );
  }
  return kind === "submission" ? <SubmissionGrade id={numeric} batch={batch} /> : <AttemptGrade id={numeric} batch={batch} />;
}

// ---------------------------------------------------------------- a hand-in

function SubmissionGrade({ id, batch }: { id: number; batch: number | undefined }) {
  const query = useQuery({ queryKey: ["submissions", "detail", id], queryFn: () => assessmentsApi.submission(id) });
  const nav = useNextItem(`submission-${id}`, batch);
  return (
    <div className="mx-auto max-w-4xl">
      <QueryView query={query} skeleton="detail">
        {(submission) => <SubmissionBody submission={submission} nav={nav} batch={batch} />}
      </QueryView>
    </div>
  );
}

function SubmissionBody({ submission, nav, batch }: { submission: Submission; nav: ReturnType<typeof useNextItem>; batch: number | undefined }) {
  const id = submission.submission_id;
  const assignment = submission.assignment;
  const max = Number(assignment.max_marks ?? 0);
  const [feedback, setFeedback] = useState("");
  const [marks, setMarks] = useState("");
  const [resubmitBy, setResubmitBy] = useState(istInputIn(72));
  const [asking, setAsking] = useState(false);
  const checked = checkMarks(marks, max);
  const started = Boolean(submission.review_started_at);
  const done = submission.review !== null;
  const latest = (submission.versions ?? []).at(-1)?.submission_id;
  const newer = latest !== undefined && latest !== id;

  const start = useApiMutation(() => assessmentsApi.startReview(id), { invalidate: [["submissions", "detail", id], ["trainer"]] });
  // The next item is fixed when the button is pressed: saving changes the list, and the one to open must not move with it
  const save = useApiMutation((_go: Advance) => assessmentsApi.review(id, { outcome: "Reviewed", feedback: feedback.trim(), marks: checked.value ?? 0 }), {
    success: "Review saved",
    next: "The marks stay provisional until your Branch Manager publishes them.",
    invalidate: REFRESH,
    onSuccess: (_result, go) => {
      if (go.advance) nav.goTo(go.to);
    },
  });
  const resubmit = useApiMutation(
    (_go: Advance) =>
      assessmentsApi.review(id, { outcome: "Resubmission Requested", feedback: feedback.trim(), resubmission_due_at: fromIstInput(resubmitBy) }),
    {
      success: `${submission.student.full_name} was asked to resubmit`,
      next: "They are notified and can hand in a new version.",
      invalidate: REFRESH,
      onSuccess: (_result, go) => nav.goTo(go.to),
    },
  );

  const canSave = started && feedback.trim().length > 0 && checked.value !== null && !save.isPending;

  return (
    <>
      <Breadcrumbs items={[{ label: "To grade", to: "/trainer/to-grade" }, { label: assignment.title }]} />
      <PageHead
        title={assignment.title}
        description={
          <>
            {submission.student.full_name} · {submission.student.student_code} · handed in {fmtDateTime(submission.submitted_at)}
            {submission.is_late && " (late)"}
          </>
        }
        actions={<Position position={nav.position} total={nav.total} next={nav.next} go={nav.go} {...(batch ? { batch } : {})} />}
      />
      <div className="space-y-4">
        {newer && (
          <StatusNote tone="warning">The student handed in a newer version. Open it from To grade; only the newest version can be reviewed.</StatusNote>
        )}
        <Section title="Their work">
          <div className="space-y-2">
            {submission.body_text && <p className="whitespace-pre-wrap rounded-lg bg-muted p-3 text-sm">{submission.body_text}</p>}
            {submission.link_url && (
              <a href={submission.link_url} target="_blank" rel="noreferrer" className="block text-sm text-primary underline">
                {submission.link_url}
              </a>
            )}
            {submission.file && (
              <Button variant="outline" size="sm" onClick={() => void assessmentsApi.downloadSubmission(id, submission.file!.filename)}>
                Download {submission.file.filename}
              </Button>
            )}
            {submission.ai_disclosure && <p className="text-sm">AI use they declared: {submission.ai_disclosure}</p>}
            {!submission.body_text && !submission.link_url && !submission.file && <p className="text-sm text-muted-foreground">Nothing was attached.</p>}
          </div>
          {(submission.versions?.length ?? 0) > 1 && (
            <p className="mt-3 text-xs text-muted-foreground">
              This is version {submission.version_no} of {submission.versions!.length}. Earlier versions:{" "}
              {submission
                .versions!.filter((v) => v.submission_id !== id)
                .map(
                  (v) =>
                    `v${v.version_no} on ${fmtDate(v.submitted_at)}${v.review ? ` (${v.review.outcome === "Reviewed" ? "reviewed" : "resubmission asked"})` : ""}`,
                )
                .join(", ")}
              .
            </p>
          )}
        </Section>
        <details className="rounded-xl border bg-card p-4 shadow-sm">
          <summary className="cursor-pointer text-sm font-semibold">The task they were given (out of {max} marks)</summary>
          <p className="mt-2 whitespace-pre-wrap text-sm">{assignment.brief}</p>
        </details>

        <Section title="Your review">
          {done ? (
            <div className="space-y-2 text-sm">
              <p>
                <Tag tone="success">{submission.review!.outcome === "Reviewed" ? "Reviewed" : "Asked to resubmit"}</Tag>
                {submission.review!.marks !== null && (
                  <span className="ml-2 font-medium">
                    {submission.review!.marks} / {max}
                  </span>
                )}
              </p>
              <p className="whitespace-pre-wrap">{submission.review!.feedback}</p>
              <Button onClick={nav.go}>{nav.next ? "On to the next one" : "Back to the list"}</Button>
            </div>
          ) : !started ? (
            <div className="space-y-3">
              <p className="text-sm">
                You have not started this review. Start it when you open the work: it records that you are looking at it. Then write your feedback and marks.
              </p>
              <Button disabled={start.isPending} onClick={() => start.mutate(undefined)}>
                Start review
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
                <Field label="Feedback for the student" htmlFor="grade-feedback">
                  <Textarea id="grade-feedback" rows={4} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
                </Field>
                <Field label={`Marks out of ${max}`} htmlFor="grade-marks" error={checked.error ?? undefined}>
                  <Input id="grade-marks" inputMode="decimal" value={marks} aria-invalid={checked.error !== null} onChange={(e) => setMarks(e.target.value)} />
                </Field>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button disabled={!canSave || !nav.ready} onClick={() => save.mutate({ advance: true, to: nav.next })}>
                  Save &amp; next
                </Button>
                <Button variant="outline" disabled={!canSave} onClick={() => save.mutate({ advance: false, to: undefined })}>
                  Save
                </Button>
                <Button variant="ghost" onClick={() => setAsking((open) => !open)} aria-expanded={asking}>
                  More
                </Button>
              </div>
              {asking && (
                <div className="space-y-2 rounded-lg border bg-muted/40 p-3">
                  <p className="text-sm font-medium">Ask the student to hand it in again</p>
                  <p className="text-xs text-muted-foreground">Uses your feedback above as the reason. No marks are given for this version.</p>
                  <Field label="Hand in again by (IST)" htmlFor="grade-resubmit-by">
                    <Input id="grade-resubmit-by" type="datetime-local" value={resubmitBy} onChange={(e) => setResubmitBy(e.target.value)} />
                  </Field>
                  <ConfirmDialog
                    title="Ask for a new version?"
                    consequence={`${submission.student.full_name} is told to hand this work in again by ${resubmitBy.replace("T", " ")} IST. This version gets no marks.`}
                    confirmLabel="Ask to resubmit"
                    onConfirm={() => resubmit.mutateAsync({ advance: true, to: nav.next })}
                  >
                    <Button variant="outline" disabled={!feedback.trim() || resubmit.isPending}>
                      Ask to resubmit
                    </Button>
                  </ConfirmDialog>
                  {!feedback.trim() && <p className="text-xs text-muted-foreground">Write your feedback first.</p>}
                </div>
              )}
              <p className="text-xs text-muted-foreground">The marks stay provisional until your Branch Manager publishes them.</p>
            </div>
          )}
        </Section>
      </div>
    </>
  );
}

// ---------------------------------------------------------------- a test attempt

function AttemptGrade({ id, batch }: { id: number; batch: number | undefined }) {
  const query = useQuery({ queryKey: ["attempts", "staff", id], queryFn: () => assessmentsApi.staffAttempt(id) });
  const nav = useNextItem(`attempt-${id}`, batch);
  return (
    <div className="mx-auto max-w-4xl">
      <QueryView query={query} skeleton="detail">
        {(attempt) => <AttemptBody attempt={attempt} id={id} nav={nav} batch={batch} />}
      </QueryView>
    </div>
  );
}

function AttemptBody({ attempt, id, nav, batch }: { attempt: StaffAttempt; id: number; nav: ReturnType<typeof useNextItem>; batch: number | undefined }) {
  const pending = attempt.questions.filter((q) => q.needs_grading);
  const [marks, setMarks] = useState<Record<number, string>>({});
  const [notes, setNotes] = useState<Record<number, string>>({});
  const checks = Object.fromEntries(pending.map((q) => [q.question_id, checkMarks(marks[q.question_id] ?? "", Number(q.marks))]));
  const complete = pending.length > 0 && pending.every((q) => checks[q.question_id]?.value !== null);
  const finished = attempt.attempt.grading_status === "Graded";

  const save = useApiMutation(
    (_go: Advance) =>
      assessmentsApi.grade(
        id,
        pending.map((q) => ({
          question_id: q.question_id,
          marks: checks[q.question_id]?.value ?? 0,
          ...(notes[q.question_id]?.trim() ? { feedback: notes[q.question_id]!.trim() } : {}),
        })),
      ),
    {
      success: "Marks saved",
      next: "The score stays provisional until your Branch Manager publishes it.",
      invalidate: REFRESH,
      onSuccess: (_result, go) => {
        if (go.advance) nav.goTo(go.to);
      },
    },
  );

  return (
    <>
      <Breadcrumbs items={[{ label: "To grade", to: "/trainer/to-grade" }, { label: attempt.test.title }]} />
      <PageHead
        title={attempt.test.title}
        description={
          <>
            {attempt.student.full_name} · {attempt.student.student_code} · submitted {fmtDateTime(attempt.attempt.submitted_at)} · receipt{" "}
            {attempt.attempt.receipt_code}
          </>
        }
        actions={<Position position={nav.position} total={nav.total} next={nav.next} go={nav.go} {...(batch ? { batch } : {})} />}
      />
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Questions with fixed answers are already scored. Mark the written and coding answers below
          {pending.length > 0 ? ` (${pending.length} to mark).` : "."}
        </p>
        {attempt.questions.map((q) => (
          <Section key={q.question_id} title={`Question ${q.position} · ${q.question_type} · ${q.marks} marks`}>
            <p className="whitespace-pre-wrap text-sm">{q.stem}</p>
            <pre className="my-2 whitespace-pre-wrap rounded-lg bg-muted p-3 font-mono text-xs">
              {q.answer === null || q.answer === undefined ? "(no answer)" : typeof q.answer === "string" ? q.answer : JSON.stringify(q.answer)}
            </pre>
            {q.needs_grading ? (
              <div className="grid gap-3 sm:grid-cols-[10rem_1fr]">
                <Field label={`Marks out of ${q.marks}`} htmlFor={`marks-${q.question_id}`} error={checks[q.question_id]?.error ?? undefined}>
                  <Input
                    id={`marks-${q.question_id}`}
                    inputMode="decimal"
                    value={marks[q.question_id] ?? ""}
                    aria-invalid={checks[q.question_id]?.error != null}
                    onChange={(e) => setMarks({ ...marks, [q.question_id]: e.target.value })}
                  />
                </Field>
                <Field label="Feedback (optional)" htmlFor={`note-${q.question_id}`}>
                  <Textarea
                    id={`note-${q.question_id}`}
                    rows={2}
                    value={notes[q.question_id] ?? ""}
                    onChange={(e) => setNotes({ ...notes, [q.question_id]: e.target.value })}
                  />
                </Field>
                <p className="text-xs text-muted-foreground sm:col-span-2">
                  What a good answer has: {String((q.answer_key as { rubric?: string } | undefined)?.rubric ?? "no guide was written")}
                </p>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Scored {q.awarded_marks ?? "0"} / {q.marks}
                {q.is_auto_graded ? " automatically" : ""}.
              </p>
            )}
          </Section>
        ))}
        {!attempt.can_grade ? (
          <StatusNote tone="info">Only the trainer of this batch marks these answers.</StatusNote>
        ) : finished ? (
          <StatusNote tone="success">
            Marked: {attempt.attempt.total_score} / {attempt.attempt.total_marks}.{" "}
            <button className="underline" onClick={nav.go}>
              {nav.next ? "On to the next one" : "Back to the list"}
            </button>
          </StatusNote>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <Button disabled={!complete || save.isPending || !nav.ready} onClick={() => save.mutate({ advance: true, to: nav.next })}>
              Save &amp; next
            </Button>
            <Button variant="outline" disabled={!complete || save.isPending} onClick={() => save.mutate({ advance: false, to: undefined })}>
              Save
            </Button>
            {!complete && pending.length > 0 && <span className="text-xs text-muted-foreground">Give marks for every written answer to save.</span>}
          </div>
        )}
      </div>
    </>
  );
}
