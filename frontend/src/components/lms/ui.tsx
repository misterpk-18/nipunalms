/** Building blocks shared by every LMS screen (visual language from the approved prototype's shared components). */
import { useState, type ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, CircleX, Clock, Info, Loader, Lock, PlugZap, TriangleAlert, type LucideIcon } from "lucide-react";
import { errorMessage } from "@/api/client";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

const TONE_CLASS: Record<Tone, string> = {
  success: "bg-success-soft text-success border-success/30",
  warning: "bg-warning-soft text-warning border-warning/30",
  danger: "bg-danger-soft text-danger border-danger/30",
  info: "bg-info-soft text-info border-info/30",
  neutral: "bg-neutral-soft text-neutral border-neutral/25",
};

const TONE_ICON: Record<Tone, LucideIcon> = {
  success: CircleCheck,
  warning: TriangleAlert,
  danger: CircleX,
  info: Info,
  neutral: CircleAlert,
};

// ---------------------------------------------------------------- layout

export function PageHead({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Section({
  title,
  actions,
  id,
  className,
  children,
}: {
  title?: string;
  actions?: ReactNode;
  id?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className={cn("rounded-xl border bg-card p-4 shadow-sm sm:p-5", className)}>
      {(title || actions) && (
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          {title && <h2 className="text-base font-semibold">{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

const GRID_COLS = { 2: "md:grid-cols-2", 3: "md:grid-cols-2 lg:grid-cols-3", 4: "sm:grid-cols-2 lg:grid-cols-4" } as const;

export function Grid({ cols = 3, children }: { cols?: 2 | 3 | 4; children: ReactNode }) {
  return <div className={cn("grid gap-4", GRID_COLS[cols])}>{children}</div>;
}

/** Small dashed explanatory line under a section. */
export function Note({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed bg-muted px-3 py-2 text-xs text-muted-foreground">
      <Info className="mr-1 inline size-3.5" aria-hidden />
      {children}
    </p>
  );
}

export function KeyValue({ items }: { items: [label: ReactNode, value: ReactNode][] }) {
  return (
    <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
      {items.map(([label, value], i) => (
        <div key={i} className="min-w-0 border-b border-dashed pb-2">
          <dt className="text-xs text-muted-foreground">{label}</dt>
          <dd className="break-words text-sm font-medium">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

// ---------------------------------------------------------------- status

/** The status-state catalogue: every screen reports loading, empty, partial, restricted and failed data the same way. */
const STATES = {
  Loading: { tone: "info", icon: Loader, text: "Loading…" },
  Empty: { tone: "neutral", icon: Info, text: "Nothing here yet." },
  "Partial Data": { tone: "warning", icon: TriangleAlert, text: "Some sources did not respond; figures shown are incomplete." },
  "Pending Verification": { tone: "warning", icon: Clock, text: "Awaiting verification — not treated as confirmed." },
  Stale: { tone: "warning", icon: Clock, text: "Data is older than the freshness window." },
  "Integration Unavailable": { tone: "neutral", icon: PlugZap, text: "This integration is not connected yet." },
  "Permission Restricted": { tone: "neutral", icon: Lock, text: "Your role cannot view this information." },
  Error: { tone: "danger", icon: CircleX, text: "Something went wrong. Try again or raise a support request." },
  Saving: { tone: "info", icon: Loader, text: "Saving…" },
  Saved: { tone: "success", icon: CircleCheck, text: "Saved." },
  "Not Submitted": { tone: "neutral", icon: Info, text: "Not submitted yet." },
  Failed: { tone: "danger", icon: CircleX, text: "Action failed." },
  "Confirmation Pending": { tone: "warning", icon: Clock, text: "Waiting for confirmation." },
} as const satisfies Record<string, { tone: Tone; icon: LucideIcon; text: string }>;

export type StatusState = keyof typeof STATES;

export function StatusNote({ state, children }: { state: StatusState; children?: ReactNode }) {
  const { tone, icon: Icon, text } = STATES[state];
  return (
    <div role="status" className={cn("flex items-start gap-2 rounded-lg border px-3 py-2 text-sm", TONE_CLASS[tone])}>
      <Icon className={cn("mt-0.5 size-4 shrink-0", (state === "Loading" || state === "Saving") && "animate-spin")} aria-hidden />
      <div>
        <strong className="font-semibold">{state}:</strong> {children ?? text}
      </div>
    </div>
  );
}

/** Tone for a status string; the order matters (a "Pending" word beats a generic success word). */
export function toneFor(status: string): Tone {
  const t = status.toLowerCase();
  if (/(?<!not )\breviewed\b/.test(t)) return "success"; // "Reviewed" is done; "Under Review" is still open
  if (/(revoked|failed|error|absent(?!.*recovery)|blocked|overdue|rejected|cancelled|breach)/.test(t)) return "danger";
  if (/(pending|partial|held|stale|review|awaiting|warning|forming|quota|interrupted|not yet|alert|open|due|rescheduled|escalated|expiring)/.test(t))
    return "warning";
  if (/(unavailable|not configured|not released|disabled|restricted|superseded|not submitted|not started|none|expired|withdrawn|inactive|suspended|—)/.test(t))
    return "neutral";
  if (
    /(issued|released|present|delivered|reviewed|saved|active|ready|approved|running|verified|submitted|available|completed|activated|published|resolved|live)/.test(
      t,
    )
  )
    return "success";
  return "info";
}

export function StatusBadge({ children, tone }: { children: ReactNode; tone?: Tone }) {
  const resolved = tone ?? toneFor(String(children));
  const Icon = TONE_ICON[resolved];
  return (
    <span className={cn("inline-flex max-w-full items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium leading-5", TONE_CLASS[resolved])}>
      <Icon className="size-3.5 shrink-0" aria-hidden />
      <span className="break-words">{children}</span>
    </span>
  );
}

// ---------------------------------------------------------------- data

export type Column<T> = { h: string; c: (row: T) => ReactNode };

/** A table on desktop; on phones every row becomes a card with labelled values. */
export function DataTable<T>({
  rows,
  cols,
  caption,
  getKey,
  empty = "Nothing here yet.",
}: {
  rows: T[];
  cols: Column<T>[];
  caption: string;
  getKey: (row: T, index: number) => string | number;
  empty?: string;
}) {
  if (rows.length === 0) return <StatusNote state="Empty">{empty}</StatusNote>;
  return (
    <div>
      <div className="hidden overflow-x-auto rounded-xl border bg-card md:block">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              {cols.map((col) => (
                <th key={col.h} scope="col" className="px-3 py-2.5 font-semibold">
                  {col.h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={getKey(row, i)} className="border-t align-top">
                {cols.map((col) => (
                  <td key={col.h} className="px-3 py-2.5">
                    {col.c(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="space-y-3 md:hidden" aria-label={caption}>
        {rows.map((row, i) => (
          <li key={getKey(row, i)} className="rounded-xl border bg-card p-3 shadow-sm">
            <dl className="space-y-1.5">
              {cols.map((col) => (
                <div key={col.h} className="flex flex-wrap gap-x-2 text-sm">
                  <dt className="min-w-24 text-xs text-muted-foreground">{col.h}</dt>
                  <dd className="min-w-0 flex-1 break-words">{col.c(row)}</dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function PillTabs<T extends string>({ tabs, value, onChange, label }: { tabs: readonly T[]; value: T; onChange: (tab: T) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="mb-4 flex flex-wrap gap-2">
      {tabs.map((tab) => (
        <button
          key={tab}
          role="tab"
          aria-selected={value === tab}
          onClick={() => onChange(tab)}
          className={cn(
            "tap rounded-full border px-4 py-1.5 text-sm font-medium",
            value === tab ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-accent",
          )}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}

/**
 * Renders a TanStack Query result: Loading while it loads, Error (with the API message and a retry link) when it
 * fails, Empty when `isEmpty` says so, and `children(data)` otherwise.
 */
export function QueryView<T>({
  query,
  isEmpty,
  empty,
  children,
}: {
  query: UseQueryResult<T>;
  isEmpty?: (data: T) => boolean;
  empty?: string;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) return <StatusNote state="Loading" />;
  if (query.isError)
    return (
      <StatusNote state="Error">
        {errorMessage(query.error)}{" "}
        <button className="underline" onClick={() => void query.refetch()}>
          Try again
        </button>
      </StatusNote>
    );
  if (isEmpty?.(query.data)) return <StatusNote state="Empty">{empty}</StatusNote>;
  return <>{children(query.data)}</>;
}

// ---------------------------------------------------------------- actions

/** Wraps a trigger element (usually a Button) in a confirmation dialog; `onConfirm` runs only after the user agrees. */
export function ConfirmAction({
  children,
  title,
  description,
  confirmLabel = "Confirm",
  destructive,
  onConfirm,
}: {
  children: ReactNode;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  destructive?: boolean;
  onConfirm: () => void | Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>{children}</AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={busy}
            className={cn(destructive && "bg-destructive text-destructive-foreground hover:bg-destructive/90")}
            onClick={async () => {
              setBusy(true);
              try {
                await onConfirm();
              } finally {
                setBusy(false);
              }
            }}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
