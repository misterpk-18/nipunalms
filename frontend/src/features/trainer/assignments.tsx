import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, batchesForAuthoring, ASSIGNMENT_KINDS, AI_RULES, type Assignment } from "@/api/assessments";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { DataTable, PageHead, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { Field, NativeSelect } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { formatIst, fromIstInput, istInputIn, toIstInput } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";

const REFRESH = [["assignments"]];

/** Write a new assignment, or (with `assignment`) edit a draft that has not been released. */
function AssignmentDialog({ open, onOpenChange, assignment }: { open: boolean; onOpenChange: (open: boolean) => void; assignment?: Assignment | undefined }) {
  const editing = assignment !== undefined;
  const batches = useQuery({ queryKey: ["batches", "authoring"], queryFn: batchesForAuthoring, enabled: open && !editing });
  const [batchId, setBatchId] = useState(assignment ? String(assignment.batch.batch_id) : "");
  const [topicId, setTopicId] = useState(assignment?.topic ? String(assignment.topic.topic_id) : "");
  const [title, setTitle] = useState(assignment?.title ?? "");
  const [kind, setKind] = useState<string>(assignment?.kind ?? ASSIGNMENT_KINDS[0]);
  const [brief, setBrief] = useState(assignment?.brief ?? "");
  const [required, setRequired] = useState(assignment?.is_required ?? true);
  const [maxMarks, setMaxMarks] = useState(assignment ? String(Number(assignment.max_marks)) : "20");
  const [due, setDue] = useState(assignment ? toIstInput(assignment.due_at) : istInputIn(24 * 7));
  const [aiRule, setAiRule] = useState<string>(assignment?.ai_use_rule ?? AI_RULES[0]);
  const options = useQuery({
    queryKey: ["curriculum-options", batchId],
    queryFn: () => assessmentsApi.curriculum(Number(batchId)),
    enabled: open && batchId !== "",
  });

  const fields = {
    topic_id: topicId ? Number(topicId) : null,
    title,
    kind,
    brief,
    is_required: required,
    max_marks: Number(maxMarks),
    due_at: fromIstInput(due),
    ai_use_rule: aiRule,
  };
  const create = useApiMutation(
    (release: boolean) =>
      editing
        ? assessmentsApi
            .updateAssignment(assignment.assignment_id, fields)
            .then(async (updated) => (release ? assessmentsApi.releaseAssignment(updated.assignment_id) : updated))
        : assessmentsApi.createAssignment({ batch_id: Number(batchId), ...fields, release_now: release }),
    {
      success: (a) => (a.status === "Released" ? "Assignment released to the batch" : "Draft saved"),
      next: (a) => (a.status === "Released" ? "Students of the batch can see it and hand in work." : "Release it when it is ready."),
      invalidate: REFRESH,
      onSuccess: () => onOpenChange(false),
    },
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editing ? `Edit ${assignment.title}` : "New assignment"}</DialogTitle>
          <DialogDescription>
            {editing
              ? "Change this draft. Students cannot see it until you release it."
              : "Linked to a course topic; students allocated to the batch see it once released."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Field label="Batch" htmlFor="asg-batch">
            <NativeSelect
              id="asg-batch"
              value={batchId}
              disabled={editing}
              onChange={(e) => {
                setBatchId(e.target.value);
                setTopicId("");
              }}
              placeholder="Select a batch"
              options={
                editing
                  ? [{ value: assignment.batch.batch_id, label: assignment.batch.batch_code }]
                  : (batches.data?.data ?? []).map((b) => ({ value: b.batch_id, label: `${b.batch_code} · ${b.course.title}` }))
              }
            />
          </Field>
          <Field label="Course topic" htmlFor="asg-topic">
            <NativeSelect
              id="asg-topic"
              value={topicId}
              onChange={(e) => setTopicId(e.target.value)}
              placeholder="Not linked to a topic"
              options={(options.data ?? []).flatMap((m) => m.topics.map((t) => ({ value: t.topic_id, label: `${m.title} → ${t.title}` })))}
            />
          </Field>
          <Field label="Title" htmlFor="asg-title">
            <Input id="asg-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Type" htmlFor="asg-kind">
              <NativeSelect
                id="asg-kind"
                value={kind}
                onChange={(e) => setKind(e.target.value)}
                options={ASSIGNMENT_KINDS.map((k) => ({ value: k, label: k }))}
              />
            </Field>
            <Field label="Maximum marks" htmlFor="asg-marks">
              <Input id="asg-marks" inputMode="numeric" value={maxMarks} onChange={(e) => setMaxMarks(e.target.value)} />
            </Field>
            <Field label="Due (IST)" htmlFor="asg-due">
              <Input id="asg-due" type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
            </Field>
            <Field label="AI use rule" htmlFor="asg-ai">
              <NativeSelect id="asg-ai" value={aiRule} onChange={(e) => setAiRule(e.target.value)} options={AI_RULES.map((k) => ({ value: k, label: k }))} />
            </Field>
          </div>
          <Field label="Brief" htmlFor="asg-brief">
            <Textarea id="asg-brief" rows={4} value={brief} onChange={(e) => setBrief(e.target.value)} />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} /> Required (counts towards the course)
          </label>
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" disabled={!batchId || !title || !brief || create.isPending} onClick={() => create.mutate(false)}>
            {editing ? "Save changes" : "Save draft"}
          </Button>
          <Button disabled={!batchId || !title || !brief || create.isPending} onClick={() => create.mutate(true)}>
            {editing ? "Save and release" : "Create and release"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SubmissionsDialog({ assignment, onClose }: { assignment: Assignment | null; onClose: () => void }) {
  const query = useQuery({
    queryKey: ["submissions", "assignment", assignment?.assignment_id],
    queryFn: () => assessmentsApi.submissions({ assignment_id: assignment!.assignment_id }),
    enabled: assignment !== null,
  });
  return (
    <Dialog open={assignment !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{assignment?.title}: submissions</DialogTitle>
          <DialogDescription>Newest version per student. Mark them in To grade.</DialogDescription>
        </DialogHeader>
        <QueryView query={query} isEmpty={(p) => p.data.length === 0} empty="No submissions yet.">
          {(page) => (
            <DataTable
              caption="Submissions"
              rows={page.data}
              getKey={(s) => s.submission_id}
              cols={[
                { h: "Student", c: (s) => s.student.full_name },
                { h: "Version", c: (s) => `v${s.version_no}${s.is_late ? " (late)" : ""}` },
                { h: "Submitted", c: (s) => formatIst(s.submitted_at) },
                { h: "State", c: (s) => <StatusBadge domain="work" code={s.review ? s.review.outcome : s.review_started_at ? "Under Review" : "Submitted"} /> },
              ]}
            />
          )}
        </QueryView>
      </DialogContent>
    </Dialog>
  );
}

function ExtendDialog({ assignment, onClose }: { assignment: Assignment | null; onClose: () => void }) {
  const [due, setDue] = useState("");
  const extend = useApiMutation(() => assessmentsApi.updateAssignment(assignment!.assignment_id, { due_at: fromIstInput(due) }), {
    success: "Due time extended; students were told",
    invalidate: REFRESH,
    onSuccess: onClose,
  });
  return (
    <Dialog open={assignment !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Extend the due time</DialogTitle>
          <DialogDescription>Currently {formatIst(assignment?.due_at)}. A due time can only be moved later after release.</DialogDescription>
        </DialogHeader>
        <Field label="New due time (IST)" htmlFor="ext-due">
          <Input id="ext-due" type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
        </Field>
        <DialogFooter>
          <Button disabled={!due || extend.isPending} onClick={() => extend.mutate(undefined)}>
            Extend
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function TrainerAssignments() {
  const query = useQuery({ queryKey: ["assignments", "list", "staff"], queryFn: () => assessmentsApi.assignments() });
  const [creating, setCreating] = useState(false);
  const [viewing, setViewing] = useState<Assignment | null>(null);
  const [extending, setExtending] = useState<Assignment | null>(null);
  const [editing, setEditing] = useState<Assignment | null>(null);
  const release = useApiMutation((a: Assignment) => assessmentsApi.releaseAssignment(a.assignment_id), {
    success: (a) => `${a.title} released to the batch`,
    next: "Students of the batch can see it and hand in work.",
    invalidate: REFRESH,
  });
  const withdraw = useApiMutation((a: Assignment) => assessmentsApi.withdrawAssignment(a.assignment_id, "Withdrawn by the trainer"), {
    success: "Assignment withdrawn",
    invalidate: REFRESH,
  });

  return (
    <div className="mx-auto max-w-6xl">
      <PageHead
        title="Assignments"
        description="Write assignments for your batches, release them, and see who has handed in. Marking happens in To grade."
        actions={<Button onClick={() => setCreating(true)}>New assignment</Button>}
      />
      <QueryView
        query={query}
        isEmpty={(p) => p.data.length === 0}
        empty="No assignments yet. Write one for a batch; students see it only once you release it."
        emptyAction={<Button onClick={() => setCreating(true)}>New assignment</Button>}
      >
        {(page) => (
          <DataTable
            caption="Assignments"
            rows={page.data}
            getKey={(a) => a.assignment_id}
            cols={[
              { h: "Title", c: (a) => <span className="font-medium">{a.title}</span> },
              { h: "Batch", c: (a) => <span className="font-mono text-xs">{a.batch.batch_code}</span> },
              { h: "Topic", c: (a) => a.topic?.title ?? "—" },
              { h: "Type", c: (a) => <Tag tone={a.is_required ? "info" : "neutral"}>{a.is_required ? "Required" : "Optional"}</Tag> },
              { h: "Due", c: (a) => formatIst(a.due_at) },
              { h: "State", c: (a) => <StatusBadge domain="assignment" code={a.status} /> },
              {
                h: "Submissions",
                c: (a) => (a.counts ? `${a.counts.submitted} submitted · ${a.counts.awaiting_review} to review` : "—"),
              },
              {
                h: "Actions",
                c: (a) => (
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => setViewing(a)}>
                      Submissions
                    </Button>
                    {a.can_manage && a.status === "Draft" && (
                      <Button size="sm" variant="outline" onClick={() => setEditing(a)}>
                        Edit
                      </Button>
                    )}
                    {a.can_manage && a.status === "Draft" && (
                      <ConfirmDialog
                        title={`Release ${a.title}?`}
                        consequence={`Students of ${a.batch.batch_code} will see it now and can hand in work. It is due ${formatIst(a.due_at)}.`}
                        confirmLabel="Release"
                        onConfirm={async () => void (await release.mutateAsync(a))}
                      >
                        <Button size="sm">Release</Button>
                      </ConfirmDialog>
                    )}
                    {a.can_manage && a.status === "Released" && (
                      <Button size="sm" variant="outline" onClick={() => setExtending(a)}>
                        Extend due
                      </Button>
                    )}
                    {a.can_manage && a.status !== "Withdrawn" && (
                      <ConfirmDialog
                        title="Withdraw this assignment?"
                        consequence="Students will no longer see it. Submissions and reviews already recorded are kept."
                        destructive
                        confirmLabel="Withdraw"
                        onConfirm={async () => void (await withdraw.mutateAsync(a))}
                      >
                        <Button size="sm" variant="outline">
                          Withdraw
                        </Button>
                      </ConfirmDialog>
                    )}
                  </div>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <AssignmentDialog open={creating} onOpenChange={setCreating} />
      {editing && <AssignmentDialog key={editing.assignment_id} open assignment={editing} onOpenChange={(open) => !open && setEditing(null)} />}
      <SubmissionsDialog assignment={viewing} onClose={() => setViewing(null)} />
      <ExtendDialog key={extending?.assignment_id} assignment={extending} onClose={() => setExtending(null)} />
    </div>
  );
}
