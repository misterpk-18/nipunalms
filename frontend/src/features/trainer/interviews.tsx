import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, type Slot } from "@/api/assessments";
import { Field, NativeSelect } from "@/components/lms/forms";
import { DataTable, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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

function InterviewTest({ testId, title }: { testId: number; title: string }) {
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
    invalidate: REFRESH,
  });

  return (
    <Section title={title}>
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
              { h: "State", c: (s) => <StatusBadge>{s.status}</StatusBadge> },
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
    </Section>
  );
}

export function MockInterviews() {
  const query = useQuery({ queryKey: ["tests", "list", "interviews"], queryFn: () => assessmentsApi.tests({ kind: "Mock interview" }) });
  return (
    <QueryView query={query} isEmpty={(p) => p.data.length === 0} empty="No mock interviews for your batches.">
      {(page) => (
        <div className="space-y-4">
          {page.data.map((t) => (
            <InterviewTest key={t.test_id} testId={t.test_id} title={`${t.title} · ${t.batch.batch_code}`} />
          ))}
        </div>
      )}
    </QueryView>
  );
}
