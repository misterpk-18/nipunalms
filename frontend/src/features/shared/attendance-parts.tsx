/** Pieces shared by the attendance, progress, completion and certificate screens of every workspace (slice S4). */
import { useState, type ReactNode } from "react";
import type { Measures } from "@/api/attendance";
import { fmtDateTime, percent } from "@/features/shared/format";
import { NativeSelect, Field } from "@/components/lms/forms";
import { Grid, Note, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

/** The attendance cell of a table: the percentage, or the reason there is none ("Partial Data", "Not started"). */
export function AttendanceCell({ measures }: { measures: Measures["attendance"] }) {
  if (measures.state === "Not started") return <StatusBadge tone="neutral">Not started</StatusBadge>;
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      {measures.state === "Partial Data" ? <StatusBadge tone="warning">Partial Data</StatusBadge> : <strong>{percent(measures.percent)}</strong>}
      {measures.alert && <StatusBadge tone="danger">Alert &lt; {measures.alert_threshold}%</StatusBadge>}
    </span>
  );
}

export function Meter({ value, label }: { value: number | null; label: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-3xl font-semibold tabular-nums">{value === null ? "—" : `${Math.round(value)}%`}</span>
        <span className="text-right text-xs text-muted-foreground">{label}</span>
      </div>
      <div
        className="mt-2 h-2 overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={`${label}: ${value === null ? "not yet calculable" : `${Math.round(value)} percent`}`}
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${value ?? 0}%` }} />
      </div>
    </div>
  );
}

/** The four progress measures, each in its own card and never merged into one score. */
export function MeasureCards({ measures }: { measures: Measures }) {
  const { delivery, attendance, required_learning: learning, engagement } = measures;
  return (
    <Grid cols={2}>
      <Section title="1 · Curriculum delivered">
        <Meter value={delivery.percent} label={`${delivery.delivered_sessions} of ${delivery.planned_sessions} planned sessions delivered`} />
        <p className="mt-2 text-xs text-muted-foreground">What has been taught to your batch.</p>
      </Section>
      <Section title="2 · Attendance / approved recovery">
        {attendance.state === "Not started" ? (
          <StatusNote state="Empty">Attendance starts counting from your first regular class.</StatusNote>
        ) : (
          <>
            <Meter value={attendance.percent} label={`${attendance.present + attendance.late} attended of ${attendance.marked} marked classes`} />
            <p className="mt-2 text-xs text-muted-foreground">
              Present {attendance.present} · Late {attendance.late} · Absent {attendance.absent} · Excused {attendance.excused}
              {attendance.recovered > 0 && ` · ${attendance.recovered} approved recovery reported separately`}
            </p>
            {attendance.state === "Partial Data" && (
              <div className="mt-2">
                <StatusNote state="Partial Data">{attendance.unmarked} delivered class(es) are not marked yet, so this figure is provisional.</StatusNote>
              </div>
            )}
            {attendance.alert && (
              <div className="mt-2">
                <StatusNote state="Error">Attendance is below {attendance.alert_threshold}%. Ask your coordinator about recovery options.</StatusNote>
              </div>
            )}
          </>
        )}
      </Section>
      <Section title="3 · Required learning completed">
        <Meter
          value={learning.percent}
          label={`${learning.covered_topics} of ${learning.required_topics} required topics covered by attended or recovered classes`}
        />
      </Section>
      <Section title="4 · LMS engagement">
        <div className="flex items-center gap-2">
          <StatusBadge
            tone={engagement.level === "High" ? "success" : engagement.level === "Medium" ? "info" : engagement.level === "Low" ? "warning" : "neutral"}
          >
            {engagement.level}
          </StatusBadge>
          <span className="text-sm text-muted-foreground">
            {engagement.events_in_window} activity event(s) in the last {engagement.window_days} days
          </span>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">Last activity: {fmtDateTime(engagement.last_activity_at)}. Engagement is informational only.</p>
      </Section>
    </Grid>
  );
}

export function CompletionNote() {
  return <Note>Course completion and certificate eligibility are decided through Completion Review, not from any single percentage.</Note>;
}

export type FieldDef = {
  name: string;
  label: string;
  kind: "textarea" | "text" | "select" | "date";
  required?: boolean;
  options?: readonly string[];
  initial?: string;
  hint?: string;
};

/** A button that opens a small form (reason, choice, date ...) and runs `onSubmit` with the values; the dialog closes on success. */
export function FormDialog({
  trigger,
  title,
  description,
  submitLabel,
  fields,
  onSubmit,
  destructive,
}: {
  trigger: ReactNode;
  title: string;
  description?: ReactNode;
  submitLabel: string;
  fields: FieldDef[];
  onSubmit: (values: Record<string, string>) => Promise<unknown>;
  destructive?: boolean;
}) {
  const initial = () => Object.fromEntries(fields.map((f) => [f.name, f.initial ?? (f.kind === "select" ? (f.options?.[0] ?? "") : "")]));
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>(initial);
  const [busy, setBusy] = useState(false);
  const missing = fields.some((f) => f.required && !values[f.name]?.trim());

  const submit = async () => {
    setBusy(true);
    try {
      await onSubmit(values);
      setOpen(false);
      setValues(initial());
    } catch {
      /* the mutation already showed the server's message */
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <div className="space-y-3">
          {fields.map((f) => (
            <Field key={f.name} label={f.label} htmlFor={`fd-${f.name}`} hint={f.hint}>
              {f.kind === "textarea" && (
                <Textarea id={`fd-${f.name}`} rows={3} value={values[f.name]} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
              )}
              {f.kind === "text" && <Input id={`fd-${f.name}`} value={values[f.name]} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />}
              {f.kind === "date" && (
                <Input id={`fd-${f.name}`} type="date" value={values[f.name]} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
              )}
              {f.kind === "select" && (
                <NativeSelect
                  id={`fd-${f.name}`}
                  value={values[f.name]}
                  onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
                  options={(f.options ?? []).map((o) => ({ value: o, label: o }))}
                />
              )}
            </Field>
          ))}
        </div>
        <DialogFooter>
          <Button variant={destructive ? "destructive" : "default"} disabled={busy || missing} onClick={() => void submit()}>
            {submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
