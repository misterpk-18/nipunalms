/** The Recovery requests and Corrections tabs: each decision says what it will change, and a rejection always asks for a reason. */
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { attendanceApi, attendanceKeys, type CorrectionRow, type Recovery } from "@/api/attendance";
import { useAuth } from "@/auth/auth";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { DataTable, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FormDialog } from "@/features/shared/attendance-parts";
import { fmtDate } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { Pager } from "@/features/shared/pager";

const PER_PAGE = 20;
const done = [attendanceKeys.all, ["progress"], ["completion"], ["certificates"], ["nav"], ["branch"]];
const classText = (s: { title: string; starts_at: string }) => `${s.title} on ${fmtDate(s.starts_at)}`;

// ---------------------------------------------------------------- recovery requests

function ApproveRecovery({ recovery, busy, onApprove }: { recovery: Recovery; busy: boolean; onApprove: (date: string) => Promise<unknown> }) {
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState("");
  const first = recovery.student.full_name.split(" ")[0];
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button size="sm" onClick={() => setOpen(true)} aria-label={`Approve recovery for ${recovery.student.full_name}`}>
        Approve
      </Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{`Approve the recovery for ${recovery.student.full_name}?`}</DialogTitle>
          <DialogDescription>
            {`${recovery.student.full_name} will be told they can make up ${classText(recovery.session)}${date ? ` by ${fmtDate(date)}` : ""}.`}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-1">
          <Label htmlFor="recovery-date">Make up by (optional)</Label>
          <Input id="recovery-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          <p className="text-xs text-muted-foreground">{first} sees this date in their attendance. Leave it empty to give no deadline.</p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            disabled={busy}
            onClick={() =>
              void onApprove(date).then(
                () => setOpen(false),
                () => undefined,
              )
            }
          >
            Approve recovery
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function RecoveriesTab({ branchId }: { branchId: number | null }) {
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: [...attendanceKeys.recoveries({ status: "Requested", page, branchId })],
    queryFn: () => attendanceApi.recoveries({ status: "Requested", page, per_page: PER_PAGE }),
    placeholderData: keepPreviousData,
  });
  const decide = useApiMutation(
    (v: { recovery: Recovery; decision: "Approved" | "Rejected"; note?: string; target?: string }) =>
      attendanceApi.decideRecovery(v.recovery.recovery_id, { decision: v.decision, decision_note: v.note, target_date: v.target || undefined }),
    {
      success: (r) => (r.status === "Approved" ? `Recovery approved for ${r.student.full_name}` : `Recovery not approved for ${r.student.full_name}`),
      next: (r) => (r.status === "Approved" ? "The student has been told they can make up the class." : "The student has been told, with your reason."),
      invalidate: done,
    },
  );
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Students who missed a class and asked to make it up. Approve to let them, or say why not.</p>
      <QueryView
        query={query}
        isEmpty={(r) => r.data.length === 0}
        empty="No recovery request is waiting. When a student or trainer asks to make up a missed class, it appears here."
      >
        {(result) => (
          <div className="space-y-3">
            <DataTable
              caption="Recovery requests"
              rows={result.data}
              getKey={(r) => r.recovery_id}
              cols={[
                { h: "Student", c: (r) => r.student.full_name },
                { h: "Missed class", c: (r) => `${r.session.title} · ${fmtDate(r.session.starts_at)}` },
                { h: "How", c: (r) => r.method },
                { h: "Reason", c: (r) => `${r.reason} (${r.requested_by.full_name})` },
                { h: "Status", c: (r) => <StatusBadge domain="approval" code={r.status} /> },
                {
                  h: "Decision",
                  c: (r) => (
                    <div className="flex flex-wrap gap-2">
                      <ApproveRecovery
                        recovery={r}
                        busy={decide.isPending}
                        onApprove={(target) => decide.mutateAsync({ recovery: r, decision: "Approved", target })}
                      />
                      <FormDialog
                        trigger={
                          <Button size="sm" variant="outline" aria-label={`Reject recovery for ${r.student.full_name}`}>
                            Reject
                          </Button>
                        }
                        title={`Reject the recovery for ${r.student.full_name}?`}
                        description={`${r.student.full_name} will be told this recovery was not approved, and sees your reason.`}
                        submitLabel="Reject recovery"
                        destructive
                        fields={[{ name: "note", label: "Reason", kind: "textarea", required: true }]}
                        onSubmit={(v) => decide.mutateAsync({ recovery: r, decision: "Rejected", note: v["note"] })}
                      />
                    </div>
                  ),
                },
              ]}
            />
            <Pager meta={result.meta} onPage={setPage} noun="requests" />
          </div>
        )}
      </QueryView>
    </div>
  );
}

// ---------------------------------------------------------------- corrections

function CorrectionDecision({
  correction,
  busy,
  decide,
}: {
  correction: CorrectionRow;
  busy: boolean;
  decide: (c: CorrectionRow, decision: "Approved" | "Rejected", note?: string) => Promise<unknown>;
}) {
  const { profile } = useAuth();
  if (correction.can_decide === false) {
    const mine = correction.requested_by.user_id === profile?.user.user_id;
    return (
      <p className="max-w-56 text-sm text-muted-foreground">
        {mine ? "You asked for this change, so someone else decides" : "Decided by the Founder or a Super Admin"}
      </p>
    );
  }
  const from = correction.previous_status ?? "Not yet marked";
  const name = correction.student.full_name;
  return (
    <div className="flex flex-wrap gap-2">
      <ConfirmDialog
        title={`Approve this correction for ${name}?`}
        consequence={`The attendance entry for ${name} on ${classText(correction.session)} changes from ${from} to ${correction.requested_status} and their attendance figure is recalculated.`}
        confirmLabel="Approve correction"
        onConfirm={() => decide(correction, "Approved")}
      >
        <Button size="sm" disabled={busy} aria-label={`Approve correction for ${name}`}>
          Approve
        </Button>
      </ConfirmDialog>
      <FormDialog
        trigger={
          <Button size="sm" variant="outline" aria-label={`Reject correction for ${name}`}>
            Reject
          </Button>
        }
        title={`Reject this correction for ${name}?`}
        description={`The entry stays as ${from}. The person who asked is told, with your reason.`}
        submitLabel="Reject correction"
        destructive
        fields={[{ name: "note", label: "Reason", kind: "textarea", required: true }]}
        onSubmit={(v) => decide(correction, "Rejected", v["note"])}
      />
    </div>
  );
}

export function CorrectionsTab({ branchId }: { branchId: number | null }) {
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: [...attendanceKeys.corrections({ status: "Pending", page, branchId })],
    queryFn: () => attendanceApi.branchCorrections({ status: "Pending", page, per_page: PER_PAGE }),
    placeholderData: keepPreviousData,
  });
  const decide = useApiMutation(
    (v: { correction: CorrectionRow; decision: "Approved" | "Rejected"; note?: string }) =>
      attendanceApi.decideCorrection(v.correction.correction_id, { decision: v.decision, decision_note: v.note }),
    {
      success: (c) => (c.status === "Approved" ? "Correction approved" : "Correction not approved"),
      next: (c) =>
        c.status === "Approved"
          ? "The entry is changed and the attendance figure is recalculated."
          : "The entry stays as it was. The person who asked has been told.",
      invalidate: done,
    },
  );
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Mistakes in a marked class that a student or trainer wants changed. You cannot decide a change you asked for or an entry you marked yourself.
      </p>
      <QueryView
        query={query}
        isEmpty={(r) => r.data.length === 0}
        empty="No correction is waiting. When someone reports a mistake in an attendance entry, it appears here."
      >
        {(result) => (
          <div className="space-y-3">
            <DataTable
              caption="Attendance corrections"
              rows={result.data}
              getKey={(c) => c.correction_id}
              cols={[
                { h: "Student", c: (c) => c.student.full_name },
                { h: "Class", c: (c) => `${c.session.title} · ${fmtDate(c.session.starts_at)}` },
                { h: "Change", c: (c) => `${c.previous_status ?? "Not yet marked"} to ${c.requested_status}` },
                { h: "Reason", c: (c) => `${c.reason} (${c.requested_by.full_name})` },
                {
                  h: "Decision",
                  c: (c) => (
                    <CorrectionDecision
                      correction={c}
                      busy={decide.isPending}
                      decide={(correction, decision, note) => decide.mutateAsync({ correction, decision, ...(note ? { note } : {}) })}
                    />
                  ),
                },
              ]}
            />
            <Pager meta={result.meta} onPage={setPage} noun="corrections" />
          </div>
        )}
      </QueryView>
    </div>
  );
}
