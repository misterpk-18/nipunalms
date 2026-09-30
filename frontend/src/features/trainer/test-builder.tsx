import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, batchesForAuthoring, TEST_KINDS, type TestItem } from "@/api/assessments";
import { Field, NativeSelect } from "@/components/lms/forms";
import { DataTable, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { formatIst, fromIstInput, istInputIn } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";

const REFRESH = [["tests"]];

function NewTestDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const batches = useQuery({ queryKey: ["batches", "authoring"], queryFn: batchesForAuthoring, enabled: open });
  const [batchId, setBatchId] = useState("");
  const [kind, setKind] = useState<string>("Practice quiz");
  const [title, setTitle] = useState("");
  const [duration, setDuration] = useState("");
  const [passMarks, setPassMarks] = useState("");
  const [closes, setCloses] = useState(istInputIn(24 * 7));
  const [instructions, setInstructions] = useState("");
  const create = useApiMutation(
    () =>
      assessmentsApi.createTest({
        batch_id: Number(batchId),
        kind,
        title,
        instructions: instructions || undefined,
        ...(duration ? { duration_minutes: Number(duration) } : {}),
        ...(passMarks ? { pass_marks: Number(passMarks) } : {}),
        closes_at: closes ? fromIstInput(closes) : null,
      }),
    {
      success: (t) => `${t.test_code} created`,
      invalidate: REFRESH,
      onSuccess: () => {
        onOpenChange(false);
        setTitle("");
      },
    },
  );
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Build test</DialogTitle>
          <DialogDescription>Defaults follow the type (module 30 min, final 60, coding 90). Then select questions and release.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Field label="Batch" htmlFor="t-batch">
            <NativeSelect
              id="t-batch"
              value={batchId}
              onChange={(e) => setBatchId(e.target.value)}
              placeholder="Select a batch"
              options={(batches.data?.data ?? []).map((b) => ({ value: b.batch_id, label: `${b.batch_code} · ${b.course.title}` }))}
            />
          </Field>
          <Field label="Type" htmlFor="t-kind">
            <NativeSelect id="t-kind" value={kind} onChange={(e) => setKind(e.target.value)} options={TEST_KINDS.map((k) => ({ value: k, label: k }))} />
          </Field>
          <Field label="Title" htmlFor="t-title">
            <Input id="t-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Duration (min)" htmlFor="t-duration" hint="Blank = type default">
              <Input id="t-duration" inputMode="numeric" value={duration} onChange={(e) => setDuration(e.target.value)} />
            </Field>
            <Field label="Pass marks" htmlFor="t-pass" hint="Required for formal tests">
              <Input id="t-pass" inputMode="decimal" value={passMarks} onChange={(e) => setPassMarks(e.target.value)} />
            </Field>
            <Field label="Closes (IST)" htmlFor="t-closes">
              <Input id="t-closes" type="datetime-local" value={closes} onChange={(e) => setCloses(e.target.value)} />
            </Field>
          </div>
          <Field label="Instructions" htmlFor="t-instructions">
            <Textarea id="t-instructions" rows={2} value={instructions} onChange={(e) => setInstructions(e.target.value)} />
          </Field>
        </div>
        <DialogFooter>
          <Button disabled={!batchId || !title || create.isPending} onClick={() => create.mutate(undefined)}>
            Create test
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
  const [selecting, setSelecting] = useState<number | null>(null);
  const detail = useQuery({ queryKey: ["tests", "detail", "builder", selecting], queryFn: () => assessmentsApi.test(selecting!), enabled: selecting !== null });
  const release = useApiMutation((t: TestItem) => assessmentsApi.releaseTest(t.test_id), { success: "Test released", invalidate: REFRESH });
  const close = useApiMutation((t: TestItem) => assessmentsApi.closeTest(t.test_id), { success: "Test closed", invalidate: REFRESH });

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button onClick={() => setCreating(true)}>Build test</Button>
      </div>
      <QueryView query={query} isEmpty={(p) => p.data.length === 0} empty="No tests yet.">
        {(page) => (
          <DataTable
            caption="Tests"
            rows={page.data}
            getKey={(t) => t.test_id}
            cols={[
              { h: "Title", c: (t) => <span className="font-medium">{t.title}</span> },
              { h: "Type", c: (t) => <StatusBadge tone="info">{t.kind}</StatusBadge> },
              { h: "Batch", c: (t) => <span className="font-mono text-xs">{t.batch.batch_code}</span> },
              { h: "Duration", c: (t) => (t.duration_minutes ? `${t.duration_minutes} min` : "Untimed") },
              { h: "Window", c: (t) => (t.opens_at || t.closes_at ? `${formatIst(t.opens_at)} → ${formatIst(t.closes_at)}` : "—") },
              { h: "State", c: (t) => <StatusBadge>{t.status}</StatusBadge> },
              { h: "Missing", c: (t) => (t.gaps?.length ? t.gaps.join("; ") : "Ready") },
              {
                h: "Actions",
                c: (t) => (
                  <div className="flex flex-wrap gap-2">
                    {t.can_manage && t.kind !== "Mock interview" && ["Configuration Pending", "Not Released"].includes(t.release_status) && (
                      <Button size="sm" variant="outline" onClick={() => setSelecting(t.test_id)}>
                        Questions ({t.question_count})
                      </Button>
                    )}
                    {t.can_manage && t.release_status === "Not Released" && (
                      <Button size="sm" onClick={() => release.mutate(t)}>
                        Release
                      </Button>
                    )}
                    {t.can_manage && t.release_status === "Released" && (
                      <Button size="sm" variant="outline" onClick={() => close.mutate(t)}>
                        Close
                      </Button>
                    )}
                  </div>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <NewTestDialog open={creating} onOpenChange={setCreating} />
      <QuestionsDialog key={detail.data?.test_id} test={selecting !== null ? (detail.data ?? null) : null} onClose={() => setSelecting(null)} />
    </div>
  );
}
