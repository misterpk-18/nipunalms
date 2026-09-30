/**
 * Support requests for everyone who works on them: a filterable list and a request panel with the thread. The student
 * screen uses `mode="student"` (reply, close, reopen); trainer, academic and branch screens use `mode="staff"`
 * (internal remarks, status, escalate, reassign).
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "@/api/client";
import { SUPPORT_CATEGORIES, SUPPORT_STATUSES, supportApi, type SupportDetail, type SupportFilters, type SupportSummary } from "@/api/support";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/auth/auth";
import { useApiMutation } from "@/lib/mutation";
import { formatIst } from "./ist";
import { ReasonDialog } from "./reason-dialog";

export type SupportMode = "student" | "staff";

/** Status badge plus the escalation and SLA flags of a request. */
export function SupportState({ request }: { request: SupportSummary }) {
  return (
    <div className="flex flex-wrap gap-1">
      <StatusBadge>{request.status}</StatusBadge>
      {request.escalation_level && <StatusBadge tone="warning">Escalated to {request.escalation_level}</StatusBadge>}
      {request.sla_breached && <StatusBadge tone="danger">SLA breached</StatusBadge>}
    </div>
  );
}

export function SupportDesk({ mode, base = {}, caption, empty }: { mode: SupportMode; base?: SupportFilters; caption: string; empty: string }) {
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(null);
  const filters: SupportFilters = { ...base, status, category, q, page };
  const query = useQuery({ queryKey: ["support", "list", filters], queryFn: () => supportApi.list(filters) });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <div className="w-full sm:w-44">
          <Label htmlFor="support-status">Status</Label>
          <NativeSelect
            id="support-status"
            placeholder="All"
            value={status}
            onChange={(e) => (setStatus(e.target.value), setPage(1))}
            options={SUPPORT_STATUSES.map((s) => ({ value: s, label: s }))}
          />
        </div>
        <div className="w-full sm:w-48">
          <Label htmlFor="support-category">Category</Label>
          <NativeSelect
            id="support-category"
            placeholder="All"
            value={category}
            onChange={(e) => (setCategory(e.target.value), setPage(1))}
            options={SUPPORT_CATEGORIES.map((s) => ({ value: s, label: s }))}
          />
        </div>
        {mode === "staff" && (
          <div className="w-full sm:w-64">
            <Label htmlFor="support-q">Search</Label>
            <Input id="support-q" placeholder="ID, subject or student" value={q} onChange={(e) => (setQ(e.target.value), setPage(1))} />
          </div>
        )}
      </div>
      <QueryView query={query} isEmpty={(r) => r.data.length === 0} empty={empty}>
        {(result) => (
          <>
            <DataTable
              caption={caption}
              rows={result.data}
              getKey={(r) => r.support_request_id}
              cols={[
                { h: "ID", c: (r) => <span className="font-mono text-xs">{r.request_code}</span> },
                ...(mode === "staff" ? [{ h: "Student", c: (r: SupportSummary) => r.student.full_name }] : []),
                { h: "Category", c: (r) => r.category },
                { h: "Subject", c: (r) => r.subject },
                { h: "Named owner", c: (r) => r.owner.label },
                { h: "State", c: (r) => <SupportState request={r} /> },
                {
                  h: "Open",
                  c: (r) => (
                    <Button size="sm" variant="outline" onClick={() => setOpenId(r.support_request_id)} aria-label={`Open ${r.request_code}`}>
                      Open
                    </Button>
                  ),
                },
              ]}
            />
            {result.meta.pages > 1 && (
              <div className="flex items-center justify-end gap-2 text-sm">
                <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                  Previous
                </Button>
                <span>
                  Page {result.meta.page} of {result.meta.pages}
                </span>
                <Button size="sm" variant="outline" disabled={page >= result.meta.pages} onClick={() => setPage(page + 1)}>
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </QueryView>
      <SupportPanel id={openId} mode={mode} onClose={() => setOpenId(null)} />
    </div>
  );
}

type StaffMember = { user_id: number; full_name: string; role_code: string };

export function SupportPanel({ id, mode, onClose }: { id: number | null; mode: SupportMode; onClose: () => void }) {
  return (
    <Dialog open={id !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">{id !== null && <PanelBody id={id} mode={mode} />}</DialogContent>
    </Dialog>
  );
}

function PanelBody({ id, mode }: { id: number; mode: SupportMode }) {
  const { profile } = useAuth();
  const query = useQuery({ queryKey: ["support", "detail", id], queryFn: () => supportApi.get(id) });
  const done = { invalidate: [["support"]] };
  const [text, setText] = useState("");
  const [internal, setInternal] = useState(false);
  const [target, setTarget] = useState("");
  const [assignee, setAssignee] = useState("");

  const message = useApiMutation((vars: { body: string; internal: boolean }) => supportApi.message(id, vars.body, vars.internal), {
    ...done,
    success: "Message sent",
    onSuccess: () => setText(""),
  });
  const status = useApiMutation((vars: { status: string; note?: string }) => supportApi.status(id, vars.status, vars.note), {
    ...done,
    success: "Status updated",
  });
  const close = useApiMutation(() => supportApi.close(id), { ...done, success: "Request closed" });
  const reopen = useApiMutation((reason: string) => supportApi.reopen(id, reason), { ...done, success: "Request reopened" });
  const escalate = useApiMutation((reason: string) => supportApi.escalate(id, reason), { ...done, success: "Request escalated" });
  const assign = useApiMutation((ownerId: number) => supportApi.assign(id, ownerId), { ...done, success: "Owner changed" });
  const branchId = query.data?.branch.branch_id;
  const staff = useQuery({
    queryKey: ["reference", "staff", branchId],
    queryFn: () => get<StaffMember[]>("/reference/staff", { branch_id: branchId }),
    enabled: mode === "staff" && branchId !== undefined,
  });

  return (
    <QueryView query={query}>
      {(request: SupportDetail) => {
        const finished = request.status === "Resolved" || request.status === "Closed";
        const owners = [...new Map((staff.data ?? []).map((s) => [s.user_id, s])).values()];
        return (
          <div className="space-y-4">
            <DialogHeader>
              <DialogTitle>
                <span className="font-mono">{request.request_code}</span> · {request.category}
              </DialogTitle>
              <DialogDescription>
                {request.subject} — raised {formatIst(request.created_at)}
                {request.raised_via === "Staff flag" ? ` by ${request.raised_by.full_name} (support flag)` : ""}
              </DialogDescription>
            </DialogHeader>
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-muted-foreground">Named owner</dt>
                <dd className="font-medium">
                  {request.owner.label} ({request.owner.full_name})
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">State</dt>
                <dd>
                  <SupportState request={request} />
                </dd>
              </div>
              {mode === "staff" && (
                <div>
                  <dt className="text-xs text-muted-foreground">Student</dt>
                  <dd>
                    {request.student.full_name} <span className="font-mono text-xs">{request.student.student_code}</span>
                  </dd>
                </div>
              )}
              <div>
                <dt className="text-xs text-muted-foreground">Respond by</dt>
                <dd>{formatIst(request.sla_due_at)}</dd>
              </div>
              {request.resolution_note && (
                <div className="sm:col-span-2">
                  <dt className="text-xs text-muted-foreground">Resolution</dt>
                  <dd>{request.resolution_note}</dd>
                </div>
              )}
            </dl>

            <ol className="space-y-2" aria-label="Conversation">
              {request.messages.map((m) => (
                <li
                  key={m.support_message_id}
                  className={`rounded-lg border p-2.5 text-sm ${m.kind !== "Message" ? "bg-muted text-muted-foreground" : m.is_internal ? "border-warning/40 bg-warning-soft" : "bg-card"}`}
                >
                  <div className="mb-0.5 flex flex-wrap justify-between gap-2 text-xs text-muted-foreground">
                    <span>
                      {m.from_student ? "Student" : m.author.full_name}
                      {m.author.user_id === profile?.user.user_id ? " (you)" : ""}
                      {m.is_internal ? " · internal remark, not shown to the student" : ""}
                    </span>
                    <span>{formatIst(m.created_at)}</span>
                  </div>
                  <p className="whitespace-pre-wrap break-words">{m.body}</p>
                </li>
              ))}
            </ol>

            {!finished && (
              <div className="space-y-2">
                <Label htmlFor="support-reply">Reply</Label>
                <Textarea id="support-reply" rows={3} value={text} onChange={(e) => setText(e.target.value)} />
                <div className="flex flex-wrap items-center gap-3">
                  <Button disabled={!text.trim() || message.isPending} onClick={() => message.mutate({ body: text.trim(), internal })}>
                    {internal ? "Add internal remark" : "Send reply"}
                  </Button>
                  {mode === "staff" && (
                    <label className="flex items-center gap-1.5 text-sm">
                      <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} /> Internal remark (student cannot see it)
                    </label>
                  )}
                </div>
              </div>
            )}

            <div className="flex flex-wrap items-end gap-2 border-t pt-3">
              {mode === "student" && request.status === "Resolved" && (
                <Button onClick={() => close.mutate()} disabled={close.isPending}>
                  Confirm resolved and close
                </Button>
              )}
              {finished && (
                <ReasonDialog
                  title="Reopen this request"
                  description="Tell us what is still not working."
                  confirmLabel="Reopen"
                  busy={reopen.isPending}
                  onSubmit={(reason) => reopen.mutateAsync(reason)}
                  trigger={<Button variant="outline">Reopen</Button>}
                />
              )}
              {mode === "staff" && !finished && (
                <>
                  <div className="w-44">
                    <Label htmlFor="support-set-status">Change status</Label>
                    <NativeSelect
                      id="support-set-status"
                      placeholder="Choose…"
                      value={target}
                      onChange={(e) => setTarget(e.target.value)}
                      options={["In Progress", "Waiting on Student"].filter((s) => s !== request.status).map((s) => ({ value: s, label: s }))}
                    />
                  </div>
                  <Button
                    variant="outline"
                    disabled={!target || status.isPending}
                    onClick={() => status.mutate({ status: target }, { onSuccess: () => setTarget("") })}
                  >
                    Update
                  </Button>
                  <ReasonDialog
                    title="Resolve this request"
                    label="How was it resolved?"
                    confirmLabel="Resolve"
                    busy={status.isPending}
                    onSubmit={(note) => status.mutateAsync({ status: "Resolved", note })}
                    trigger={<Button>Resolve</Button>}
                  />
                  {request.escalation_level !== "Branch Manager" && (
                    <ReasonDialog
                      title="Escalate this request"
                      description={request.owner.role_code === "TRAINER" ? "It moves to the Academic Coordinator." : "It goes to the Branch Manager."}
                      confirmLabel="Escalate"
                      busy={escalate.isPending}
                      onSubmit={(reason) => escalate.mutateAsync(reason)}
                      trigger={<Button variant="outline">Escalate</Button>}
                    />
                  )}
                  {profile?.scopes.some((s) => ["ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO"].includes(s.role_code)) && (
                    <>
                      <div className="w-52">
                        <Label htmlFor="support-assign">Reassign to</Label>
                        <NativeSelect
                          id="support-assign"
                          placeholder="Choose…"
                          value={assignee}
                          onChange={(e) => setAssignee(e.target.value)}
                          options={owners.map((s) => ({ value: s.user_id, label: `${s.full_name} (${s.role_code.replaceAll("_", " ").toLowerCase()})` }))}
                        />
                      </div>
                      <Button
                        variant="outline"
                        disabled={!assignee || assign.isPending}
                        onClick={() => assign.mutate(Number(assignee), { onSuccess: () => setAssignee("") })}
                      >
                        Assign
                      </Button>
                    </>
                  )}
                </>
              )}
              {mode === "staff" && request.status === "Resolved" && (
                <Button variant="outline" onClick={() => status.mutate({ status: "Closed" })} disabled={status.isPending}>
                  Close
                </Button>
              )}
            </div>
          </div>
        );
      }}
    </QueryView>
  );
}
