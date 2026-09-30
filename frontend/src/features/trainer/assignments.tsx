import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, batchesForAuthoring, ASSIGNMENT_KINDS, AI_RULES, type Assignment } from "@/api/assessments";
import { ConfirmAction, DataTable, PageHead, QueryView, StatusBadge } from "@/components/lms/ui";
import { Field, NativeSelect } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { formatIst, fromIstInput, istInputIn } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";

const REFRESH = [["assignments"]];

function NewAssignmentDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const batches = useQuery({ queryKey: ["batches", "authoring"], queryFn: batchesForAuthoring, enabled: open });
  const [batchId, setBatchId] = useState("");
  const [topicId, setTopicId] = useState("");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<string>(ASSIGNMENT_KINDS[0]);
  const [brief, setBrief] = useState("");
  const [required, setRequired] = useState(true);
  const [maxMarks, setMaxMarks] = useState("20");
  const [due, setDue] = useState(istInputIn(24 * 7));
  const [aiRule, setAiRule] = useState<string>(AI_RULES[0]);
  const options = useQuery({
    queryKey: ["curriculum-options", batchId],
    queryFn: () => assessmentsApi.curriculum(Number(batchId)),
    enabled: open && batchId !== "",
  });

  const create = useApiMutation(
    (release: boolean) =>
      assessmentsApi.createAssignment({
        batch_id: Number(batchId),
        topic_id: topicId ? Number(topicId) : null,
        title,
        kind,
        brief,
        is_required: required,
        max_marks: Number(maxMarks),
        due_at: fromIstInput(due),
        ai_use_rule: aiRule,
        release_now: release,
      }),
    {
      success: (a) => (a.status === "Released" ? "Assignment released to the batch" : "Draft saved"),
      invalidate: REFRESH,
      onSuccess: () => onOpenChange(false),
    },
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New assignment</DialogTitle>
          <DialogDescription>Linked to a curriculum topic; students allocated to the batch see it once released.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Field label="Batch" htmlFor="asg-batch">
            <NativeSelect
              id="asg-batch"
              value={batchId}
              onChange={(e) => {
                setBatchId(e.target.value);
                setTopicId("");
              }}
              placeholder="Select a batch"
              options={(batches.data?.data ?? []).map((b) => ({ value: b.batch_id, label: `${b.batch_code} · ${b.course.title}` }))}
            />
          </Field>
          <Field label="Curriculum topic" htmlFor="asg-topic">
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
            <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} /> Required (counts towards the curriculum)
          </label>
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" disabled={!batchId || !title || !brief || create.isPending} onClick={() => create.mutate(false)}>
            Save draft
          </Button>
          <Button disabled={!batchId || !title || !brief || create.isPending} onClick={() => create.mutate(true)}>
            Create and release
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
          <DialogDescription>Newest version per student. Review them in Reviews.</DialogDescription>
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
                { h: "State", c: (s) => <StatusBadge>{s.review ? s.review.outcome : s.review_started_at ? "Under Review" : "Submitted"}</StatusBadge> },
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
  const release = useApiMutation((a: Assignment) => assessmentsApi.releaseAssignment(a.assignment_id), {
    success: "Released to the batch",
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
        description="Create and release curriculum-linked assignments for the batches you teach."
        actions={<Button onClick={() => setCreating(true)}>New assignment</Button>}
      />
      <QueryView query={query} isEmpty={(p) => p.data.length === 0} empty="No assignments yet.">
        {(page) => (
          <DataTable
            caption="Assignments"
            rows={page.data}
            getKey={(a) => a.assignment_id}
            cols={[
              { h: "Title", c: (a) => <span className="font-medium">{a.title}</span> },
              { h: "Batch", c: (a) => <span className="font-mono text-xs">{a.batch.batch_code}</span> },
              { h: "Topic", c: (a) => a.topic?.title ?? "—" },
              { h: "Type", c: (a) => <StatusBadge tone={a.is_required ? "info" : "neutral"}>{a.is_required ? "Required" : "Optional"}</StatusBadge> },
              { h: "Due", c: (a) => formatIst(a.due_at) },
              { h: "State", c: (a) => <StatusBadge>{a.status}</StatusBadge> },
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
                      <Button size="sm" onClick={() => release.mutate(a)}>
                        Release
                      </Button>
                    )}
                    {a.can_manage && a.status === "Released" && (
                      <Button size="sm" variant="outline" onClick={() => setExtending(a)}>
                        Extend due
                      </Button>
                    )}
                    {a.can_manage && a.status !== "Withdrawn" && (
                      <ConfirmAction
                        title="Withdraw this assignment?"
                        description="Students no longer see it. Submissions and reviews already recorded are kept."
                        destructive
                        confirmLabel="Withdraw"
                        onConfirm={async () => void (await withdraw.mutateAsync(a))}
                      >
                        <Button size="sm" variant="outline">
                          Withdraw
                        </Button>
                      </ConfirmAction>
                    )}
                  </div>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <NewAssignmentDialog open={creating} onOpenChange={setCreating} />
      <SubmissionsDialog assignment={viewing} onClose={() => setViewing(null)} />
      <ExtendDialog key={extending?.assignment_id} assignment={extending} onClose={() => setExtending(null)} />
    </div>
  );
}
