import type { ReactNode } from "react";
import { Inbox, type LucideIcon } from "lucide-react";

/** Nothing to show: says why, and offers the next action where there is one. */
export function EmptyState({ reason, action, icon: Icon = Inbox }: { reason: ReactNode; action?: ReactNode; icon?: LucideIcon }) {
  return (
    <div role="status" className="flex flex-col items-center gap-3 rounded-xl border border-dashed bg-card px-4 py-8 text-center">
      <Icon className="size-6 text-muted-foreground" aria-hidden />
      <p className="max-w-prose text-sm text-muted-foreground">{reason}</p>
      {action && <div className="flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}
