/** Building blocks for the staff dashboards: ranked tiles, the CRM "Unavailable" tile, and the quick links. */
import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import type { NotConfigured } from "@/api/dashboards";
import { Section } from "@/components/lms/ui";
import { fmtDateTime } from "@/features/shared/format";
import { cn } from "@/lib/utils";

/** A headline figure. `rank` marks the approved priority order (Module 25); tiles without one are secondary widgets. */
export function Tile({ label, value, hint, rank, to }: { label: string; value: ReactNode; hint?: ReactNode; rank?: number; to?: string }) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        {rank !== undefined && (
          <span
            className="grid size-5 shrink-0 place-items-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary"
            aria-label={`Priority ${rank}`}
          >
            {rank}
          </span>
        )}
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </>
  );
  const className = cn("block rounded-xl border bg-card p-4 shadow-sm", to && "hover:bg-accent");
  return to ? (
    <Link to={to} className={className}>
      {body}
    </Link>
  ) : (
    <div className={className} role="group" aria-label={label}>
      {body}
    </div>
  );
}

/** A CRM-authoritative figure: "Unavailable" with the Not Configured hint, never 0. */
export function CrmTile({ label, figure, rank }: { label: string; figure: NotConfigured; rank?: number }) {
  return (
    <Tile
      label={label}
      rank={rank}
      value="Unavailable"
      hint={
        <>
          {figure.state} — {figure.reason}
          {figure.refreshed_at && <> · CRM finance data last refreshed {fmtDateTime(figure.refreshed_at)}</>}
        </>
      }
    />
  );
}

export function TileRow({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div className="grid gap-3 sm:grid-cols-3" aria-label={label}>
      {children}
    </div>
  );
}

export function QuickLinks({ title, links }: { title: string; links: readonly (readonly [to: string, label: string])[] }) {
  return (
    <Section title={title}>
      <div className="flex flex-wrap gap-2 text-sm">
        {links.map(([to, label]) => (
          <Link key={to} to={to} className="tap inline-flex items-center rounded-lg border px-3 hover:bg-accent">
            {label}
          </Link>
        ))}
      </div>
    </Section>
  );
}
