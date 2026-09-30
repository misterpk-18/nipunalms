/** Access entitlement card and the extension request dialog, shared by the Resources and Recordings screens. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { accessText, contentApi, formatDate, type AccessOverview } from "@/api/content";
import { QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Field, NativeSelect } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";

const SCOPES = ["Both", "Recording", "Material"] as const;

export function AccessWindow({ focus }: { focus: "Recording" | "Material" }) {
  const query = useQuery({ queryKey: ["me", "access"], queryFn: contentApi.access });
  const [requesting, setRequesting] = useState<AccessOverview | null>(null);
  return (
    <Section title="Access entitlement" className="mb-4">
      <ul className="mb-3 list-disc space-y-1 pl-5 text-sm">
        <li>
          Default: <strong>one calendar year from your confirmed Joining Date</strong> (first regular class you attend).
        </li>
        <li>
          You may request <strong>one extension to the second anniversary</strong> of the Joining Date. Repeated requests do not add further years.
        </li>
        <li>A request after the first expiry (but before the second anniversary) restores only the remaining time to the second anniversary.</li>
        <li>After the second anniversary only a Founder/CEO or Super Admin exception can extend access.</li>
        <li>
          Before a Joining Date exists, expiry shows as <strong>Pending</strong>.
        </li>
      </ul>
      <QueryView query={query} isEmpty={(rows) => rows.length === 0} empty="You have no active enrolments yet.">
        {(rows) => (
          <ul className="space-y-2">
            {rows.map((row) => {
              const state = focus === "Recording" ? row.recording : row.material;
              const pending = row.pending_requests[0];
              return (
                <li key={row.enrolment.enrolment_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-sm">
                  <div>
                    <div className="font-medium">{row.enrolment.course.title}</div>
                    <div className="text-xs text-muted-foreground">
                      Joining Date {row.joining_date ? formatDate(row.joining_date) : "pending"} · {focus === "Recording" ? "Recordings" : "Materials"}:{" "}
                      {accessText(state)}
                      {state.extended && " (extended)"}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {pending && <StatusBadge tone="warning">{`${pending.request_code} pending`}</StatusBadge>}
                    {row.can_request.Recording || row.can_request.Material ? (
                      <Button variant="outline" size="sm" onClick={() => setRequesting(row)}>
                        Request extension
                      </Button>
                    ) : (
                      !pending && (
                        <span className="text-xs text-muted-foreground">{row.joining_date ? "Extension already used" : "Available after you join"}</span>
                      )
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </QueryView>
      {requesting && <ExtensionDialog row={requesting} onClose={() => setRequesting(null)} />}
    </Section>
  );
}

function ExtensionDialog({ row, onClose }: { row: AccessOverview; onClose: () => void }) {
  const allowed = SCOPES.filter((scope) => (scope === "Both" ? row.can_request.Recording && row.can_request.Material : row.can_request[scope]));
  const [scope, setScope] = useState<string>(allowed[0] ?? "Both");
  const [reason, setReason] = useState("");
  const mutation = useApiMutation((body: { enrolment_id: number; scope: string; reason: string }) => contentApi.requestExtension(body), {
    success: "Extension request sent for review",
    invalidate: [["me", "access"]],
    onSuccess: onClose,
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Request an access extension</DialogTitle>
          <DialogDescription>
            {row.enrolment.course.title}: access is extended to {formatDate(row.second_expiry)}, the second anniversary of your Joining Date.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Field label="What should be extended?" htmlFor="ext-scope">
            <NativeSelect
              id="ext-scope"
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              options={allowed.map((s) => ({ value: s, label: s === "Both" ? "Recordings and materials" : s === "Recording" ? "Recordings" : "Materials" }))}
            />
          </Field>
          <Field label="Reason" htmlFor="ext-reason">
            <Textarea id="ext-reason" value={reason} onChange={(e) => setReason(e.target.value)} rows={3} placeholder="Why do you need more time?" />
          </Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={!reason.trim() || mutation.isPending}
            onClick={() => mutation.mutate({ enrolment_id: row.enrolment.enrolment_id, scope, reason: reason.trim() })}
          >
            Send request
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
