/** Academic calendar: a month grid or a list (what is ahead first) of company holidays and branch closures, with Add, Edit and Cancel. */
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CalendarDays, ChevronLeft, ChevronRight, List, Plus } from "lucide-react";
import { calendarApi, calendarKeys, type Closure, type ClosureKind } from "@/api/calendar";
import { useAuth } from "@/auth/auth";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { AddClosureDialog, CancelClosureDialog, DecideClosureDialog, EditClosureDialog, rangeText } from "./calendar-dialogs";
import { Pager } from "./shared";
import { pageOf, useUrlParams } from "./url-params";

const istToday = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
const iso = (d: Date) => d.toISOString().slice(0, 10);
const monthOf = (date: string) => date.slice(0, 7);
const addMonths = (month: string, n: number) => {
  const [y, m] = month.split("-").map(Number) as [number, number];
  return iso(new Date(Date.UTC(y, m - 1 + n, 1))).slice(0, 7);
};
const monthTitle = (month: string) => new Date(`${month}-01T00:00:00Z`).toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });

/** The 6 x 7 days a month grid shows, Monday first. */
function gridDays(month: string): string[] {
  const [y, m] = month.split("-").map(Number) as [number, number];
  const first = new Date(Date.UTC(y, m - 1, 1));
  const start = new Date(first.getTime() - ((first.getUTCDay() + 6) % 7) * 86_400_000);
  return Array.from({ length: 42 }, (_, i) => iso(new Date(start.getTime() + i * 86_400_000)));
}

/** Can this entry still be changed? Not when it is over, cancelled or rejected. */
const changeable = (c: Closure) => c.status !== "Cancelled" && c.status !== "Rejected" && c.ends_on >= istToday();

type Dialog = { kind: "add"; date?: string } | { kind: "edit" | "cancel" | "decide" | "open"; closure: Closure };

function chipClass(c: Closure) {
  if (c.status === "Pending") return "border border-dashed border-warning bg-warning-soft text-warning";
  if (c.status === "Cancelled" || c.status === "Rejected") return "bg-muted text-muted-foreground line-through";
  return c.kind === "Company Holiday" ? "bg-info-soft text-info" : "bg-warning-soft text-warning";
}

function MonthGrid({
  month,
  today,
  onOpen,
  onAdd,
  canAdd,
}: {
  month: string;
  today: string;
  onOpen: (c: Closure) => void;
  onAdd: (date: string) => void;
  canAdd: boolean;
}) {
  const days = gridDays(month);
  const query = useQuery({
    queryKey: [...calendarKeys.all, "window", days[0], days[41]],
    queryFn: () => calendarApi.inWindow(days[0]!, days[41]!),
    placeholderData: keepPreviousData,
  });
  return (
    <QueryView query={query} skeleton="detail">
      {(closures) => {
        const shown = closures.filter((c) => c.status !== "Cancelled" && c.status !== "Rejected");
        return (
          <div role="grid" aria-label={monthTitle(month)} className="overflow-hidden rounded-xl border bg-card">
            <div role="row" className="grid grid-cols-7 border-b bg-muted/50 text-center text-xs font-medium text-muted-foreground">
              {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                <div key={d} role="columnheader" className="py-1.5">
                  {d}
                </div>
              ))}
            </div>
            {Array.from({ length: 6 }, (_, w) => days.slice(w * 7, w * 7 + 7)).map((week) => (
              <div key={week[0]} role="row" className="grid grid-cols-7">
                {week.map((day) => {
                  const here = shown.filter((c) => c.starts_on <= day && day <= c.ends_on);
                  const inMonth = monthOf(day) === month;
                  return (
                    <div
                      key={day}
                      role="gridcell"
                      aria-label={day}
                      className={cn(
                        "min-h-16 min-w-0 border-b border-r p-1 sm:min-h-24",
                        !inMonth && "bg-muted/30 text-muted-foreground",
                        day === today && "ring-2 ring-inset ring-primary",
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium">{Number(day.slice(8))}</span>
                        {canAdd && day >= today && (
                          <button
                            type="button"
                            aria-label={`Add on ${day}`}
                            onClick={() => onAdd(day)}
                            className="hidden rounded p-0.5 text-muted-foreground hover:bg-accent sm:block"
                          >
                            <Plus className="size-3" aria-hidden />
                          </button>
                        )}
                      </div>
                      <div className="mt-0.5 space-y-0.5">
                        {here.slice(0, 2).map((c) => (
                          <button
                            key={c.closure_id}
                            type="button"
                            data-closure={c.closure_id}
                            onClick={() => onOpen(c)}
                            title={`${c.title}${c.branch ? ` (${c.branch.branch_name})` : ""}`}
                            className={cn("block w-full truncate rounded px-1 py-0.5 text-left text-[10px] leading-tight sm:text-xs", chipClass(c))}
                          >
                            {c.title}
                          </button>
                        ))}
                        {here.length > 2 && <span className="block px-1 text-[10px] text-muted-foreground">+{here.length - 2} more</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        );
      }}
    </QueryView>
  );
}

function Actions({ closure, canEdit, canDecide, onDialog }: { closure: Closure; canEdit: boolean; canDecide: boolean; onDialog: (d: Dialog) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {canDecide && closure.status === "Pending" && (
        <Button size="sm" onClick={() => onDialog({ kind: "decide", closure })}>
          Decide
        </Button>
      )}
      {canEdit && changeable(closure) && (
        <>
          <Button size="sm" variant="outline" onClick={() => onDialog({ kind: "edit", closure })} aria-label={`Edit ${closure.title}`}>
            Edit
          </Button>
          <Button size="sm" variant="outline" onClick={() => onDialog({ kind: "cancel", closure })} aria-label={`Cancel ${closure.title}`}>
            Cancel
          </Button>
        </>
      )}
    </div>
  );
}

function ClosureList({ canEdit, canDecide, onDialog }: { canEdit: boolean; canDecide: boolean; onDialog: (d: Dialog) => void }) {
  const [params, setParams] = useUrlParams();
  const page = pageOf(params);
  const query = useQuery({
    queryKey: [...calendarKeys.all, "list", page],
    queryFn: () => calendarApi.list({ sort: "upcoming", page }),
    placeholderData: keepPreviousData,
  });
  return (
    <QueryView
      query={query}
      isEmpty={(p) => p.data.length === 0}
      empty="No holidays or closures yet. Weekends and bank holidays are working days until they are added here."
      emptyAction={
        canEdit ? (
          <Button size="sm" onClick={() => onDialog({ kind: "add" })}>
            Add holiday or closure
          </Button>
        ) : undefined
      }
    >
      {(result) => (
        <>
          <ul className="divide-y rounded-xl border bg-card shadow-sm" aria-label="Holidays and closures">
            {result.data.map((c) => (
              <li key={c.closure_id} className="flex flex-wrap items-start justify-between gap-3 p-4" data-closure={c.closure_id}>
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-semibold">{c.title}</h3>
                    <StatusBadge domain="approval" code={c.status} />
                    <Tag tone={c.kind === "Company Holiday" ? "info" : "warning"}>{c.branch?.branch_name ?? "Every branch"}</Tag>
                  </div>
                  <p className="text-sm text-muted-foreground">{rangeText(c)}</p>
                  {c.reason && <p className="text-xs text-muted-foreground">{c.reason}</p>}
                  {c.cancel_reason && <p className="text-xs text-muted-foreground">Cancelled: {c.cancel_reason}</p>}
                </div>
                <Actions closure={c} canEdit={canEdit} canDecide={canDecide} onDialog={onDialog} />
              </li>
            ))}
          </ul>
          <Pager meta={result.meta} onPage={(p) => setParams({ page: String(p) })} />
        </>
      )}
    </QueryView>
  );
}

export function AdminCalendar() {
  const { hasRole } = useAuth();
  const [params, setParams] = useUrlParams();
  const today = istToday();
  const view = params["view"] === "list" ? "list" : "month";
  const month = /^\d{4}-\d{2}$/.test(params["month"] ?? "") ? (params["month"] as string) : monthOf(today);
  const central = hasRole("FOUNDER_CEO", "SUPER_ADMIN");
  const canEdit = hasRole("SUPER_ADMIN");
  const kinds: ClosureKind[] = [...(central ? (["Company Holiday"] as const) : []), ...(canEdit ? (["Branch Closure"] as const) : [])];
  const [dialog, setDialog] = useState<Dialog | null>(params["add"] === "1" && kinds.length ? { kind: "add" } : null);
  const close = () => {
    setDialog(null);
    if (params["add"]) setParams({ add: undefined });
  };

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead
        title="Academic calendar"
        description="Company holidays and branch closures. Classes are never moved for you: Branch Managers are asked to replace the ones that fall on these dates."
        actions={
          kinds.length > 0 && (
            <Button onClick={() => setDialog({ kind: "add" })}>
              <Plus className="size-4" aria-hidden /> Add holiday / closure
            </Button>
          )
        }
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="View" className="inline-flex rounded-lg border bg-card p-0.5">
          {(
            [
              ["month", "Month", CalendarDays],
              ["list", "List", List],
            ] as const
          ).map(([key, label, Icon]) => (
            <button
              key={key}
              type="button"
              aria-pressed={view === key}
              onClick={() => setParams({ view: key === "month" ? undefined : key, page: undefined })}
              className={cn(
                "tap inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium",
                view === key ? "bg-primary text-primary-foreground" : "hover:bg-accent",
              )}
            >
              <Icon className="size-4" aria-hidden /> {label}
            </button>
          ))}
        </div>
        {view === "month" && (
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" aria-label="Previous month" onClick={() => setParams({ month: addMonths(month, -1) })}>
              <ChevronLeft className="size-4" aria-hidden />
            </Button>
            <span className="min-w-36 text-center text-sm font-semibold" aria-live="polite">
              {monthTitle(month)}
            </span>
            <Button variant="outline" size="icon" aria-label="Next month" onClick={() => setParams({ month: addMonths(month, 1) })}>
              <ChevronRight className="size-4" aria-hidden />
            </Button>
            {month !== monthOf(today) && (
              <Button variant="ghost" size="sm" onClick={() => setParams({ month: undefined })}>
                This month
              </Button>
            )}
          </div>
        )}
      </div>
      {view === "month" ? (
        <>
          <MonthGrid
            month={month}
            today={today}
            canAdd={kinds.length > 0}
            onAdd={(date) => setDialog({ kind: "add", date })}
            onOpen={(closure) => setDialog({ kind: "open", closure })}
          />
          <p className="text-xs text-muted-foreground">
            Blue is a company holiday, amber is a branch closure and a dashed edge is a closure waiting for a decision. Cancelled entries are in the list.
          </p>
        </>
      ) : (
        <ClosureList canEdit={canEdit} canDecide={canEdit} onDialog={setDialog} />
      )}
      <HowThisWorks>
        <p>
          Weekends and bank holidays count as working days until they are added here. Targets such as allocation deadlines and review times skip the days on
          this calendar.
        </p>
        <p>A branch closure proposed by a Branch Manager is approved as they record it; one proposed by someone else waits for a decision.</p>
        <p>Editing or cancelling an entry shows how many classes it touches before you confirm. A cancelled entry stays in the list.</p>
      </HowThisWorks>

      {dialog?.kind === "add" && <AddClosureDialog kinds={kinds} {...(dialog.date ? { initialDate: dialog.date } : {})} onClose={close} />}
      {dialog?.kind === "edit" && <EditClosureDialog closure={dialog.closure} onClose={close} />}
      {dialog?.kind === "cancel" && <CancelClosureDialog closure={dialog.closure} onClose={close} />}
      {dialog?.kind === "decide" && <DecideClosureDialog closure={dialog.closure} onClose={close} />}
      {dialog?.kind === "open" && (
        <Dialog open onOpenChange={(open) => !open && close()}>
          <DialogContent className="w-[calc(100vw-1.5rem)] max-w-md">
            <DialogHeader>
              <DialogTitle>{dialog.closure.title}</DialogTitle>
              <DialogDescription>
                {rangeText(dialog.closure)} · {dialog.closure.branch?.branch_name ?? "Every branch"}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-2 text-sm">
              <StatusBadge domain="approval" code={dialog.closure.status} />
              {dialog.closure.reason && <p className="text-muted-foreground">{dialog.closure.reason}</p>}
              <p className="text-xs text-muted-foreground">Added by {dialog.closure.requested_by.full_name}</p>
              <Actions closure={dialog.closure} canEdit={canEdit} canDecide={canEdit} onDialog={setDialog} />
              {!changeable(dialog.closure) && dialog.closure.status === "Approved" && (
                <p className="text-xs text-muted-foreground">This one is over, so it can't be changed.</p>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
