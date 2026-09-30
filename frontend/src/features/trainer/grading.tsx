import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, type AttemptRow } from "@/api/assessments";
import { DataTable, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { formatIst } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";

const REFRESH = [["attempts"], ["results"], ["tests"]];

function GradeDialog({ attempt, onClose }: { attempt: AttemptRow | null; onClose: () => void }) {
  const detail = useQuery({
    queryKey: ["attempts", "staff", attempt?.attempt_id],
    queryFn: () => assessmentsApi.staffAttempt(attempt!.attempt_id),
    enabled: attempt !== null,
  });
  const [marks, setMarks] = useState<Record<number, string>>({});
  const [notes, setNotes] = useState<Record<number, string>>({});
  const pending = (detail.data?.questions ?? []).filter((q) => q.needs_grading);
  const grade = useApiMutation(
    () =>
      assessmentsApi.grade(
        attempt!.attempt_id,
        pending
          .filter((q) => marks[q.question_id] !== undefined && marks[q.question_id] !== "")
          .map((q) => ({ question_id: q.question_id, marks: Number(marks[q.question_id]), feedback: notes[q.question_id] })),
      ),
    { success: "Marks saved", invalidate: REFRESH, onSuccess: onClose },
  );
  return (
    <Dialog open={attempt !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {attempt?.test.title}: {attempt?.student.full_name}
          </DialogTitle>
          <DialogDescription>Receipt {attempt?.receipt_code}. Objective questions are already scored; mark the written and coding answers.</DialogDescription>
        </DialogHeader>
        <QueryView query={detail}>
          {(d) => (
            <div className="space-y-3">
              {d.questions.map((q) => (
                <div key={q.question_id} className="rounded-lg border p-3 text-sm">
                  <p className="font-medium">
                    Q{q.position} · {q.question_type} · {q.marks} marks
                  </p>
                  <p className="my-1 whitespace-pre-wrap">{q.stem}</p>
                  <pre className="whitespace-pre-wrap rounded bg-muted p-2 font-mono text-xs">
                    {q.answer === null || q.answer === undefined ? "(no answer)" : String(q.answer)}
                  </pre>
                  {q.needs_grading ? (
                    <div className="mt-2 grid gap-2 sm:grid-cols-[8rem_1fr]">
                      <Input
                        aria-label={`Marks for question ${q.position}`}
                        inputMode="decimal"
                        placeholder={`/ ${q.marks}`}
                        value={marks[q.question_id] ?? ""}
                        onChange={(e) => setMarks({ ...marks, [q.question_id]: e.target.value })}
                      />
                      <Textarea
                        aria-label={`Feedback for question ${q.position}`}
                        rows={1}
                        placeholder="Feedback"
                        value={notes[q.question_id] ?? ""}
                        onChange={(e) => setNotes({ ...notes, [q.question_id]: e.target.value })}
                      />
                      <p className="text-xs text-muted-foreground sm:col-span-2">Rubric: {String((q.answer_key as { rubric?: string })?.rubric ?? "—")}</p>
                    </div>
                  ) : (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Awarded {q.awarded_marks ?? "—"} {q.is_auto_graded ? "(automatic)" : ""}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </QueryView>
        <DialogFooter>
          <Button disabled={grade.isPending || pending.length === 0} onClick={() => grade.mutate(undefined)}>
            Save marks
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function GradingQueue() {
  const query = useQuery({ queryKey: ["attempts", "queue"], queryFn: () => assessmentsApi.attempts({ grading_status: "Awaiting Grading" }) });
  const [open, setOpen] = useState<AttemptRow | null>(null);
  return (
    <div>
      <QueryView query={query} isEmpty={(p) => p.data.length === 0} empty="No attempts are waiting for grading.">
        {(page) => (
          <DataTable
            caption="Grading queue"
            rows={page.data}
            getKey={(a) => a.attempt_id}
            cols={[
              { h: "Student", c: (a) => a.student.full_name },
              { h: "Test", c: (a) => a.test.title },
              { h: "Receipt", c: (a) => <span className="font-mono text-xs">{a.receipt_code}</span> },
              { h: "Submitted", c: (a) => formatIst(a.submitted_at) },
              { h: "Auto score", c: (a) => `${a.auto_score ?? "—"} / ${a.total_marks}` },
              { h: "State", c: (a) => <StatusBadge>{`${a.manual_pending} to grade`}</StatusBadge> },
              {
                h: "Action",
                c: (a) => (
                  <Button size="sm" onClick={() => setOpen(a)}>
                    Grade
                  </Button>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <GradeDialog key={open?.attempt_id} attempt={open} onClose={() => setOpen(null)} />
    </div>
  );
}
