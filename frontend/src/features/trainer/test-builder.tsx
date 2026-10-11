import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, batchesForAuthoring, TEST_KINDS, type TestItem } from "@/api/assessments";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { Field, NativeSelect } from "@/components/lms/forms";
import { DataTable, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { formatIst, fromIstInput, istInputIn, toIstInput } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";

const REFRESH = [["tests"]];

/**
 * Build a test, or (with `test`) edit one that is not released yet. `fixedKind` fixes the type: the "New mock interview" button
 * uses it, and an interview has no pass marks or questions, only slots (offered on the Interviews tab).
 */
export function TestDialog({
  open,
  onOpenChange,
  test,
  fixedKind,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  test?: TestItem | undefined;
  fixedKind?: (typeof TEST_KINDS)[number];
}) {
  const editing = test !== undefined;
  const batches = useQuery({ queryKey: ["batches", "authoring"], queryFn: batchesForAuthoring, enabled: open && !editing });
  const [batchId, setBatchId] = useState("");
  const [kind, setKind] = useState<string>(test?.kind ?? fixedKind ?? "Practice quiz");
  const [title, setTitle] = useState(test?.title ?? "");
  const [duration, setDuration] = useState(test?.duration_minutes ? String(test.duration_minutes) : "");
  const [passMarks, setPassMarks] = useState(test?.pass_marks ?? "");
  const [closes, setCloses] = useState(editing ? toIstInput(test.closes_at) : fixedKind ? "" : istInputIn(24 * 7));
  const [instructions, setInstructions] = useState(test?.instructions ?? "");
  const interview = kind === "Mock interview";
  const create = useApiMutation(
    () =>
      editing
        ? assessmentsApi.updateTest(test.test_id, {
            title,
            instructions: instructions || null,
            duration_minutes: duration ? Number(duration) : null,
            ...(interview ? {} : { pass_marks: passMarks ? Number(passMarks) : null }),
            closes_at: closes ? fromIstInput(closes) : null,
          })
        : assessmentsApi.createTest({
            batch_id: Number(batchId),
            kind,
            title,
            instructions: instructions || undefined,
            ...(duration ? { duration_minutes: Number(duration) } : {}),
            ...(passMarks && !interview ? { pass_marks: Number(passMarks) } : {}),
            closes_at: closes ? fromIstInput(closes) : null,
          }),
    {
      success: (t) => (editing ? `${t.title} saved` : interview ? `${t.test_code} created` : `${t.test_code} created`),
      next: (t) =>
        t.kind === "Mock interview"
          ? "Offer interview slots on the Interviews tab, then release it."
          : editing
            ? "Select its questions if you have not, then release it."
            : "Select its questions, then release it to the batch.",
      invalidate: REFRESH,
      onSuccess: () => {
        onOpenChange(false);
        if (!editing) setTitle("");
      },
    },
  );
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editing ? `Edit ${test.title}` : interview ? "New mock interview" : "Build test"}</DialogTitle>
          <DialogDescription>
            {editing
              ? "Change the details while the test is not released. Once it is released only the instructions and the closing time can change."
              : interview
                ? "A practice interview with your students. Offer time slots next; students book one."
                : "Defaults follow the type (module test 30 minutes, final test 60, coding exercise 90). Then select questions and release."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {!editing ? (
            <Field label="Batch" htmlFor="t-batch">
              <NativeSelect
                id="t-batch"
                value={batchId}
                onChange={(e) => setBatchId(e.target.value)}
                placeholder="Select a batch"
                options={(batches.data?.data ?? []).map((b) => ({ value: b.batch_id, label: `${b.batch_code} · ${b.course.title}` }))}
              />
            </Field>
          ) : (
            <p className="text-sm text-muted-foreground">
              {test.kind} for batch <span className="font-mono">{test.batch.batch_code}</span>
            </p>
          )}
          {!editing && !fixedKind && (
            <Field label="Type" htmlFor="t-kind">
              <NativeSelect
                id="t-kind"
                value={kind}
                onChange={(e) => setKind(e.target.value)}
                options={TEST_KINDS.filter((k) => k !== "Mock interview").map((k) => ({ value: k, label: k }))}
              />
            </Field>
          )}
          <Field label="Title" htmlFor="t-title">
            <Input id="t-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Duration (min)" htmlFor="t-duration" hint="Blank = the type's default">
              <Input id="t-duration" inputMode="numeric" value={duration} onChange={(e) => setDuration(e.target.value)} />
            </Field>
            {!interview && (
              <Field label="Pass marks" htmlFor="t-pass" hint="Needed for module, coding and final tests">
                <Input id="t-pass" inputMode="decimal" value={passMarks} onChange={(e) => setPassMarks(e.target.value)} />
              </Field>
            )}
            <Field label="Closes (IST)" htmlFor="t-closes">
              <Input id="t-closes" type="datetime-local" value={closes} onChange={(e) => setCloses(e.target.value)} />
            </Field>
          </div>
          <Field label="Instructions" htmlFor="t-instructions">
            <Textarea id="t-instructions" rows={2} value={instructions} onChange={(e) => setInstructions(e.target.value)} />
          </Field>
        </div>
        <DialogFooter>
          <Button disabled={(!editing && !batchId) || !title || create.isPending} onClick={() => create.mutate(undefined)}>
            {editing ? "Save changes" : interview ? "Create interview" : "Create test"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function QuestionsDialog({ test, onClose }: { test: TestItem | null; onClose: () => void }) {
  const bank = useQuery({ queryKey: ["questions", "approved"], queryFn: () => assessmentsApi.questions({ status: "Approved" }), enabled: test !== null });
  const [chosen, setChosen] = useState<number[] | null>(null);
  const current = chosen ?? test?.questions?.map((q) => q.question_id) ?? [];
  const usable = (bank.data?.data ?? []).filter((q) => q.course.course_code === test?.batch.course_code);
  const save = useApiMutation(() => assessmentsApi.setQuestions(test!.test_id, current), {
    success: "Questions saved",
    invalidate: REFRESH,
    onSuccess: onClose,
  });
  return (
    <Dialog open={test !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Questions for {test?.title}</DialogTitle>
          <DialogDescription>Only approved questions of this course. Each question is frozen into the test as it is now.</DialogDescription>
        </DialogHeader>
        <QueryView query={bank} isEmpty={() => usable.length === 0} empty="No approved questions for this course yet.">
          {() => (
            <ul className="space-y-2">
              {usable.map((q) => (
                <li key={q.question_id}>
                  <label className="flex items-start gap-2 rounded-lg border p-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={current.includes(q.question_id)}
                      onChange={(e) => setChosen(e.target.checked ? [...current, q.question_id] : current.filter((id) => id !== q.question_id))}
                    />
                    <span>
                      <span className="font-mono text-xs">{q.question_code}</span> {q.stem}
                      <span className="ml-2 text-muted-foreground">
                        {q.question_type} · {q.marks} marks
                      </span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
        </QueryView>
        <DialogFooter>
          <Button disabled={save.isPending} onClick={() => save.mutate(undefined)}>
            Save {current.length} question{current.length === 1 ? "" : "s"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function TestBuilder() {
  const query = useQuery({ queryKey: ["tests", "list", "staff"], queryFn: () => assessmentsApi.tests() });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<TestItem | null>(null);
  const [selecting, setSelecting] = useState<number | null>(null);
  const detail = useQuery({ queryKey: ["tests", "detail", "builder", selecting], queryFn: () => assessmentsApi.test(selecting!), enabled: selecting !== null });
  const release = useApiMutation((t: TestItem) => assessmentsApi.releaseTest(t.test_id), {
    success: (t) => `${t.title} released`,
    next: "Students of the batch can see it and take it in its window.",
    invalidate: REFRESH,
  });
  const close = useApiMutation((t: TestItem) => assessmentsApi.closeTest(t.test_id), {
    success: (t) => `${t.title} closed`,
    next: "Attempts already submitted are kept and still need marking.",
    invalidate: REFRESH,
  });

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button onClick={() => setCreating(true)}>Build test</Button>
      </div>
      <QueryView
        query={query}
        isEmpty={(p) => p.data.filter((t) => t.kind !== "Mock interview").length === 0}
        empty="No tests yet. A test is built from approved questions in the question bank, then released to one of your batches."
        emptyAction={<Button onClick={() => setCreating(true)}>Build test</Button>}
      >
        {(page) => (
          <DataTable
            caption="Tests"
            rows={page.data.filter((t) => t.kind !== "Mock interview")}
            getKey={(t) => t.test_id}
            cols={[
              { h: "Title", c: (t) => <span className="font-medium">{t.title}</span> },
              { h: "Type", c: (t) => <Tag tone="info">{t.kind}</Tag> },
              { h: "Batch", c: (t) => <span className="font-mono text-xs">{t.batch.batch_code}</span> },
              { h: "Duration", c: (t) => (t.duration_minutes ? `${t.duration_minutes} min` : "Untimed") },
              { h: "Window", c: (t) => (t.opens_at || t.closes_at ? `${formatIst(t.opens_at)} → ${formatIst(t.closes_at)}` : "—") },
              { h: "State", c: (t) => <StatusBadge domain="test" code={t.status === "Available" ? "Released" : t.status} /> },
              { h: "What is left", c: (t) => (t.gaps?.length ? t.gaps.join("; ") : "Ready") },
              {
                h: "Actions",
                c: (t) => {
                  const draft = ["Configuration Pending", "Not Released"].includes(t.release_status);
                  return (
                    <div className="flex flex-wrap gap-2">
                      {t.can_manage && draft && (
                        <Button size="sm" variant="outline" onClick={() => setSelecting(t.test_id)}>
                          Questions ({t.question_count})
                        </Button>
                      )}
                      {t.can_manage && draft && (
                        <Button size="sm" variant="outline" onClick={() => setEditing(t)}>
                          Edit
                        </Button>
                      )}
                      {t.can_manage && t.release_status === "Not Released" && (
                        <ConfirmDialog
                          title={`Release ${t.title}?`}
                          consequence={`Students of ${t.batch.batch_code} will see this test${t.opens_at ? ` from ${formatIst(t.opens_at)}` : " now"} and can take it. After release the questions and settings are locked; only the instructions and the closing time can change.`}
                          confirmLabel="Release"
                          onConfirm={async () => void (await release.mutateAsync(t))}
                        >
                          <Button size="sm">Release</Button>
                        </ConfirmDialog>
                      )}
                      {t.can_manage && t.release_status === "Released" && (
                        <ConfirmDialog
                          title={`Close ${t.title}?`}
                          consequence="Students can no longer start this test. Attempts already submitted are kept, and you can still mark them. A closed test cannot be reopened."
                          confirmLabel="Close test"
                          destructive
                          onConfirm={async () => void (await close.mutateAsync(t))}
                        >
                          <Button size="sm" variant="outline">
                            Close
                          </Button>
                        </ConfirmDialog>
                      )}
                    </div>
                  );
                },
              },
            ]}
          />
        )}
      </QueryView>
      <TestDialog open={creating} onOpenChange={setCreating} />
      {editing && <TestDialog key={editing.test_id} open test={editing} onOpenChange={(open) => !open && setEditing(null)} />}
      <QuestionsDialog key={detail.data?.test_id} test={selecting !== null ? (detail.data ?? null) : null} onClose={() => setSelecting(null)} />
    </div>
  );
}
