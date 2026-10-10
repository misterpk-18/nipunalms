/** One live class under the Meet operations view: people, incidents, disruptions, cover, shared batches and participation. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  deliveryApi,
  type BatchRef,
  type CoverRequest,
  type Disruption,
  type MeetIncident,
  type Participation,
  type SessionOperations,
  type SessionPerson,
  type SessionRoster,
} from "@/api/delivery";
import type { BranchRef } from "@/api/types";
import { useAuth } from "@/auth/auth";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { DataTable, PillTabs, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { ActionDialog, fmtDate, fmtRange, fromIstInput, toIstInput, useCanManage, useIsManager } from "@/features/shared/delivery-ui";
import { useDelivery } from "@/features/shared/sessions";
import { useStaffOptions } from "@/features/shared/staff-picker";

export type ClassTarget = { session_id: number; session_code: string; title: string; starts_at: string; ends_at: string; batch: BatchRef; branch: BranchRef };

const TABS = ["People", "Incidents and disruptions", "Cover", "Shared batches", "Participation"] as const;
const HOSTING_ROLES = ["TRAINER", "BRANCH_MANAGER", "SUPER_ADMIN"];
const opt = (values: string[]) => values.map((v) => ({ value: v, label: v }));
export const DISRUPTION_CAUSES = opt(["Institute", "Provider", "Trainer", "Unknown"]);
const who = (u: { full_name: string } | null) => u?.full_name ?? "—";

// ---------------------------------------------------------------- people

function People({ target, ops }: { target: ClassTarget; ops: SessionOperations }) {
  const manager = useCanManage();
  const staff = useStaffOptions(target.branch.branch_id, HOSTING_ROLES);
  const add = useDelivery((body: Record<string, unknown>) => deliveryApi.addPerson(target.session_id, body), "Person added");
  const decide = useDelivery(
    (v: { id: number; decision: "Approved" | "Rejected"; note?: string }) => deliveryApi.decideGuest(v.id, { decision: v.decision, note: v.note }),
    "Guest decision recorded",
  );
  const remove = useDelivery((id: number) => deliveryApi.removePerson(id), "Removed");
  const people = ops.people.filter((p) => !p.removed_at);
  return (
    <div className="space-y-3">
      <DataTable
        caption="People in the class"
        rows={people}
        getKey={(p) => p.session_person_id}
        empty="No host, backup or guest is named yet. The trainer hosts by default."
        cols={[
          { h: "Role", c: (p: SessionPerson) => <Tag tone={p.role === "Guest" ? "warning" : "info"}>{p.role}</Tag> },
          {
            h: "Who",
            c: (p: SessionPerson) =>
              p.user ? (
                p.user.full_name
              ) : (
                <>
                  {p.guest_name}
                  {p.guest_email && <div className="text-xs text-muted-foreground">{p.guest_email}</div>}
                </>
              ),
          },
          {
            h: "Why",
            c: (p: SessionPerson) =>
              p.role === "Guest" ? (
                <>
                  {p.purpose}
                  {p.student_agreement && <div className="text-xs text-muted-foreground">Students: {p.student_agreement}</div>}
                  <div className="text-xs text-muted-foreground">A guest gets no LMS rights.</div>
                </>
              ) : (
                "—"
              ),
          },
          { h: "Status", c: (p: SessionPerson) => <StatusBadge domain="approval" code={p.status} /> },
          ...(manager
            ? [
                {
                  h: "Actions",
                  c: (p: SessionPerson) => (
                    <div className="flex flex-wrap gap-1.5">
                      {p.role === "Guest" && p.status === "Pending" && (
                        <>
                          <Button size="sm" onClick={() => decide.mutate({ id: p.session_person_id, decision: "Approved" })}>
                            Approve
                          </Button>
                          <ActionDialog
                            trigger={
                              <Button size="sm" variant="outline">
                                Reject
                              </Button>
                            }
                            title="Reject the guest"
                            fields={[{ name: "note", label: "Why", type: "textarea" }]}
                            submitLabel="Reject"
                            onSubmit={(v) => decide.mutateAsync({ id: p.session_person_id, decision: "Rejected", note: v["note"] || undefined })}
                          />
                        </>
                      )}
                      <Button size="sm" variant="ghost" onClick={() => remove.mutate(p.session_person_id)}>
                        Remove
                      </Button>
                    </div>
                  ),
                },
              ]
            : []),
        ]}
      />
      {manager && (
        <div className="flex flex-wrap gap-2">
          <ActionDialog
            trigger={<Button size="sm">Add host or backup</Button>}
            title="Name the host or backup"
            description="A staff member with a verified identity who is not busy with another class then. A new host or backup replaces the earlier one."
            fields={[
              { name: "role", label: "Role", type: "select", options: opt(["Host", "Backup"]) },
              { name: "user_id", label: "Person", type: "select", required: true, options: staff },
            ]}
            submitLabel="Add"
            onSubmit={(v) => add.mutateAsync({ role: v["role"], user_id: Number(v["user_id"]) })}
          />
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Add a guest
              </Button>
            }
            title="Propose a guest"
            description="A guest is approved by someone other than the proposer, and gets no LMS access."
            fields={[
              { name: "guest_name", label: "Guest name", required: true },
              { name: "guest_email", label: "Guest email" },
              { name: "purpose", label: "Why they are joining", type: "textarea", required: true },
              { name: "student_agreement", label: "How the students agreed", type: "textarea", hint: "If the guest sees the students" },
            ]}
            submitLabel="Propose guest"
            onSubmit={(v) =>
              add.mutateAsync({
                role: "Guest",
                guest_name: v["guest_name"],
                guest_email: v["guest_email"] || undefined,
                purpose: v["purpose"],
                student_agreement: v["student_agreement"] || undefined,
              })
            }
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- incidents and disruptions

export function ResolveDisruptionDialog({ disruption }: { disruption: Disruption }) {
  const resolve = useDelivery(
    (v: { recovery_plan: string; undelivered_minutes: number; cause: string }) => deliveryApi.resolveDisruption(disruption.disruption_id, v),
    "Disruption resolved — the students have been told the plan",
  );
  return (
    <ActionDialog
      trigger={<Button size="sm">Resolve</Button>}
      title={`Resolve: ${disruption.kind}`}
      description={`${disruption.session.title} (${disruption.session.session_code}). The students are told the recovery plan.`}
      fields={[
        { name: "recovery_plan", label: "Recovery plan", type: "textarea", required: true },
        { name: "undelivered_minutes", label: "Minutes not delivered", type: "number", min: 0, required: true, value: String(disruption.delay_minutes ?? 0) },
        { name: "cause", label: "Cause", type: "select", options: DISRUPTION_CAUSES, value: disruption.cause },
      ]}
      submitLabel="Resolve"
      onSubmit={(v) =>
        resolve.mutateAsync({ recovery_plan: v["recovery_plan"]!, undelivered_minutes: Number(v["undelivered_minutes"]), cause: v["cause"]! })
      }
    />
  );
}

function Incidents({ target, ops }: { target: ClassTarget; ops: SessionOperations }) {
  const manager = useCanManage();
  const incident = useDelivery(
    (body: Parameters<typeof deliveryApi.reportIncident>[1]) => deliveryApi.reportIncident(target.session_id, body),
    "Incident reported — the Branch Managers are alerted",
  );
  const disrupt = useDelivery((body: Parameters<typeof deliveryApi.recordDisruption>[1]) => deliveryApi.recordDisruption(target.session_id, body), "Disruption recorded");
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <ActionDialog
          trigger={<Button size="sm">Report a link incident</Button>}
          title="Report a Meet link incident"
          description="The Branch Managers are alerted. Replacing the link removes it and tells the participants."
          fields={[
            { name: "kind", label: "What happened", type: "select", options: opt(["Compromised link", "Unexpected joiner", "Host access failure", "Other"]) },
            { name: "description", label: "Description", type: "textarea", required: true },
            { name: "actions_taken", label: "Actions taken", type: "textarea", required: true },
            { name: "replace_link", label: "Link", type: "checkbox", hint: "Replace the link (the current one is removed)" },
          ]}
          submitLabel="Report"
          onSubmit={(v) =>
            incident.mutateAsync({ kind: v["kind"]!, description: v["description"]!, actions_taken: v["actions_taken"]!, replace_link: v["replace_link"] === "true" })
          }
        />
        {manager && (
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Record a disruption
              </Button>
            }
            title="Record a disruption"
            description="A delayed or failed start, a connection failure or a compromised link. It stays open until it is resolved with a recovery plan."
            fields={[
              { name: "kind", label: "Kind", type: "select", options: opt(["Delayed start", "Failed start", "Connection failure", "Compromised link", "Other"]) },
              { name: "cause", label: "Cause", type: "select", options: DISRUPTION_CAUSES, value: "Unknown" },
              { name: "delay_minutes", label: "Delay in minutes", type: "number", min: 0 },
              { name: "detail", label: "Detail", type: "textarea" },
            ]}
            submitLabel="Record"
            onSubmit={(v) =>
              disrupt.mutateAsync({ kind: v["kind"]!, cause: v["cause"], delay_minutes: v["delay_minutes"] ? Number(v["delay_minutes"]) : null, detail: v["detail"] || undefined })
            }
          />
        )}
      </div>
      <DataTable
        caption="Link incidents"
        rows={ops.incidents}
        getKey={(i) => i.incident_id}
        empty="No link incidents for this class."
        cols={[
          { h: "When", c: (i: MeetIncident) => fmtDate(i.reported_at) },
          { h: "Incident", c: (i: MeetIncident) => <><strong>{i.kind}</strong><div>{i.description}</div></> },
          { h: "Actions taken", c: (i: MeetIncident) => i.actions_taken },
          { h: "Link", c: (i: MeetIncident) => (i.link_replaced ? "Replaced" : "Kept") },
          { h: "By", c: (i: MeetIncident) => who(i.reported_by) },
        ]}
      />
      <DataTable
        caption="Disruptions"
        rows={ops.disruptions}
        getKey={(d) => d.disruption_id}
        empty="No disruption recorded for this class."
        cols={[
          { h: "Kind", c: (d: Disruption) => <><strong>{d.kind}</strong>{d.detail && <div>{d.detail}</div>}</> },
          { h: "Delay", c: (d: Disruption) => (d.delay_minutes != null ? `${d.delay_minutes} min` : "—") },
          { h: "Cause", c: (d: Disruption) => d.cause },
          { h: "Status", c: (d: Disruption) => <StatusBadge domain="approval" code={d.status} /> },
          {
            h: "Recovery",
            c: (d: Disruption) =>
              d.status === "Resolved" ? (
                <>
                  {d.recovery_plan}
                  <div className="text-xs text-muted-foreground">{d.undelivered_minutes} minutes not delivered</div>
                </>
              ) : manager ? (
                <ResolveDisruptionDialog disruption={d} />
              ) : (
                "—"
              ),
          },
        ]}
      />
    </div>
  );
}

// ---------------------------------------------------------------- cover

function Cover({ target, ops }: { target: ClassTarget; ops: SessionOperations }) {
  const { hasRole } = useAuth();
  const manager = useCanManage();
  const approver = useIsManager();
  const verifier = hasRole("BRANCH_MANAGER", "SUPER_ADMIN");
  const trainers = useStaffOptions(target.branch.branch_id, ["TRAINER"]);
  const request = useDelivery((body: Parameters<typeof deliveryApi.requestCover>[1]) => deliveryApi.requestCover(target.session_id, body), "Cover requested");
  const decide = useDelivery(
    (v: { id: number; decision: "Approved" | "Rejected"; note?: string }) => deliveryApi.decideCover(v.id, { decision: v.decision, note: v.note }),
    "Decision recorded",
  );
  const verify = useDelivery((v: { id: number; note: string }) => deliveryApi.verifyCover(v.id, v.note), "Cover verified");
  return (
    <div className="space-y-3">
      <DataTable
        caption="Cover requests"
        rows={ops.cover_requests}
        getKey={(c) => c.request_id}
        empty="No cover has been requested for this class."
        cols={[
          { h: "Cover", c: (c: CoverRequest) => <><strong>{c.cover_role}</strong>: {who(c.cover)}<div className="text-xs text-muted-foreground">for {who(c.planned_trainer)}</div></> },
          { h: "Why", c: (c: CoverRequest) => <>{c.reason}<div className="text-xs text-muted-foreground">Scope: {c.scope}</div><div className="text-xs text-muted-foreground">Handover: {c.handover}</div></> },
          {
            h: "Status",
            c: (c: CoverRequest) => (
              <>
                <StatusBadge domain="approval" code={c.status} />
                <div className="mt-1 text-xs text-muted-foreground">
                  {c.approved_at ? `Approved by ${who(c.approved_by)}` : "Not approved yet"} · {c.verified_at ? `Verified by ${who(c.verified_by)}` : "Not verified yet"}
                </div>
              </>
            ),
          },
          ...(manager
            ? [
                {
                  h: "Actions",
                  c: (c: CoverRequest) => {
                    if (c.status === "Applied" || c.status === "Rejected") return "—";
                    return (
                      <div className="flex flex-wrap gap-1.5">
                        {approver && !c.approved_at && (
                          <>
                            <Button size="sm" onClick={() => decide.mutate({ id: c.request_id, decision: "Approved" })}>
                              Approve
                            </Button>
                            <ActionDialog
                              trigger={
                                <Button size="sm" variant="outline">
                                  Reject
                                </Button>
                              }
                              title="Reject the cover request"
                              fields={[{ name: "note", label: "Why", type: "textarea" }]}
                              submitLabel="Reject"
                              onSubmit={(v) => decide.mutateAsync({ id: c.request_id, decision: "Rejected", note: v["note"] || undefined })}
                            />
                          </>
                        )}
                        {verifier && !c.verified_at && (
                          <ActionDialog
                            trigger={
                              <Button size="sm" variant="outline">
                                Verify
                              </Button>
                            }
                            title="Verify the cover"
                            description="Confirm the cover person is free, holds the Trainer role and has the handover."
                            fields={[{ name: "note", label: "Verification note", type: "textarea", required: true }]}
                            submitLabel="Verify"
                            onSubmit={(v) => verify.mutateAsync({ id: c.request_id, note: v["note"]! })}
                          />
                        )}
                      </div>
                    );
                  },
                },
              ]
            : []),
        ]}
      />
      {manager && (
        <ActionDialog
          trigger={<Button size="sm">Request cover</Button>}
          title="Request a substitute or assistant"
          description="The Branch Manager approves and verifies it. A Branch Manager’s own request is decided by a Super Admin. A substitute becomes the class trainer for this class only."
          fields={[
            { name: "cover_role", label: "Cover role", type: "select", options: opt(["Substitute", "Assistant"]) },
            { name: "cover_user_id", label: "Cover person", type: "select", required: true, options: trainers, hint: "Trainers of this branch" },
            { name: "reason", label: "Reason", type: "textarea", required: true },
            { name: "scope", label: "Scope", type: "textarea", required: true, hint: "What the cover person does in this class" },
            { name: "handover", label: "Handover", type: "textarea", required: true, hint: "What they need to know from the planned trainer" },
          ]}
          submitLabel="Request cover"
          onSubmit={(v) =>
            request.mutateAsync({ cover_role: v["cover_role"]!, cover_user_id: Number(v["cover_user_id"]), reason: v["reason"]!, scope: v["scope"]!, handover: v["handover"]! })
          }
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------- shared batches

function Shared({ target, ops }: { target: ClassTarget; ops: SessionOperations }) {
  const { hasRole } = useAuth();
  const allowed = hasRole("BRANCH_MANAGER", "SUPER_ADMIN");
  const batches = useQuery({ queryKey: ["delivery", "batches", "open"], queryFn: () => deliveryApi.batches({}), enabled: allowed });
  const add = useDelivery((body: { batch_id: number; topic_id?: number | null; coverage_note: string }) => deliveryApi.addRoster(target.session_id, body), "Batch added to the class");
  const remove = useDelivery((batchId: number) => deliveryApi.removeRoster(target.session_id, batchId), "Batch removed from the class");
  const joined = new Set([target.batch.batch_id, ...ops.rosters.map((r) => r.batch.batch_id)]);
  const options = (batches.data?.data ?? [])
    .filter((b) => !joined.has(b.batch_id) && !["Completed", "Cancelled", "Archived"].includes(b.state))
    .map((b) => ({ value: b.batch_id, label: `${b.batch_code} — ${b.course.course_code} (${b.state_label})` }));
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        A shared class is one class for several batches: one attendance entry per person, hours and trainer time counted once. Together they may not exceed the class's verified
        seats.
      </p>
      <DataTable
        caption="Batches in this class"
        rows={ops.rosters}
        getKey={(r) => r.batch.batch_id}
        empty="Only the class's own batch attends."
        cols={[
          { h: "Batch", c: (r: SessionRoster) => r.batch.batch_code },
          { h: "Coverage", c: (r: SessionRoster) => r.coverage_note },
          { h: "Topic", c: (r: SessionRoster) => (r.topic_id ? `Topic ${r.topic_id}` : "—") },
          ...(allowed
            ? [
                {
                  h: "Actions",
                  c: (r: SessionRoster) => (
                    <Button size="sm" variant="outline" onClick={() => remove.mutate(r.batch.batch_id)}>
                      Remove
                    </Button>
                  ),
                },
              ]
            : []),
        ]}
      />
      {allowed && (
        <ActionDialog
          trigger={<Button size="sm">Add a batch</Button>}
          title="Add a batch to this class"
          description="Removing a batch is refused once attendance is marked."
          fields={[
            { name: "batch_id", label: "Batch", type: "select", required: true, options },
            { name: "coverage_note", label: "Coverage note", type: "textarea", required: true, hint: "What this batch gets from the shared class" },
            { name: "topic_id", label: "Topic ID (optional)", type: "number", min: 1 },
          ]}
          submitLabel="Add batch"
          onSubmit={(v) => add.mutateAsync({ batch_id: Number(v["batch_id"]), coverage_note: v["coverage_note"]!, topic_id: v["topic_id"] ? Number(v["topic_id"]) : null })}
        />
      )}
      {!allowed && <p className="text-xs text-muted-foreground">Branch Managers and Super Admins manage shared classes.</p>}
    </div>
  );
}

// ---------------------------------------------------------------- participation

export function ReviewParticipationDialog({ row }: { row: Participation }) {
  const review = useDelivery(
    (v: { match_status: "Matched" | "Dismissed"; user_id?: number | null; note?: string }) => deliveryApi.reviewParticipation(row.participation_id, v),
    "Review recorded",
  );
  return (
    <ActionDialog
      trigger={
        <Button size="sm" variant="outline">
          Review
        </Button>
      }
      title="Review an unmatched participant"
      description={`${row.participant_name ?? "Unnamed"}${row.participant_email ? ` · ${row.participant_email}` : ""}. Participation is evidence only; it is never attendance.`}
      fields={[
        { name: "match_status", label: "Decision", type: "select", options: [{ value: "Matched", label: "Match to a person" }, { value: "Dismissed", label: "Dismiss" }] },
        { name: "user_id", label: "User ID to match", type: "number", min: 1, required: true, showIf: (v) => v["match_status"] === "Matched" },
        { name: "note", label: "Note", type: "textarea" },
      ]}
      submitLabel="Save review"
      onSubmit={(v) =>
        review.mutateAsync({ match_status: v["match_status"] as "Matched" | "Dismissed", user_id: v["user_id"] ? Number(v["user_id"]) : null, note: v["note"] || undefined })
      }
    />
  );
}

function ParticipationTab({ target, ops }: { target: ClassTarget; ops: SessionOperations }) {
  const record = useDelivery(
    (body: Parameters<typeof deliveryApi.recordParticipation>[1]) => deliveryApi.recordParticipation(target.session_id, body),
    "Participation recorded",
  );
  return (
    <div className="space-y-3">
      <DataTable
        caption="Meet participation"
        rows={ops.participation}
        getKey={(p) => p.participation_id}
        empty="No participation recorded for this class."
        cols={[
          { h: "Participant", c: (p: Participation) => <>{p.participant_name ?? "—"}<div className="text-xs text-muted-foreground">{p.participant_email}</div></> },
          { h: "Joined", c: (p: Participation) => fmtDate(p.joined_at) },
          { h: "Source", c: (p: Participation) => p.source },
          {
            h: "Match",
            c: (p: Participation) => (
              <>
                <StatusBadge domain="approval" code={p.match_status} />
                {p.matched_user && <div className="text-xs text-muted-foreground">{p.matched_user.full_name}</div>}
              </>
            ),
          },
          { h: "", c: (p: Participation) => (p.match_status === "Unmatched" ? <ReviewParticipationDialog row={p} /> : "—") },
        ]}
      />
      <ActionDialog
        trigger={<Button size="sm">Record participation</Button>}
        title="Record a participant"
        description="Matched by email to staff or a seated student; otherwise Unmatched for review. It is evidence only; attendance is marked separately."
        fields={[
          { name: "source", label: "Source", type: "select", options: opt(["Manual", "Meet API"]) },
          { name: "participant_name", label: "Name" },
          { name: "participant_email", label: "Email" },
          { name: "joined_at", label: "Joined (IST)", type: "datetime", required: true, value: toIstInput(target.starts_at) },
          { name: "left_at", label: "Left (IST)", type: "datetime", value: toIstInput(target.ends_at) },
        ]}
        submitLabel="Record"
        onSubmit={(v) =>
          record.mutateAsync({
            source: v["source"],
            entries: [
              {
                participant_name: v["participant_name"] || undefined,
                participant_email: v["participant_email"] || undefined,
                joined_at: fromIstInput(v["joined_at"]!),
                left_at: v["left_at"] ? fromIstInput(v["left_at"]) : undefined,
              },
            ],
          })
        }
      />
    </div>
  );
}

// ---------------------------------------------------------------- the dialog

export function ClassOperationsDialog({ target, trigger }: { target: ClassTarget; trigger?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<(typeof TABS)[number]>("People");
  const query = useQuery({ queryKey: ["delivery", "session-operations", target.session_id], queryFn: () => deliveryApi.sessionOperations(target.session_id), enabled: open });
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button size="sm" variant="outline">
            Manage class
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>{target.title}</DialogTitle>
          <DialogDescription>
            {target.session_code} · {target.batch.batch_code} · {fmtRange(target.starts_at, target.ends_at)}
          </DialogDescription>
        </DialogHeader>
        <PillTabs label="Class operations" tabs={TABS} value={tab} onChange={setTab} />
        <QueryView query={query}>
          {(ops) => (
            <>
              {tab === "People" && <People target={target} ops={ops} />}
              {tab === "Incidents and disruptions" && <Incidents target={target} ops={ops} />}
              {tab === "Cover" && <Cover target={target} ops={ops} />}
              {tab === "Shared batches" && <Shared target={target} ops={ops} />}
              {tab === "Participation" && <ParticipationTab target={target} ops={ops} />}
            </>
          )}
        </QueryView>
      </DialogContent>
    </Dialog>
  );
}
