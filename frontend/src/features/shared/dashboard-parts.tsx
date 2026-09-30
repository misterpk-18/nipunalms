/** Pieces the dashboard screens share: the ranked tile and the honest empty / unavailable line of a card. */
import type { ReactNode } from "react";
import { StatusNote } from "@/components/lms/ui";
import { cn } from "@/lib/utils";

/** A ranked summary tile (rank 1 is what to look at first). */
export function Tile({
  rank,
  label,
  value,
  hint,
  children,
  className,
}: {
  rank: number;
  label: string;
  value?: ReactNode;
  hint?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl border bg-card p-4 shadow-sm", className)}>
      <div className="flex items-center gap-2 text-xs font-medium uppercase text-muted-foreground">
        <span className="grid size-5 place-items-center rounded-full bg-navy text-[11px] text-navy-foreground" aria-hidden>
          {rank}
        </span>
        <span>{label}</span>
      </div>
      {value !== undefined && <div className="mt-2 text-xl font-semibold leading-snug">{value}</div>}
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
      {children}
    </div>
  );
}

/** A card whose source is Empty or Unavailable: say so, in words (never a blank or a zero). */
export function CardGap({ card }: { card: { state: string; message?: string | null } }) {
  if (card.state === "Unavailable") return <StatusNote state="Error">{card.message ?? "This information could not be loaded right now."}</StatusNote>;
  return <p className="text-sm text-muted-foreground">{card.message ?? "Nothing here yet."}</p>;
}
