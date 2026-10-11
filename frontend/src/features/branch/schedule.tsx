/** Schedule & calendar: the week at a glance by batch or trainer (or a list), what needs a decision on top, and New class. */
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { deliveryApi, type Batch, type ClassSession, type RescheduleRequest } from "@/api/delivery";
import { useActing } from "@/auth/acting";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, PageHead, PillTabs, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ActionDialog, StateBadge, fmtRange, fmtTime, useCanManage, useIsManager } from "@/features/shared/delivery-ui";
import { useDelivery } from "@/features/shared/sessions";
import { AcademicCalendar } from "@/features/shared/academic-calendar";
import { todayIso } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ClassActions, ClassDetails } from "./class-actions";
import { BranchPicker } from "./my-work";
import { NewClassDialog } from "./new-class";

type View = "week" | "list";
type By = "batch" | "trainer";
const VIEWS = ["Week", "List"] as const;
const WHEN = ["Coming up", "Past", "All"] as const;
const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAY_MS = 86_400_000;

// ---------------------------------------------------------------- dates (IST calendar days as YYYY-MM-DD)

const addDays = (day: string, n: number) => new Date(new Date(`${day}T12:00:00Z`).getTime() + n * DAY_MS).toISOString().slice(0, 10);
/** The Monday of the week that holds `day`. */
const mondayOf = (day: string) => addDays(day, -((new Date(`${day}T12:00:00Z`).getUTCDay() + 6) % 7));
const dayOfIso = (iso: string) => new Date(new Date(iso).getTime() + 5.5 * 3600 * 1000).toISOString().slice(0, 10);
const dayLabel = (day: string) => new Date(`${day}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
const weekLabel = (monday: string) => `${dayLabel(monday)} – ${dayLabel(addDays(monday, 6))}`;

const batchName = (b: { display_name?: string | null; batch_code: string }) => b.display_name ?? b.batch_code;

// ---------------------------------------------------------------- Needs decision

function RequestRow({ request }: { request: RescheduleRequest }) {
  const approver = useIsManager();
  const approve = useDelivery(
    (v: { id: number; body: Parameters<typeof deliveryApi.approveRequest>[1] }) => deliveryApi.approveRequest(v.id, v.body),
    "Approved. The class moved and everyone has been told.",
  );
  const reject = useDelivery((v: { id: number; note: string }) => deliveryApi.rejectRequest(v.id, v.note), "Not approved. The trainer has been told.");
  const [dialog, setDialog] = useState<"approve" | "reject" | null>(null);
  const soon = new Date(request.session.starts_at).getTime() - Date.now() < DAY_MS;
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-2.5">
      <div className="min-w-0">
        <p className="text-sm font-medium">
          {request.requested_by.full_name} asks to move "{request.session.title}"
        </p>
        <p className="text-xs text-muted-foreground">
          {batchName(request.session.batch)} · now {fmtRange(request.session.starts_at, request.session.ends_at)} · asks for{" "}
          {fmtRange(request.proposed_starts_at, request.proposed_ends_at)} · {request.reason}
        </p>
      </div>
      {approver && (
        <div className="flex items-center gap-1.5">
          <Button size="sm" onClick={() => setDialog("approve")}>
            Approve
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="outline" aria-label={`More for the request about ${request.session.title}`}>
                More
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => setDialog("reject")}>Do not approve</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}
      {dialog === "approve" && (
        <ActionDialog
          open
          onOpenChange={(open) => !open && setDialog(null)}
          title={`Move "${request.session.title}"?`}
          description="The class moves to the time the trainer asked for. The students and the trainer are told."
          fields={[
            { name: "note", label: "Note to the trainer", type: "textarea" },
            {
              name: "emergency_reason",
              label: "Emergency reason",
              type: "textarea",
              required: soon,
              hint: soon ? "The class starts within 24 hours, so this is needed" : "Only needed when the class starts within 24 hours",
            },
            { name: "next_action", label: "What happens next for the students", type: "textarea", required: soon },
            { name: "override_reason", label: "Why the warning is acceptable", type: "textarea", required: true, afterWarnings: true },
          ]}
          submitLabel="Approve"
          onSubmit={(v) =>
            approve.mutateAsync({
              id: request.request_id,
              body: {
                note: v["note"] || undefined,
                override_reason: v["override_reason"] || undefined,
                emergency_reason: v["emergency_reason"] || undefined,
                next_action: v["next_action"] || undefined,
              },
            })
          }
        />
      )}
      {dialog === "reject" && (
        <ActionDialog
          open
          onOpenChange={(open) => !open && setDialog(null)}
          title="Do not approve this request"
          description="The class stays where it is. The trainer is told why."
          fields={[{ name: "note", label: "Why (the trainer sees this)", type: "textarea", required: true }]}
          submitLabel="Do not approve"
          onSubmit={(v) => reject.mutateAsync({ id: request.request_id, note: v["note"]! })}
        />
      )}
    </li>
  );
}

/** Trainers' reschedule requests and proposed extra, remedial or replacement classes, with the count. */
export function NeedsDecision({ branchId, highlight }: { branchId: number | null; highlight?: boolean }) {
  const requests = useQuery({
    queryKey: ["delivery", "requests", "open", branchId],
    queryFn: () => deliveryApi.requests({ status: "Open", branch_id: branchId }),
  });
  const proposed = useQuery({
    queryKey: ["delivery", "sessions", "pending-approval", branchId],
    queryFn: () => deliveryApi.sessions({ approval_status: "Pending", upcoming: true, branch_id: branchId }),
  });
  useEffect(() => {
    if (highlight && requests.data && proposed.data) document.getElementById("needs-decision")?.scrollIntoView({ block: "start" });
  }, [highlight, requests.data, proposed.data]);
  if (requests.isPending || proposed.isPending) return null;
  const list = requests.data?.data ?? [];
  const classes = proposed.data?.data ?? [];
  const total = list.length + classes.length;
  if (total === 0) return null;
  return (
    <section
      id="needs-decision"
      aria-label="Needs decision"
      className={cn("rounded-xl border bg-card p-4 shadow-sm sm:p-5", highlight && "ring-2 ring-primary/40")}
    >
      <h2 className="mb-1 flex items-center gap-2 text-base font-semibold">
        Needs decision <span className="rounded-full bg-primary/10 px-2 text-sm text-primary">{total}</span>
      </h2>
      <ul className="divide-y">
        {list.map((r) => (
          <RequestRow key={`r${r.request_id}`} request={r} />
        ))}
        {classes.map((s) => (
          <li key={`c${s.session_id}`} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
            <div className="min-w-0">
              <p className="text-sm font-medium">
                {s.purpose} class "{s.title}" is waiting for approval
              </p>
              <p className="text-xs text-muted-foreground">
                {batchName(s.batch)} · {fmtRange(s.starts_at, s.ends_at)}
                {s.purpose_reference ? ` · ${s.purpose_reference}` : ""}
              </p>
            </div>
            <ClassActions session={s} />
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------------------------------------------------------------- week

function Chip({ session, onOpen }: { session: ClassSession; onOpen: (s: ClassSession) => void }) {
  const cancelled = session.state === "Cancelled";
  const pending = session.approval_status === "Pending";
  return (
    <button
      type="button"
      onClick={() => onOpen(session)}
      aria-label={`${session.title}, ${fmtRange(session.starts_at, session.ends_at)}, ${session.state_label}`}
      className={cn(
        "block w-full rounded-md border-l-4 bg-muted/60 px-2 py-1 text-left text-xs hover:bg-accent",
        cancelled
          ? "border-neutral text-muted-foreground line-through"
          : pending
            ? "border-warning"
            : session.state === "Live"
              ? "border-success"
              : "border-primary",
      )}
    >
      <span className="font-medium tabular-nums">{fmtTime(session.starts_at)}</span> {session.title}
      {pending && <span className="block text-warning">Waiting for approval</span>}
    </button>
  );
}

function WeekCalendar({ sessions, monday, by, onOpen }: { sessions: ClassSession[]; monday: string; by: By; onOpen: (s: ClassSession) => void }) {
  const days = DAY_NAMES.map((name, i) => ({ name, date: addDays(monday, i) }));
  const today = todayIso();
  const rows = useMemo(() => {
    const map = new Map<string, { label: string; sessions: ClassSession[] }>();
    for (const s of sessions) {
      const key = by === "batch" ? `b${s.batch.batch_id}` : `t${s.trainer.user_id}`;
      const entry = map.get(key) ?? { label: by === "batch" ? batchName(s.batch) : s.trainer.full_name, sessions: [] };
      entry.sessions.push(s);
      map.set(key, entry);
    }
    return [...map.entries()].map(([key, v]) => ({ key, ...v })).sort((a, b) => a.label.localeCompare(b.label));
  }, [sessions, by]);

  return (
    <>
      <div className="hidden overflow-x-auto rounded-xl border bg-card md:block">
        <table className="w-full min-w-[56rem] table-fixed border-collapse text-sm">
          <caption className="sr-only">Classes this week by {by}</caption>
          <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th scope="col" className="w-40 px-3 py-2 text-left font-semibold">
                {by === "batch" ? "Batch" : "Trainer"}
              </th>
              {days.map((d) => (
                <th key={d.date} scope="col" className={cn("px-2 py-2 text-left font-semibold", d.date === today && "text-primary")}>
                  {d.name} {dayLabel(d.date)}
                  {d.date === today ? " · today" : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className="border-t align-top">
                <th scope="row" className="px-3 py-2 text-left font-medium">
                  {row.label}
                </th>
                {days.map((d) => (
                  <td key={d.date} className={cn("space-y-1 px-1.5 py-1.5", d.date === today && "bg-primary/5")}>
                    {row.sessions
                      .filter((s) => dayOfIso(s.starts_at) === d.date)
                      .map((s) => (
                        <Chip key={s.session_id} session={s} onOpen={onOpen} />
                      ))}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="space-y-3 md:hidden">
        {days.map((d) => {
          const day = sessions.filter((s) => dayOfIso(s.starts_at) === d.date);
          return (
            <section key={d.date} aria-label={`${d.name} ${dayLabel(d.date)}`} className="rounded-xl border bg-card p-3">
              <h3 className={cn("mb-2 text-sm font-semibold", d.date === today && "text-primary")}>
                {d.name} {dayLabel(d.date)}
                {d.date === today ? " · today" : ""}
              </h3>
              {day.length === 0 ? (
                <p className="text-xs text-muted-foreground">No classes.</p>
              ) : (
                <ul className="space-y-1.5">
                  {day.map((s) => (
                    <li key={s.session_id}>
                      <Chip session={s} onOpen={onOpen} />
                      <p className="px-2 text-xs text-muted-foreground">{by === "batch" ? s.trainer.full_name : batchName(s.batch)}</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          );
        })}
      </div>
    </>
  );
}

// ---------------------------------------------------------------- the screen

export function BranchSchedule() {
  const manager = useCanManage();
  const { branchId } = useActing("branch");
  const search = useSearch({ from: "/branch/schedule" });
  const navigate = useNavigate({ from: "/branch/schedule" });
  const view: View = search.view ?? "week";
  const by: By = search.by ?? "batch";
  const monday = mondayOf(search.week ?? todayIso());
  const [when, setWhen] = useState<(typeof WHEN)[number]>("Coming up");
  const [trainer, setTrainer] = useState("");
  const [open, setOpen] = useState<ClassSession | null>(null);
  const [replacing, setReplacing] = useState<ClassSession | null>(null);
  const set = (next: Partial<{ view: View; by: By; week: string; batch: number | undefined }>) =>
    void navigate({ search: (prev) => ({ ...prev, ...next }), replace: true });

  const batches = useQuery({ queryKey: ["delivery", "batches", "schedule", branchId], queryFn: () => deliveryApi.batches({ branch_id: branchId }) });
  const openBatches = (batches.data?.data ?? []).filter((b) => !["Completed", "Cancelled", "Archived", "On Hold"].includes(b.state));
  const trainers = useMemo(() => {
    const seen = new Map<number, string>();
    for (const b of batches.data?.data ?? []) for (const t of b.trainers) seen.set(t.user_id, t.full_name);
    return [...seen.entries()].map(([value, label]) => ({ value, label }));
  }, [batches.data]);

  const weekSessions = useQuery({
    queryKey: ["delivery", "sessions", "week", monday, search.batch, branchId],
    queryFn: () => deliveryApi.sessions({ from: monday, to: addDays(monday, 6), batch_id: search.batch, branch_id: branchId }),
    enabled: view === "week",
  });
  const listSessions = useQuery({
    queryKey: ["delivery", "sessions", "list", when, search.batch, trainer, branchId],
    queryFn: () =>
      deliveryApi.sessions({
        window: when === "Coming up" ? "coming" : when === "Past" ? "past" : undefined,
        batch_id: search.batch,
        trainer_user_id: trainer || undefined,
        branch_id: branchId,
      }),
    enabled: view === "list",
  });

  const newClass = (
    <NewClassDialog
      batches={openBatches}
      {...(search.batch ? { batchId: search.batch } : {})}
      trigger={<Button disabled={openBatches.length === 0}>New class</Button>}
    />
  );

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHead
        title="Schedule & calendar"
        description="See every class by week or as a list, decide what is waiting, and schedule new classes."
        actions={
          <>
            <BranchPicker />
            {manager && newClass}
          </>
        }
      />
      <NeedsDecision branchId={branchId} highlight={!!search.decide} />

      <div className="flex flex-wrap items-center gap-3">
        <PillTabs label="View" tabs={VIEWS} value={view === "week" ? "Week" : "List"} onChange={(tab) => set({ view: tab === "Week" ? "week" : "list" })} />
        <div className="mb-4 w-full max-w-xs">
          <NativeSelect
            aria-label="Filter by batch"
            placeholder="All batches"
            options={(batches.data?.data ?? []).map((b: Batch) => ({ value: b.batch_id, label: `${batchName(b)} — ${b.course.course_code}` }))}
            value={search.batch ?? ""}
            onChange={(e) => set({ batch: e.target.value ? Number(e.target.value) : undefined })}
          />
        </div>
        {view === "week" ? (
          <div className="mb-4 w-full max-w-[11rem]">
            <NativeSelect
              aria-label="Group by"
              value={by}
              onChange={(e) => set({ by: e.target.value as By })}
              options={[
                { value: "batch", label: "By batch" },
                { value: "trainer", label: "By trainer" },
              ]}
            />
          </div>
        ) : (
          <div className="mb-4 w-full max-w-xs">
            <NativeSelect
              aria-label="Filter by trainer"
              placeholder="All trainers"
              options={trainers}
              value={trainer}
              onChange={(e) => setTrainer(e.target.value)}
            />
          </div>
        )}
      </div>

      {view === "week" ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="outline" aria-label="Previous week" onClick={() => set({ week: addDays(monday, -7) })}>
              <ChevronLeft className="size-4" aria-hidden />
            </Button>
            <span className="min-w-40 text-center text-sm font-medium" aria-live="polite">
              {weekLabel(monday)}
            </span>
            <Button size="sm" variant="outline" aria-label="Next week" onClick={() => set({ week: addDays(monday, 7) })}>
              <ChevronRight className="size-4" aria-hidden />
            </Button>
            <Button size="sm" variant="ghost" onClick={() => set({ week: mondayOf(todayIso()) })}>
              This week
            </Button>
          </div>
          <QueryView
            query={weekSessions}
            isEmpty={(page) => page.data.length === 0}
            empty="No classes are scheduled this week. Create classes from a batch's timetable, or add one."
            emptyAction={
              manager ? (
                <Button asChild size="sm" variant="outline">
                  <Link to="/branch/batches">Open Batches</Link>
                </Button>
              ) : undefined
            }
          >
            {(page) => (
              <>
                <WeekCalendar sessions={page.data} monday={monday} by={by} onOpen={setOpen} />
                {page.meta.total > page.data.length && (
                  <p className="text-xs text-muted-foreground">
                    Showing the first {page.data.length} of {page.meta.total} classes. Pick a batch to narrow it down.
                  </p>
                )}
              </>
            )}
          </QueryView>
        </>
      ) : (
        <>
          <PillTabs label="Which classes" tabs={WHEN} value={when} onChange={setWhen} />
          <QueryView query={listSessions}>
            {(page) => (
              <DataTable
                caption="Classes"
                rows={page.data}
                getKey={(s) => s.session_id}
                empty="No classes match."
                cols={[
                  { h: "When (IST)", c: (s) => fmtRange(s.starts_at, s.ends_at) },
                  {
                    h: "Class",
                    c: (s) => (
                      <>
                        <div className="font-medium">{s.title}</div>
                        <div className="text-xs text-muted-foreground">
                          {batchName(s.batch)} · {s.mode}
                          {s.room ? ` · ${s.room}` : ""}
                          {s.topic ? ` · ${s.topic.title}` : ""}
                        </div>
                        {s.purpose !== "Regular" && <div className="text-xs text-info">{s.purpose} class</div>}
                      </>
                    ),
                  },
                  { h: "Trainer", c: (s) => s.trainer.full_name },
                  {
                    h: "State",
                    c: (s) => (
                      <div className="flex flex-wrap items-center gap-1">
                        <StateBadge label={s.state_label} />
                        {s.approval_status === "Pending" && <StatusBadge domain="approval" code="Pending" label="Waiting for approval" />}
                        {s.mode !== "Classroom" && s.meet_status !== "Linked" && s.state !== "Cancelled" && (
                          <span className="text-xs text-warning">No Meet link</span>
                        )}
                      </div>
                    ),
                  },
                  { h: "", c: (s) => <ClassActions session={s} onReplace={setReplacing} /> },
                ]}
              />
            )}
          </QueryView>
        </>
      )}

      {open && (
        <ClassDetails
          session={open}
          onClose={() => setOpen(null)}
          onReplace={(s) => {
            setOpen(null);
            setReplacing(s);
          }}
        />
      )}
      {replacing && <NewClassDialog batches={openBatches} replaces={replacing} open onOpenChange={(o) => !o && setReplacing(null)} />}

      <Section title="Holidays and closures" className="mt-2">
        <AcademicCalendar />
      </Section>
      <HowThisWorks>
        <p>A class moves or is cancelled only by you; trainers ask, and you decide. Students and the trainer are told each time.</p>
        <p>
          A trainer who already teaches at that time stops a class from being scheduled. A booked room or a student clash is a warning you can accept with a
          reason.
        </p>
        <p>Holidays and closures you record under Holidays and closures are skipped when classes are created from a batch's timetable.</p>
      </HowThisWorks>
    </div>
  );
}
