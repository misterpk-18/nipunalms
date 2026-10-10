/** Building blocks shared by every LMS screen (visual language from the approved prototype's shared components). */
import { useEffect, type ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, CircleX, Info, TriangleAlert, type LucideIcon } from "lucide-react";
import { errorMessage } from "@/api/client";
import { EmptyState } from "@/components/lms/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { statusInfo, type StatusDomain, type StatusTone } from "@/lib/status";
import { cn } from "@/lib/utils";

export type Tone = StatusTone;

export const TONE_CLASS: Record<Tone, string> = {
  success: "bg-success-soft text-success border-success/30",
  warning: "bg-warning-soft text-warning border-warning/30",
  danger: "bg-danger-soft text-danger border-danger/30",
  info: "bg-info-soft text-info border-info/30",
  neutral: "bg-neutral-soft text-neutral border-neutral/25",
};

export const TONE_ICON: Record<Tone, LucideIcon> = {
  success: CircleCheck,
  warning: TriangleAlert,
  danger: CircleX,
  info: Info,
  neutral: CircleAlert,
};

// ---------------------------------------------------------------- layout

/** The page title and one line saying what you can do here. It also names the browser tab. */
export function PageHead({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  useEffect(() => {
    document.title = `${title} · Nipuna LMS`;
  }, [title]);
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

/** A message about the state of a page or a form: information, success, a warning or a failure. */
export function StatusNote({ tone, title, children }: { tone: Exclude<Tone, "neutral">; title?: string; children: ReactNode }) {
  const Icon = TONE_ICON[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex items-start gap-2 rounded-lg border px-3 py-2 text-sm", TONE_CLASS[tone])}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div>
        {title && <strong className="font-semibold">{title} </strong>}
        {children}
      </div>
    </div>
  );
}

const BADGE_CLASS = "inline-flex max-w-full items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium leading-5";

/**
 * A status from the dictionary (lib/status.ts): fixed colour, plain label, and the "what it means" line as a tooltip.
 * `label` replaces the text when the API sends a more specific one (for example an attendance entry with its recovery).
 */
export function StatusBadge({ domain, code, label }: { domain: StatusDomain; code: string | number | null | undefined; label?: ReactNode }) {
  const info = statusInfo(domain, code);
  const Icon = TONE_ICON[info.tone];
  return (
    <span className={cn(BADGE_CLASS, TONE_CLASS[info.tone])} title={info.help || undefined}>
      <Icon className="size-3.5 shrink-0" aria-hidden />
      <span className="break-words">{label ?? info.label}</span>
    </span>
  );
}

/** A small label that is not a status: a kind, a role, a count. The tone is chosen by the caller, never guessed from the text. */
export function Tag({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  const Icon = TONE_ICON[tone];
  return (
    <span className={cn(BADGE_CLASS, TONE_CLASS[tone])}>
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
  emptyAction,
}: {
  rows: T[];
  cols: Column<T>[];
  caption: string;
  getKey: (row: T, index: number) => string | number;
  empty?: ReactNode;
  emptyAction?: ReactNode;
}) {
  if (rows.length === 0) return <EmptyState reason={empty} action={emptyAction} />;
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
 * Renders a TanStack Query result: a skeleton while it loads, an error (with the API message and a retry link) when it
 * fails, an empty state with the reason (and an optional next action) when `isEmpty` says so, and `children(data)` otherwise.
 */
export function QueryView<T>({
  query,
  isEmpty,
  empty,
  emptyAction,
  skeleton = "table",
  children,
}: {
  query: UseQueryResult<T>;
  isEmpty?: (data: T) => boolean;
  empty?: ReactNode;
  emptyAction?: ReactNode;
  skeleton?: "table" | "cards" | "detail";
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) return <LoadingSkeleton kind={skeleton} />;
  if (query.isError)
    return (
      <StatusNote tone="danger" title="Could not load this.">
        {errorMessage(query.error)}{" "}
        <button className="underline" onClick={() => void query.refetch()}>
          Try again
        </button>
      </StatusNote>
    );
  if (isEmpty?.(query.data)) return <EmptyState reason={empty ?? "Nothing here yet."} action={emptyAction} />;
  return <>{children(query.data)}</>;
}

/** What shows while data loads: the rough shape of the page instead of a line of text. */
export function LoadingSkeleton({ kind = "table" }: { kind?: "table" | "cards" | "detail" }) {
  if (kind === "cards")
    return (
      <div role="status" aria-label="Loading" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-28 rounded-xl" />
        ))}
      </div>
    );
  if (kind === "detail")
    return (
      <div role="status" aria-label="Loading" className="space-y-3">
        <Skeleton className="h-7 w-1/3" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-40 rounded-xl" />
      </div>
    );
  return (
    <div role="status" aria-label="Loading" className="space-y-2">
      <Skeleton className="h-9 rounded-lg" />
      {[0, 1, 2, 3].map((i) => (
        <Skeleton key={i} className="h-12 rounded-lg" />
      ))}
    </div>
  );
}
