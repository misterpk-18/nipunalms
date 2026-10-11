/** Waiting for a batch: every student with an admission and no seat yet, the batches that could take them and a one-click Allocate. */
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { branchApi, type WaitingBatch, type WaitingMatch, type WaitingRow } from "@/api/branch";
import { deliveryApi } from "@/api/delivery";
import { useActing } from "@/auth/acting";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, QueryView, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PrepareMapping } from "@/features/academic/curriculum-model";
import { useCanManage } from "@/features/shared/delivery-ui";
import { fmtDate } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { BranchPicker } from "./my-work";

/** "Mon, Wed · 15:00–17:00 · Lab 2" or "Timetable not set yet". */
export function timetableText(b: Pick<WaitingBatch, "schedule_days" | "start_time" | "end_time" | "location">): string {
  const parts = [b.schedule_days.join(", "), b.start_time && b.end_time ? `${b.start_time}–${b.end_time}` : "", b.location ?? ""].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Timetable not set yet";
}

export const batchName = (b: Pick<WaitingBatch, "display_name" | "batch_code">) => b.display_name ?? b.batch_code;

/** Allocates one student (or one track of a combo) to the batch. A match with warnings asks first and lists them. */
export function AllocateButton({ row, match, onDone }: { row: WaitingRow; match: WaitingMatch; onDone?: () => void }) {
  const allocate = useApiMutation(
    () =>
      deliveryApi.allocate(match.batch.batch_id, {
        enrolment_id: row.enrolment.enrolment_id,
        enrolment_track_id: match.track?.enrolment_track_id ?? null,
        acknowledge_warnings: match.warnings.length > 0,
      }),
    {
      success: `${row.student.full_name} is in ${batchName(match.batch)}`,
      next: "The student has been told. Their Joining Date is set when they attend the first class.",
      view: { to: `/branch/batches/${match.batch.batch_id}`, label: "View batch" },
      invalidate: [["branch"], ["delivery"], ["nav"]],
      onSuccess: onDone,
    },
  );
  const label = match.track ? `Allocate ${match.track.track_code}` : "Allocate";
  if (match.warnings.length === 0)
    return (
      <Button size="sm" disabled={allocate.isPending} onClick={() => allocate.mutate(undefined)}>
        {label}
      </Button>
    );
  return (
    <ConfirmDialog
      title={`Allocate ${row.student.full_name} to ${batchName(match.batch)}?`}
      consequence={<>Check before you go on: {match.warnings.join(" ")} The student is told about the batch.</>}
      confirmLabel="Allocate anyway"
      onConfirm={() => allocate.mutateAsync(undefined)}
    >
      <Button size="sm" variant="outline">
        {label}…
      </Button>
    </ConfirmDialog>
  );
}

function MatchLine({ row, match, manage }: { row: WaitingRow; match: WaitingMatch; manage: boolean }) {
  const b = match.batch;
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-2.5">
      <div className="min-w-0">
        <p className="text-sm font-medium">
          <Link to="/branch/batches/$id" params={{ id: String(b.batch_id) }} className="text-primary underline-offset-2 hover:underline">
            {batchName(b)}
          </Link>{" "}
          <span className="font-mono text-xs text-muted-foreground">{b.batch_code}</span>
          {match.track && (
            <span className="ml-2">
              <Tag tone="info">{`Track ${match.track.track_code}: ${match.track.track_name}`}</Tag>
            </span>
          )}
        </p>
        <p className="text-xs text-muted-foreground">
          {b.state_label} · {b.seats_left} seat{b.seats_left === 1 ? "" : "s"} left of {b.capacity} · {timetableText(b)}
          {b.planned_start ? ` · starts ${fmtDate(b.planned_start)}` : ""}
          {b.trainers.length ? ` · ${b.trainers.join(", ")}` : " · no trainer yet"}
        </p>
        {match.warnings.length > 0 && <p className="text-xs text-warning">{match.warnings.join(" ")}</p>}
      </div>
      {manage && <AllocateButton row={row} match={match} />}
    </li>
  );
}

export function WaitingStudent({ row, manage, withBranch }: { row: WaitingRow; manage: boolean; withBranch: boolean }) {
  return (
    <li className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium">
            {row.student.full_name} <span className="font-mono text-xs text-muted-foreground">{row.student.student_code}</span>
          </p>
          <p className="text-sm text-muted-foreground">
            {row.course.title} · {row.mode}
            {withBranch ? ` · ${row.branch.branch_name}` : ""} · waiting {row.waiting_days} day{row.waiting_days === 1 ? "" : "s"}
          </p>
        </div>
        {row.allocation_due_on && (
          <Tag tone={row.overdue ? "danger" : "neutral"}>
            {row.overdue ? `Allocate by ${fmtDate(row.allocation_due_on)}: overdue` : `Allocate by ${fmtDate(row.allocation_due_on)}`}
          </Tag>
        )}
      </div>
      {manage && (
        <div className="mt-1">
          <PrepareMapping enrolmentId={row.enrolment.enrolment_id} courseId={row.course.course_id} />
        </div>
      )}
      {row.matches.length === 0 ? (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted/50 px-3 py-2 text-sm">
          <span>
            No open batch of {row.course.course_code} at {row.branch.branch_name} has a seat left.
          </span>
          {manage && row.blocked.length === 0 && (
            <Button asChild size="sm" variant="outline">
              <Link to="/branch/batches" search={{ new: 1, course: row.course.course_id }}>
                Create a batch
              </Link>
            </Button>
          )}
        </div>
      ) : (
        <ul className="mt-2 divide-y">
          {row.matches.map((m) => (
            <MatchLine key={`${m.batch.batch_id}-${m.track?.enrolment_track_id ?? 0}`} row={row} match={m} manage={manage} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function BranchWaiting() {
  const manage = useCanManage();
  const { branchId, branches } = useActing("branch");
  const [q, setQ] = useState("");
  const search = q.trim();
  const query = useQuery({
    queryKey: ["branch", "waiting", branchId, search],
    queryFn: () => branchApi.waiting({ branch_id: branchId, q: search || undefined }),
  });
  const total = query.data?.meta.total;
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead
        title="Waiting for a batch"
        description="Students who have joined and have no batch yet. Each one shows the batches that could take them; allocate in one click."
        actions={<BranchPicker />}
      />
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 rounded-xl border bg-card px-4 py-2" role="status">
          <Users className="size-5 text-muted-foreground" aria-hidden />
          <span className="text-2xl font-semibold tabular-nums">{total ?? "…"}</span>
          <span className="text-sm text-muted-foreground">{total === 1 ? "student waiting" : "students waiting"}</span>
        </div>
        <Input
          className="max-w-sm"
          aria-label="Search the waiting list"
          placeholder="Search by name, mobile or admission number"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <QueryView
        query={query}
        skeleton="cards"
        isEmpty={(page) => page.data.length === 0}
        empty={
          search ? "No waiting student matches that search." : "Nobody is waiting for a batch. New admissions from the CRM appear here until they have a seat."
        }
        emptyAction={
          manage ? (
            <Button asChild size="sm" variant="outline">
              <Link to="/branch/batches">Open Batches</Link>
            </Button>
          ) : undefined
        }
      >
        {(page) => (
          <ul className="space-y-3" aria-label="Students waiting for a batch">
            {page.data.map((row) => (
              <WaitingStudent key={row.enrolment.enrolment_id} row={row} manage={manage} withBranch={branches.length > 1 && branchId === null} />
            ))}
          </ul>
        )}
      </QueryView>
      {query.data && query.data.meta.pages > 1 && (
        <p className="text-xs text-muted-foreground">
          Showing the {query.data.data.length} students who have waited longest. Allocate some, or search for a name.
        </p>
      )}
      <HowThisWorks>
        <p>A batch is offered when it teaches the student's course at their branch and has a seat left. Closed, on-hold and full batches are not listed.</p>
        <p>
          "Allocate…" with dots means the check found something to look at, such as a different class mode or a timetable clash. You see it before you confirm.
        </p>
        <p>A student's Joining Date is set when they attend their first class, not when they are allocated.</p>
      </HowThisWorks>
    </div>
  );
}
