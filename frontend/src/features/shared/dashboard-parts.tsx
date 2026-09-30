/** Pieces the dashboard screens share: ranked tiles, the CRM "Unavailable" tile, quick links and the honest empty / unavailable line of a card. */
import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import type { NotConfigured } from "@/api/dashboards";
import { Section, StatusNote } from "@/components/lms/ui";
import { fmtDateTime } from "@/features/shared/format";
import { cn } from "@/lib/utils";

/** A headline figure. `rank` marks the approved priority order (Module 25; rank 1 is what to look at first); tiles without one are secondary widgets. */
export function Tile({
  label,
  value,
  hint,
  rank,
  to,
  children,
  className,
}: {
  label: string;
  value?: ReactNode;
  hint?: ReactNode;
  rank?: number;
  to?: string;
  children?: ReactNode;
  className?: string;
}) {
  const body = (
    <>
      <div className="flex items-center gap-2 text-xs font-medium uppercase text-muted-foreground">
        {rank !== undefined && (
          <span className="grid size-5 shrink-0 place-items-center rounded-full bg-navy text-[11px] text-navy-foreground" aria-label={`Priority ${rank}`}>
            {rank}
          </span>
        )}
        <span>{label}</span>
      </div>
      {value !== undefined && <div className="mt-2 text-xl font-semibold leading-snug">{value}</div>}
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
      {children}
    </>
  );
  const classes = cn("block rounded-xl border bg-card p-4 shadow-sm", to && "hover:bg-accent", className);
  return to ? (
    <Link to={to} className={classes}>
      {body}
    </Link>
  ) : (
    <div className={classes} role="group" aria-label={label}>
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

/** A card whose source is Empty or Unavailable: say so, in words (never a blank or a zero). */
export function CardGap({ card }: { card: { state: string; message?: string | null } }) {
  if (card.state === "Unavailable") return <StatusNote state="Error">{card.message ?? "This information could not be loaded right now."}</StatusNote>;
  return <p className="text-sm text-muted-foreground">{card.message ?? "Nothing here yet."}</p>;
}
