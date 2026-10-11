/**
 * Support requests for the people who work on them (trainer and branch screens): a filterable list and a request panel with the
 * thread, internal remarks, status, escalation and reassignment. Students have their own screens (features/student/support*.tsx).
 */
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { get } from "@/api/client";
import {
  SUPPORT_CATEGORIES,
  SUPPORT_STATUSES,
  supportApi,
  type SupportDetail,
  type SupportFilters,
  type SupportRow,
  type SupportSummary,
  type SupportView,
} from "@/api/support";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, PillTabs, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/auth/auth";
import { useApiMutation } from "@/lib/mutation";
import { fmtDateTime } from "@/features/shared/format";
import { AttachmentLinks, FilePicker } from "./support-attachments";
import { ReasonDialog } from "./reason-dialog";

const ATTACH_TEXT = {
  add: "Attach files",
  hint: "Images, PDF, text or Word; up to 3 files of 5 MB",
  tooBig: (name: string) => `${name} is larger than 5 MB`,
  wrongType: (name: string) => `${name} is not an allowed file type`,
  tooMany: "Attach at most 3 files",
  remove: (name: string) => `Remove ${name}`,
};

/** Status badge plus the escalation and SLA flags of a request. */
export function SupportState({ request, hideOverdue = false }: { request: SupportSummary; hideOverdue?: boolean }) {
  return (
    <div className="flex flex-wrap gap-1">
      <StatusBadge
        domain="support"
        code={request.status}
        label={hideOverdue && request.status === "Waiting on Student" ? "Waiting for the student" : undefined}
      />
      {request.escalation_level && <Tag tone="warning">Escalated to {request.escalation_level}</Tag>}
      {request.sla_breached && !hideOverdue && <Tag tone="danger">Reply overdue</Tag>}
    </div>
  );
}

const VIEWS = ["needs_action", "waiting", "done", "all"] as const;
const VIEW_LABELS: Record<SupportView, string> = { needs_action: "Needs action", waiting: "Waiting for the student", done: "Done", all: "All" };
const VIEW_EMPTY: Record<SupportView, string> = {
  needs_action: "Nothing needs a reply right now. New requests and student replies appear here, the nearest reply deadline first.",
  waiting: "No request is waiting for the student. When you ask a student for something, the request moves here until they answer.",
  done: "No request has been resolved yet.",
  all: "There are no support requests yet.",
};

/** "Reply due in 2 hours" or "Overdue by 3 hours": the reply deadline in plain words. */
function replyDueText(dueAt: string, now: number = Date.now()): { text: string; overdue: boolean } {
  const ms = new Date(dueAt).getTime() - now;
  const minutes = Math.round(Math.abs(ms) / 60_000);
  const span =
    minutes < 60
      ? minutes <= 1
        ? "a minute"
        : `${minutes} minutes`
      : minutes < 48 * 60
        ? `${Math.round(minutes / 60)} hour${Math.round(minutes / 60) === 1 ? "" : "s"}`
        : `${Math.round(minutes / 1440)} days`;
  return ms < 0 ? { text: `Overdue by ${span}`, overdue: true } : { text: `Reply due in ${span}`, overdue: false };
}

/** The reply deadline (open requests) and the marker for a new student message. */
function ReplyCell({ request }: { request: SupportRow }) {
  const open = request.status === "Open" || request.status === "In Progress";
  const due = open ? replyDueText(request.sla_due_at) : null;
  return (
    <div className="flex flex-wrap items-center gap-1">
      {request.reply_mark === "new_reply" && <Tag tone="info">New reply</Tag>}
      {request.reply_mark === "new_request" && <Tag tone="info">New</Tag>}
      {due && <Tag tone={due.overdue ? "danger" : "neutral"}>{due.text}</Tag>}
      {!due && <span className="text-xs text-muted-foreground">{request.status === "Waiting on Student" ? "Waiting for the student" : "No reply needed"}</span>}
    </div>
  );
}

/**
 * `simple` is the trainer's view: no category filter or ID column, and escalating, reassigning and internal remarks sit under
 * "More" in the request, so the first screen is just reading, replying and the status.
 *
 * `views` is the Branch Manager's view: tabs with counts (Needs action, Waiting for the student, Done, All) in place of the status
 * filter, the nearest reply deadline first, new replies marked, and the open request kept in the address when `openId` is given.
 */
export function SupportDesk({
  base = {},
  caption,
  empty,
  simple = false,
  views = false,
  initialView = "needs_action",
  openId: controlledOpen,
  onOpen,
  branchId,
  studentId,
  perPage,
}: {
  base?: SupportFilters;
  caption: string;
  empty: string;
  simple?: boolean;
  views?: boolean;
  initialView?: SupportView;
  /** The request whose panel is open, when the page keeps it in the address. */
  openId?: number | null;
  onOpen?: (id: number | null) => void;
  branchId?: number | null;
  studentId?: number;
  perPage?: number;
}) {
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [view, setView] = useState<SupportView>(initialView);
  const [ownOpen, setOwnOpen] = useState<number | null>(null);
  const openId = controlledOpen !== undefined ? controlledOpen : ownOpen;
  const setOpenId = onOpen ?? setOwnOpen;
  const scope: SupportFilters = { ...(branchId ? { branch_id: branchId } : {}), ...(studentId ? { student_id: studentId } : {}) };
  const filters: SupportFilters = {
    ...base,
    ...scope,
    category,
    q,
    page,
    ...(perPage ? { per_page: perPage } : {}),
    ...(views ? { view } : { status }),
  };
  const query = useQuery({
    queryKey: ["support", "list", filters],
    queryFn: () => supportApi.staffList(filters),
    placeholderData: views ? keepPreviousData : undefined,
  });
  const counts = useQuery({ queryKey: ["support", "counts", scope], queryFn: () => supportApi.counts(scope), enabled: views });

  return (
    <div className="space-y-3">
      {views && (
        <PillTabs
          label="Support request views"
          tabs={VIEWS}
          labels={VIEW_LABELS}
          value={view}
          onChange={(next) => (setView(next), setPage(1))}
          counts={counts.data}
        />
      )}
      <div className="flex flex-wrap items-end gap-2">
        {!views && (
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
        )}
        {!simple && (
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
        )}
        <div className="w-full sm:w-64">
          <Label htmlFor="support-q">Search</Label>
          <Input
            id="support-q"
            placeholder={views ? "Student, request number or subject" : "ID, subject or student"}
            value={q}
            onChange={(e) => (setQ(e.target.value), setPage(1))}
          />
        </div>
      </div>
      <QueryView
        query={query}
        isEmpty={(r) => r.data.length === 0}
        empty={views ? (q || category ? "No request matches that search." : VIEW_EMPTY[view]) : empty}
      >
        {(result) => (
          <>
            <DataTable
              caption={caption}
              rows={result.data}
              getKey={(r) => r.support_request_id}
              cols={[
                ...(simple ? [] : [{ h: "ID", c: (r: SupportRow) => <span className="font-mono text-xs">{r.request_code}</span> }]),
                { h: "Student", c: (r: SupportRow) => r.student.full_name },
                ...(simple
                  ? [
                      {
                        h: "About",
                        c: (r: SupportRow) => (
                          <>
                            <div>{r.subject}</div>
                            <div className="font-mono text-xs text-muted-foreground">
                              {r.request_code} · {r.category}
                            </div>
                          </>
                        ),
                      },
                    ]
                  : [
                      { h: "Category", c: (r: SupportRow) => r.category },
                      { h: "Subject", c: (r: SupportRow) => r.subject },
                    ]),
                { h: simple ? "With" : "Named owner", c: (r) => r.owner.label },
                ...(views ? [{ h: "Reply", c: (r: SupportRow) => <ReplyCell request={r} /> }] : []),
                { h: "State", c: (r) => <SupportState request={r} hideOverdue={views} /> },
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
      <SupportPanel id={openId} onClose={() => setOpenId(null)} simple={simple} />
    </div>
  );
}

type StaffMember = { user_id: number; full_name: string; role_code: string };

export function SupportPanel({ id, onClose, simple = false }: { id: number | null; onClose: () => void; simple?: boolean }) {
  return (
    <Dialog open={id !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">{id !== null && <PanelBody id={id} simple={simple} />}</DialogContent>
    </Dialog>
  );
}

function PanelBody({ id, simple }: { id: number; simple: boolean }) {
  const { profile } = useAuth();
  const query = useQuery({ queryKey: ["support", "detail", id], queryFn: () => supportApi.get(id) });
  const done = { invalidate: [["support"]] };
  const [text, setText] = useState("");
  const [internal, setInternal] = useState(false);
  const [target, setTarget] = useState("");
  const [assignee, setAssignee] = useState("");
  const [more, setMore] = useState(false);

  const [files, setFiles] = useState<File[]>([]);
  const message = useApiMutation((vars: { body: string; internal: boolean; files: File[] }) => supportApi.message(id, vars.body, vars.internal, vars.files), {
    ...done,
    success: "Message sent",
    onSuccess: () => {
      setText("");
      setFiles([]);
    },
  });
  const status = useApiMutation((vars: { status: string; note?: string }) => supportApi.status(id, vars.status, vars.note), {
    ...done,
    success: "Status updated",
  });
  const reopen = useApiMutation((reason: string) => supportApi.reopen(id, reason), { ...done, success: "Request reopened" });
  const escalate = useApiMutation((reason: string) => supportApi.escalate(id, reason), { ...done, success: "Request escalated" });
  const assign = useApiMutation((ownerId: number) => supportApi.assign(id, ownerId), { ...done, success: "Owner changed" });
  const branchId = query.data?.branch.branch_id;
  const staff = useQuery({
    queryKey: ["reference", "staff", branchId],
    queryFn: () => get<StaffMember[]>("/reference/staff", { branch_id: branchId }),
    enabled: branchId !== undefined,
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
                {request.subject} — raised {fmtDateTime(request.created_at)}
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
              <div>
                <dt className="text-xs text-muted-foreground">Student</dt>
                <dd>
                  {request.student.full_name} <span className="font-mono text-xs">{request.student.student_code}</span>
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Respond by</dt>
                <dd>{fmtDateTime(request.sla_due_at)}</dd>
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
                      {m.author.user_id === profile?.user.user_id ? `${m.author.full_name} (you)` : m.from_student ? "Student" : m.author.full_name}
                      {m.is_internal ? " · internal remark, not shown to the student" : ""}
                    </span>
                    <span>{fmtDateTime(m.created_at)}</span>
                  </div>
                  <p className="whitespace-pre-wrap break-words">{m.body}</p>
                  <AttachmentLinks attachments={m.attachments} />
                </li>
              ))}
            </ol>

            {!finished && (
              <div className="space-y-2">
                <Label htmlFor="support-reply">Reply</Label>
                <Textarea id="support-reply" rows={3} value={text} onChange={(e) => setText(e.target.value)} />
                <FilePicker files={files} onChange={setFiles} inputId="support-reply-files" text={ATTACH_TEXT} />
                <div className="flex flex-wrap items-center gap-3">
                  <Button disabled={!text.trim() || message.isPending} onClick={() => message.mutate({ body: text.trim(), internal, files })}>
                    {internal ? "Add internal remark" : "Send reply"}
                  </Button>
                  {(!simple || more) && (
                    <label className="flex items-center gap-1.5 text-sm">
                      <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} /> Internal remark (student cannot see it)
                    </label>
                  )}
                </div>
              </div>
            )}

            <div className="flex flex-wrap items-end gap-2 border-t pt-3">
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
              {!finished && (
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
                  {simple && (
                    <Button variant="ghost" aria-expanded={more} onClick={() => setMore((open) => !open)}>
                      More
                    </Button>
                  )}
                  {(!simple || more) && request.escalation_level !== "Branch Manager" && (
                    <ReasonDialog
                      title="Escalate this request"
                      description={"It goes to the Branch Manager."}
                      confirmLabel="Escalate"
                      busy={escalate.isPending}
                      onSubmit={(reason) => escalate.mutateAsync(reason)}
                      trigger={<Button variant="outline">Escalate</Button>}
                    />
                  )}
                  {(!simple || more) && profile?.scopes.some((s) => ["BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO"].includes(s.role_code)) && (
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
              {request.status === "Resolved" && (
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
