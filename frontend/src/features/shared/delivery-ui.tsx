/** Small pieces the delivery screens share: IST formatting, delivery progress, Meet status, and a field-driven action dialog. */
import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { Field, NativeSelect } from "@/components/lms/forms";
import { StatusBadge, type Tone } from "@/components/lms/ui";
import type { ClassSession, Delivery } from "@/api/delivery";
import { useAuth } from "@/auth/auth";
import { ApiError } from "@/api/client";

/** Whether the signed-in user may change delivery records (Academic Coordinator, Branch Manager, Super Admin). The API re-checks every change. */
export function useCanManage(): boolean {
  const { profile } = useAuth();
  return !!profile?.scopes.some((s) => s.role_code === "ACADEMIC_COORDINATOR" || s.role_code === "BRANCH_MANAGER" || s.role_code === "SUPER_ADMIN");
}

// ---------------------------------------------------------------- IST formatting (business time is always Asia/Kolkata)

const IST = "Asia/Kolkata";
const dateFormat = new Intl.DateTimeFormat("en-IN", { timeZone: IST, weekday: "short", day: "numeric", month: "short", year: "numeric" });
const timeFormat = new Intl.DateTimeFormat("en-GB", { timeZone: IST, hour: "2-digit", minute: "2-digit", hour12: false });

export const fmtDate = (iso: string) => dateFormat.format(new Date(iso));
export const fmtTime = (iso: string) => timeFormat.format(new Date(iso));
export const fmtRange = (start: string, end: string) => `${fmtDate(start)} · ${fmtTime(start)}–${fmtTime(end)} IST`;
export const fmtDay = (day: string | null) => (day ? dateFormat.format(new Date(`${day}T00:00:00+05:30`)) : "—");

// The datetime-local helpers live in lib/format (shared with the assessment screens).
export { fromIstInput, toIstInput } from "@/lib/format";

// ---------------------------------------------------------------- display

export function DeliveryBar({ delivery, label = "Sessions delivered" }: { delivery: Delivery; label?: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span>{delivery.percent === null ? "No sessions planned yet" : `${delivery.delivered} of ${delivery.planned} (${delivery.percent}%)`}</span>
      </div>
      <Progress value={delivery.percent ?? 0} aria-label={label} />
    </div>
  );
}

const MEET_TONE: Record<string, Tone> = { Associated: "success", Failed: "danger", "Pending Verification": "warning", "Not Required": "neutral" };

export function MeetBadge({ session }: { session: Pick<ClassSession, "meet_status_label"> }) {
  return <StatusBadge tone={MEET_TONE[session.meet_status_label] ?? "neutral"}>Meet: {session.meet_status_label}</StatusBadge>;
}

const STATE_TONE: Record<string, Tone> = {
  Draft: "neutral",
  Proposed: "warning",
  Confirmed: "info",
  "In Progress": "success",
  "In Progress (Full)": "success",
  "On Hold": "warning",
  Completed: "success",
  Cancelled: "danger",
  Archived: "neutral",
  Planned: "neutral",
  Rescheduled: "warning",
  Held: "success",
  "Partially Held": "warning",
};

/** The batch or class state as the people who run it name it (`state_label`), with a fixed tone. */
export function StateBadge({ label }: { label: string }) {
  return <StatusBadge tone={STATE_TONE[label] ?? "info"}>{label}</StatusBadge>;
}

/** Whether a branch manager or super admin is signed in: the only people who may override an advisory warning or decide a request. */
export function useIsManager(): boolean {
  const { hasRole } = useAuth();
  return hasRole("BRANCH_MANAGER", "SUPER_ADMIN");
}

export const mono = (text: string) => <span className="font-mono text-xs">{text}</span>;

// ---------------------------------------------------------------- action dialog

export type DialogField = {
  name: string;
  label: string;
  /** "multiselect": a tick list of `options`; the value is the chosen option values, comma-separated. */
  /** "days": seven day toggles; the value is the chosen days in week order, comma-separated ("Mon,Wed,Fri"). */
  type?: "text" | "textarea" | "number" | "datetime" | "date" | "time" | "select" | "checkbox" | "days" | "multiselect";
  required?: boolean;
  options?: { value: string | number; label: string }[];
  value?: string;
  hint?: string;
  placeholder?: string;
  min?: number;
  /** Shown only while this returns true for the current values (a kind-dependent field). */
  showIf?: (values: Record<string, string>) => boolean;
  /** Shown only after the server answered with warnings (an override reason for the Branch Manager). */
  afterWarnings?: boolean;
};

/** The server's list of blockers or advisory warnings carried by a 422 (`error.details.blocking` / `.warnings`). */
export type Issues = { blocking: string[]; warnings: string[] };

export function issuesOf(error: unknown): Issues | null {
  if (!(error instanceof ApiError) || !error.details) return null;
  const blocking = error.details["blocking"];
  const warnings = error.details["warnings"];
  const list = (x: unknown) => (Array.isArray(x) ? x.map(String) : []);
  const found = { blocking: list(blocking), warnings: list(warnings) };
  return found.blocking.length || found.warnings.length ? found : null;
}

export function IssueList({ issues }: { issues: Issues }) {
  return (
    <div role="alert" className="space-y-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100">
      {issues.blocking.length > 0 && (
        <div>
          <p className="font-medium">This cannot go ahead yet:</p>
          <ul className="list-disc pl-5">
            {issues.blocking.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </div>
      )}
      {issues.warnings.length > 0 && (
        <div>
          <p className="font-medium">Warnings:</p>
          <ul className="list-disc pl-5">
            {issues.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/**
 * A button that opens a small form. `onSubmit` receives the field values as strings ("true" for a ticked checkbox);
 * the dialog closes when it resolves and stays open (values kept) when it throws.
 */
export function ActionDialog({
  trigger,
  title,
  description,
  fields,
  submitLabel = "Save",
  onSubmit,
  onFieldChange,
  children,
}: {
  trigger: ReactNode;
  title: string;
  description?: ReactNode;
  fields: DialogField[];
  submitLabel?: string;
  onSubmit: (values: Record<string, string>) => Promise<unknown>;
  onFieldChange?: (name: string, value: string) => void;
  children?: ReactNode;
}) {
  const initial = () => Object.fromEntries(fields.map((f) => [f.name, f.value ?? (f.type === "select" ? String(f.options?.[0]?.value ?? "") : "")]));
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>(initial);
  const [busy, setBusy] = useState(false);
  const [issues, setIssues] = useState<Issues | null>(null);
  const shown = (f: DialogField) => (!f.afterWarnings || (issues?.warnings.length ?? 0) > 0) && (!f.showIf || f.showIf(values));
  const set = (name: string, value: string) => {
    setValues((v) => ({ ...v, [name]: value }));
    onFieldChange?.(name, value);
  };
  const missing = fields.some((f) => shown(f) && f.required && f.type !== "checkbox" && !values[f.name]?.trim());

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next) {
          setValues(initial());
          setIssues(null);
        }
        setOpen(next);
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={async (event) => {
            event.preventDefault();
            setBusy(true);
            setIssues(null);
            try {
              const sent = Object.fromEntries(Object.entries(values).filter(([name]) => shown(fields.find((f) => f.name === name)!)));
              await onSubmit(sent);
              setOpen(false);
            } catch (error) {
              /* the mutation already showed the error; keep the dialog open and list what the server found */
              setIssues(issuesOf(error));
            } finally {
              setBusy(false);
            }
          }}
        >
          {children}
          {issues && <IssueList issues={issues} />}
          {fields.filter(shown).map((f) => (
            <Field key={f.name} label={f.label + (f.required ? " *" : "")} hint={f.type === "checkbox" ? undefined : f.hint} htmlFor={`f-${f.name}`}>
              {f.type === "textarea" ? (
                <Textarea id={`f-${f.name}`} rows={3} value={values[f.name] ?? ""} placeholder={f.placeholder} onChange={(e) => set(f.name, e.target.value)} />
              ) : f.type === "select" ? (
                <NativeSelect id={`f-${f.name}`} options={f.options ?? []} value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)} />
              ) : f.type === "multiselect" ? (
                <div id={`f-${f.name}`} role="group" className="max-h-40 space-y-1 overflow-y-auto rounded-md border p-2">
                  {(f.options ?? []).length === 0 && <p className="text-sm text-muted-foreground">Nothing to choose from.</p>}
                  {(f.options ?? []).map((o) => {
                    const chosen = (values[f.name] ?? "").split(",").filter(Boolean);
                    const on = chosen.includes(String(o.value));
                    return (
                      <label key={o.value} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={on}
                          onChange={() => set(f.name, (on ? chosen.filter((c) => c !== String(o.value)) : [...chosen, String(o.value)]).join(","))}
                        />
                        {o.label}
                      </label>
                    );
                  })}
                </div>
              ) : f.type === "days" ? (
                <DayToggles id={`f-${f.name}`} value={values[f.name] ?? ""} onChange={(v) => set(f.name, v)} />
              ) : f.type === "checkbox" ? (
                <label className="flex items-center gap-2 text-sm">
                  <input id={`f-${f.name}`} type="checkbox" checked={values[f.name] === "true"} onChange={(e) => set(f.name, e.target.checked ? "true" : "")} />
                  {f.hint}
                </label>
              ) : (
                <Input
                  id={`f-${f.name}`}
                  type={f.type === "datetime" ? "datetime-local" : (f.type ?? "text")}
                  min={f.min}
                  value={values[f.name] ?? ""}
                  placeholder={f.placeholder}
                  onChange={(e) => set(f.name, e.target.value)}
                />
              )}
            </Field>
          ))}
          <DialogFooter>
            <Button type="submit" disabled={busy || missing}>
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

/** Seven day toggles for a "days" field; the value stays in week order. */
function DayToggles({ id, value, onChange }: { id: string; value: string; onChange: (value: string) => void }) {
  const chosen = new Set(value.split(",").filter(Boolean));
  const toggle = (day: string) => {
    const next = new Set(chosen);
    if (next.has(day)) next.delete(day);
    else next.add(day);
    onChange(WEEKDAYS.filter((d) => next.has(d)).join(","));
  };
  return (
    <div id={id} className="flex flex-wrap gap-2" role="group">
      {WEEKDAYS.map((day) => (
        <label key={day} className="flex items-center gap-1 text-sm">
          <input type="checkbox" checked={chosen.has(day)} onChange={() => toggle(day)} />
          {day}
        </label>
      ))}
    </div>
  );
}
