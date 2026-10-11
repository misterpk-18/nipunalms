import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, type Slot, type TestItem } from "@/api/assessments";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { Field, NativeSelect } from "@/components/lms/forms";
import { DataTable, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { TestDialog } from "./test-builder";
import { formatIst, fromIstInput, istInputIn } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";

const REFRESH = [["tests"]];

function FeedbackDialog({ slot, onClose }: { slot: Slot | null; onClose: () => void }) {
  const [rating, setRating] = useState("3");
  const [strengths, setStrengths] = useState("");
  const [improvements, setImprovements] = useState("");
  const [next, setNext] = useState("");
  const complete = useApiMutation(() => assessmentsApi.completeSlot(slot!.slot_id, { rating: Number(rating), strengths, improvements, next_action: next }), {
    success: "Interview feedback recorded",
    invalidate: REFRESH,
    onSuccess: onClose,
  });
  return (
    <Dialog open={slot !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Interview feedback: {slot?.student?.full_name}</DialogTitle>
          <DialogDescription>Practice only. No marks and no placement promise.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Field label="Rating (1-5)" htmlFor="iv-rating">
            <NativeSelect
              id="iv-rating"
              value={rating}
              onChange={(e) => setRating(e.target.value)}
              options={[1, 2, 3, 4, 5].map((n) => ({ value: n, label: String(n) }))}
            />
          </Field>
          <Field label="Strengths" htmlFor="iv-strengths">
            <Textarea id="iv-strengths" rows={2} value={strengths} onChange={(e) => setStrengths(e.target.value)} />
          </Field>
          <Field label="Areas to improve" htmlFor="iv-improve">
            <Textarea id="iv-improve" rows={2} value={improvements} onChange={(e) => setImprovements(e.target.value)} />
          </Field>
          <Field label="Next practice action" htmlFor="iv-next">
            <Input id="iv-next" value={next} onChange={(e) => setNext(e.target.value)} />
          </Field>
        </div>
        <DialogFooter>
          <Button disabled={!strengths || !improvements || !next || complete.isPending} onClick={() => complete.mutate(undefined)}>
            Save feedback
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function InterviewTest({ test, title }: { test: TestItem; title: string }) {
  const testId = test.test_id;
  const [editing, setEditing] = useState(false);
  const slots = useQuery({ queryKey: ["tests", "slots", testId], queryFn: () => assessmentsApi.slots(testId) });
  const [start, setStart] = useState(istInputIn(48));
  const [minutes, setMinutes] = useState("30");
  const [feedback, setFeedback] = useState<Slot | null>(null);
  const offer = useApiMutation(
    () => {
      const begin = new Date(fromIstInput(start));
      return assessmentsApi.offerSlots(testId, [
        { starts_at: begin.toISOString(), ends_at: new Date(begin.getTime() + Number(minutes) * 60_000).toISOString() },
      ]);
    },
    { success: "Slot offered", invalidate: REFRESH },
  );
  const confirm = useApiMutation((s: Slot) => assessmentsApi.confirmSlot(s.slot_id), { success: "Slot confirmed; the student is told", invalidate: REFRESH });
  const cancel = useApiMutation((s: Slot) => assessmentsApi.cancelSlot(s.slot_id, "Cancelled by the trainer"), {
    success: "Slot cancelled",
    next: "A student who had booked it is told.",
    invalidate: REFRESH,
  });
  const release = useApiMutation(() => assessmentsApi.releaseTest(testId), {
    success: `${test.title} released`,
    next: "Students of the batch can now book one of your slots.",
    invalidate: REFRESH,
  });
  const close = useApiMutation(() => assessmentsApi.closeTest(testId), {
    success: `${test.title} closed`,
    next: "Students can no longer book. Confirmed interviews still go ahead.",
    invalidate: REFRESH,
  });
  const draft = ["Configuration Pending", "Not Released"].includes(test.release_status);

  return (
    <Section
      title={title}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge domain="test" code={test.status === "Available" ? "Released" : test.status} />
          {test.can_manage && draft && (
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              Edit
            </Button>
          )}
          {test.can_manage && test.release_status === "Not Released" && (
            <ConfirmDialog
              title={`Release ${test.title}?`}
              consequence={`Students of ${test.batch.batch_code} will see this interview and can book one of your open slots.`}
              confirmLabel="Release"
              onConfirm={async () => void (await release.mutateAsync(undefined))}
            >
              <Button size="sm">Release</Button>
            </ConfirmDialog>
          )}
          {test.can_manage && test.release_status === "Released" && (
            <ConfirmDialog
              title={`Close ${test.title}?`}
              consequence="Students can no longer book a slot. Interviews already confirmed still go ahead. A closed interview cannot be reopened."
              confirmLabel="Close interview"
              destructive
              onConfirm={async () => void (await close.mutateAsync(undefined))}
            >
              <Button size="sm" variant="outline">
                Close
              </Button>
            </ConfirmDialog>
          )}
        </div>
      }
    >
      {test.gaps && test.gaps.length > 0 && <p className="mb-2 text-sm text-muted-foreground">Before it can be released: {test.gaps.join("; ")}.</p>}
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <Field label="Slot starts (IST)" htmlFor={`slot-start-${testId}`}>
          <Input id={`slot-start-${testId}`} type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
        </Field>
        <Field label="Minutes" htmlFor={`slot-len-${testId}`}>
          <Input id={`slot-len-${testId}`} className="w-24" inputMode="numeric" value={minutes} onChange={(e) => setMinutes(e.target.value)} />
        </Field>
        <Button onClick={() => offer.mutate(undefined)} disabled={offer.isPending}>
          Offer slot
        </Button>
      </div>
      <QueryView query={slots} isEmpty={(s) => s.length === 0} empty="No slots offered yet.">
        {(rows) => (
          <DataTable
            caption="Interview slots"
            rows={rows}
            getKey={(s) => s.slot_id}
            cols={[
              { h: "Time", c: (s) => formatIst(s.starts_at) },
              { h: "Student", c: (s) => s.student?.full_name ?? "Open" },
              { h: "State", c: (s) => <StatusBadge domain="slot" code={s.status} /> },
              {
                h: "Actions",
                c: (s) => (
                  <div className="flex flex-wrap gap-2">
                    {s.status === "Slot Confirmation Pending" && (
                      <Button size="sm" onClick={() => confirm.mutate(s)}>
                        Confirm
                      </Button>
                    )}
                    {s.status === "Confirmed" && (
                      <Button size="sm" onClick={() => setFeedback(s)}>
                        Record feedback
                      </Button>
                    )}
                    {["Open", "Slot Confirmation Pending", "Confirmed"].includes(s.status) && (
                      <Button size="sm" variant="outline" onClick={() => cancel.mutate(s)}>
                        Cancel
                      </Button>
                    )}
                  </div>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <FeedbackDialog key={feedback?.slot_id} slot={feedback} onClose={() => setFeedback(null)} />
      {editing && <TestDialog open test={test} onOpenChange={(open) => !open && setEditing(false)} />}
    </Section>
  );
}

export function MockInterviews() {
  const [creating, setCreating] = useState(false);
  const query = useQuery({ queryKey: ["tests", "list", "staff"], queryFn: () => assessmentsApi.tests() });
  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button onClick={() => setCreating(true)}>New mock interview</Button>
      </div>
      <QueryView
        query={query}
        isEmpty={(p) => p.data.filter((t) => t.kind === "Mock interview").length === 0}
        empty="No mock interviews yet. Create one for a batch, then offer time slots for students to book."
        emptyAction={<Button onClick={() => setCreating(true)}>New mock interview</Button>}
      >
        {(page) => (
          <div className="space-y-4">
            {page.data
              .filter((t) => t.kind === "Mock interview")
              .map((t) => (
                <InterviewTest key={t.test_id} test={t} title={`${t.title} · ${t.batch.batch_code}`} />
              ))}
          </div>
        )}
      </QueryView>
      <TestDialog open={creating} onOpenChange={setCreating} fixedKind="Mock interview" />
    </div>
  );
}
