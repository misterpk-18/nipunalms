import { Link } from "@tanstack/react-router";
import type { RiskReason } from "@/api/trainer";
import { Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";

/** The reasons a student needs attention, as small labels (the detail is in the tooltip). */
export function ReasonTags({ reasons }: { reasons: RiskReason[] }) {
  if (reasons.length === 0) return <span className="text-sm text-muted-foreground">On track</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {reasons.map((r) => (
        <span key={r.kind} title={r.detail}>
          <Tag tone="warning">{r.label}</Tag>
        </span>
      ))}
    </div>
  );
}

/** Each reason with its figures and a button to the place where the trainer can act on it. */
export function ReasonList({ reasons }: { reasons: RiskReason[] }) {
  return (
    <ul className="divide-y">
      {reasons.map((r) => (
        <li key={r.kind} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
          <div className="min-w-0">
            <p className="text-sm font-medium">{r.label}</p>
            <p className="text-xs text-muted-foreground">{r.detail}</p>
          </div>
          <Button asChild size="sm" variant="outline">
            <Link to={r.to}>{r.action}</Link>
          </Button>
        </li>
      ))}
    </ul>
  );
}

export const pct = (value: number | null | undefined) => (value === null || value === undefined ? "Not calculated yet" : `${Math.round(value)}%`);
