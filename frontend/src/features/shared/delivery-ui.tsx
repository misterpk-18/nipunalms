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

export const mono = (text: string) => <span className="font-mono text-xs">{text}</span>;

// ---------------------------------------------------------------- action dialog

export type DialogField = {
  name: string;
  label: string;
  type?: "text" | "textarea" | "number" | "datetime" | "date" | "select" | "checkbox";
  required?: boolean;
  options?: { value: string | number; label: string }[];
  value?: string;
  hint?: string;
  placeholder?: string;
  min?: number;
};

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
  const set = (name: string, value: string) => {
    setValues((v) => ({ ...v, [name]: value }));
    onFieldChange?.(name, value);
  };
  const missing = fields.some((f) => f.required && f.type !== "checkbox" && !values[f.name]?.trim());

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next) setValues(initial());
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
            try {
              await onSubmit(values);
              setOpen(false);
            } catch {
              /* the mutation already showed the error; keep the dialog open */
            } finally {
              setBusy(false);
            }
          }}
        >
          {children}
          {fields.map((f) => (
            <Field key={f.name} label={f.label + (f.required ? " *" : "")} hint={f.type === "checkbox" ? undefined : f.hint} htmlFor={`f-${f.name}`}>
              {f.type === "textarea" ? (
                <Textarea id={`f-${f.name}`} rows={3} value={values[f.name] ?? ""} placeholder={f.placeholder} onChange={(e) => set(f.name, e.target.value)} />
              ) : f.type === "select" ? (
                <NativeSelect id={`f-${f.name}`} options={f.options ?? []} value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)} />
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
