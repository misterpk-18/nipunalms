/** Access-extension requests of the branch. Composed into the Branch Manager's requests page by the dashboards phase. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { contentApi, formatDate, type ExtensionRequest } from "@/api/content";
import { DataTable, Note, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Field, NativeSelect } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/auth/auth";
import { useApiMutation } from "@/lib/mutation";

const KIND = { Recording: "Recording", Material: "Material", Both: "Recording and material" } as const;

function stateText(r: ExtensionRequest): string {
  if (r.status === "Pending") return r.needs_exception ? "Needs Founder/CEO or Super Admin exception" : "Pending review";
  return r.status === "Approved" ? `Approved until ${formatDate(r.approved_expiry)}` : "Rejected";
}

export function AccessExtensions() {
  const [status, setStatus] = useState("");
  const query = useQuery({ queryKey: ["access-extensions", status], queryFn: () => contentApi.requests({ status, per_page: 100 }) });
  const [deciding, setDeciding] = useState<ExtensionRequest | null>(null);
  return (
    <Section title="Access-extension requests">
      <div className="mb-3 max-w-48">
        <NativeSelect
          aria-label="Request status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          placeholder="All requests"
          options={["Pending", "Approved", "Rejected"].map((s) => ({ value: s, label: s }))}
        />
      </div>
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No access-extension requests.">
        {(page) => (
          <DataTable
            caption="Access-extension requests"
            rows={page.data}
            getKey={(r) => r.request_id}
            cols={[
              { h: "ID", c: (r) => r.request_code },
              { h: "Type", c: (r) => `${KIND[r.scope]} extension to the 2nd anniversary${r.needs_exception ? " (after the 2nd anniversary)" : ""}` },
              {
                h: "Subject",
                c: (r) => (
                  <>
                    <div>{r.student.full_name}</div>
                    <div className="text-xs text-muted-foreground">
                      {r.student.student_code} · {r.enrolment.course.title}
                    </div>
                    <div className="text-xs text-muted-foreground">“{r.reason}”</div>
                  </>
                ),
              },
              { h: "State", c: (r) => <StatusBadge tone={r.needs_exception && r.status === "Pending" ? "danger" : undefined}>{stateText(r)}</StatusBadge> },
              {
                h: "Action",
                c: (r) =>
                  r.status === "Pending" ? (
                    <Button size="sm" variant="outline" onClick={() => setDeciding(r)}>
                      Decide
                    </Button>
                  ) : (
                    r.decided_by && <span className="text-xs text-muted-foreground">{r.decided_by.full_name}</span>
                  ),
              },
            ]}
          />
        )}
      </QueryView>
      <div className="mt-3">
        <Note>Repeated extension requests do not stack years. The routine extension always ends on the second anniversary of the Joining Date.</Note>
      </div>
      {deciding && <DecideDialog request={deciding} onClose={() => setDeciding(null)} />}
    </Section>
  );
}

function DecideDialog({ request, onClose }: { request: ExtensionRequest; onClose: () => void }) {
  const { profile } = useAuth();
  const canDecide = !request.needs_exception || profile?.scopes.some((s) => s.role_code === "SUPER_ADMIN" || s.role_code === "FOUNDER_CEO");
  const [note, setNote] = useState("");
  const [expiry, setExpiry] = useState("");
  const decide = useApiMutation((body: { decision: "approve" | "reject"; note?: string; new_expiry?: string }) => contentApi.decide(request.request_id, body), {
    success: (r) => `${r.request_code} ${r.status.toLowerCase()}`,
    invalidate: [["access-extensions"]],
    onSuccess: onClose,
  });
  const extra = note.trim() ? { note: note.trim() } : {};
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Decide {request.request_code}</DialogTitle>
          <DialogDescription>
            {request.student.full_name} · {request.enrolment.course.title} · {KIND[request.scope]}. Standard expiry {formatDate(request.original_expiry)}.
          </DialogDescription>
        </DialogHeader>
        <p className="text-sm">“{request.reason}”</p>
        {request.needs_exception && (
          <>
            {!canDecide && <p className="text-sm text-danger">Only a Founder/CEO or Super Admin can grant an exception after the second anniversary.</p>}
            <Field label="New expiry (exception)" htmlFor="new-expiry">
              <Input id="new-expiry" type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
            </Field>
          </>
        )}
        <Field label="Note (required to reject)" htmlFor="decision-note">
          <Textarea id="decision-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        <DialogFooter>
          <Button variant="outline" disabled={!note.trim() || decide.isPending || !canDecide} onClick={() => decide.mutate({ decision: "reject", ...extra })}>
            Reject
          </Button>
          <Button
            disabled={decide.isPending || !canDecide || (request.needs_exception && !expiry)}
            onClick={() => decide.mutate({ decision: "approve", ...extra, ...(expiry && { new_expiry: expiry }) })}
          >
            Approve
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
