/** Enrolments waiting for a batch, with the batch allocation review shown before anyone is allocated. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi, type EnrolmentRow } from "@/api/delivery";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field, NativeSelect } from "@/components/lms/forms";
import { DataTable, Note, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { mono, useCanManage } from "@/features/shared/delivery-ui";
import { useDelivery } from "@/features/shared/sessions";
import { CheckList } from "./batch-panel";

function AllocateDialog({ row }: { row: EnrolmentRow }) {
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState<number | null>(null);
  const batchId = chosen ?? row.open_batches?.[0]?.batch_id ?? 0;
  const [reason, setReason] = useState("");
  const [ack, setAck] = useState(false);
  const review = useQuery({
    queryKey: ["delivery", "review", batchId, row.enrolment_id],
    queryFn: () => deliveryApi.review(batchId, row.enrolment_id),
    enabled: open && batchId > 0,
  });
  const allocate = useDelivery(
    (v: { batch_id: number }) => deliveryApi.allocate(v.batch_id, { enrolment_id: row.enrolment_id, reason: reason || undefined, acknowledge_warnings: ack }),
    "Student allocated — they have been told",
  );
  const blocked = review.data?.result === "Blocked";
  const needsAck = review.data?.result === "Review needed" && !ack;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">Review &amp; allocate</Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Batch allocation review — {row.student.full_name}</DialogTitle>
          <DialogDescription>
            {row.enrolment_code} · {row.course.course_code} · {row.kind}
          </DialogDescription>
        </DialogHeader>
        {(row.open_batches ?? []).length === 0 ? (
          <Note>No open batch exists for this course at {row.service_branch.branch_name}. Create a batch first.</Note>
        ) : (
          <div className="space-y-3">
            <Field label="Batch" htmlFor="alloc-batch">
              <NativeSelect
                id="alloc-batch"
                options={(row.open_batches ?? []).map((b) => ({ value: b.batch_id, label: `${b.batch_code} (${b.state}, capacity ${b.capacity})` }))}
                value={batchId}
                onChange={(e) => {
                  setChosen(Number(e.target.value));
                  setAck(false);
                }}
              />
            </Field>
            <QueryView query={review}>
              {(r) => (
                <>
                  <CheckList checks={r.checks} />
                  <p className="text-sm">
                    Result: <StatusBadge>{r.result}</StatusBadge>
                    {r.recovery_owner && (
                      <span className="ml-2 text-muted-foreground">Recovery owner: {r.recovery_owner}. Paid receipt and Admission are preserved.</span>
                    )}
                  </p>
                  {r.warnings.length > 0 && (
                    <label className="flex items-start gap-2 text-sm">
                      <input type="checkbox" className="mt-1" checked={ack} onChange={(e) => setAck(e.target.checked)} /> I have reviewed the warnings and want
                      to allocate anyway
                    </label>
                  )}
                </>
              )}
            </QueryView>
            <Field label="Reason / note (optional)" htmlFor="alloc-reason">
              <Input id="alloc-reason" value={reason} onChange={(e) => setReason(e.target.value)} />
            </Field>
            <p className="text-xs text-muted-foreground">
              Milestones stay separate: accepted delivery plan → Admission → batch allocation → Joining Date (first confirmed regular class; a demo does not
              count).
            </p>
            <Button
              disabled={!review.data || blocked || needsAck || allocate.isPending}
              onClick={() => allocate.mutate({ batch_id: batchId }, { onSuccess: () => setOpen(false) })}
            >
              Allocate
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function AllocationQueue({ branchId }: { branchId?: string }) {
  const manager = useCanManage();
  const query = useQuery({ queryKey: ["delivery", "queue", branchId], queryFn: () => deliveryApi.allocationQueue({ branch_id: branchId || undefined }) });
  return (
    <Section title="Allocation queue — admitted students waiting for a batch">
      <QueryView query={query}>
        {(page) => (
          <DataTable
            caption="Allocation queue"
            rows={page.data}
            getKey={(r) => r.enrolment_id}
            empty="No enrolment is waiting for a batch."
            cols={[
              { h: "Student", c: (r) => `${r.student.full_name} (${r.student.student_code})` },
              {
                h: "Enrolment",
                c: (r) => (
                  <>
                    {mono(r.enrolment_code)}
                    <div className="text-xs text-muted-foreground">
                      {r.kind} · {r.mode}
                    </div>
                  </>
                ),
              },
              { h: "Course", c: (r) => `${r.course.course_code} — ${r.course.title}` },
              { h: "Branch", c: (r) => r.service_branch.branch_name },
              { h: "Waiting", c: (r) => `${r.waiting_days ?? 0} day(s)` },
              { h: "Open batches", c: (r) => (r.open_batches?.length ? r.open_batches.map((b) => b.batch_code).join(", ") : "None") },
              ...(manager ? [{ h: "Action", c: (r: EnrolmentRow) => <AllocateDialog row={r} /> }] : []),
            ]}
          />
        )}
      </QueryView>
    </Section>
  );
}
