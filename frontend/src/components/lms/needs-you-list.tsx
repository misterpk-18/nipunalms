import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { CircleCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/lms/empty-state";

export type NeedsYouItem = {
  id: string | number;
  /** What needs doing, in plain words ("3 students are waiting for a batch"). */
  what: ReactNode;
  /** Where it is, if that helps ("Java batch, Guntur"). */
  where?: ReactNode;
  /** How long it has waited ("2 days"). */
  age?: ReactNode;
  /** Where the button goes. */
  to: string;
  /** Search parameters of that screen (`{ session: 12 }`). */
  search?: Record<string, unknown>;
  /** The button's label ("Allocate"). */
  action: string;
};

/** A home screen's first block: what needs this person now, one row and one button each. */
export function NeedsYouList({
  title = "Needs you",
  items,
  empty = "Nothing needs you right now.",
}: {
  title?: string;
  items: NeedsYouItem[];
  empty?: ReactNode;
}) {
  return (
    <section aria-label={title} className="rounded-xl border bg-card p-4 shadow-sm sm:p-5">
      <h2 className="mb-3 text-base font-semibold">{title}</h2>
      {items.length === 0 ? (
        <EmptyState icon={CircleCheck} reason={empty} />
      ) : (
        <ul className="divide-y">
          {items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
              <div className="min-w-0">
                <p className="text-sm font-medium">{item.what}</p>
                {(item.where || item.age) && (
                  <p className="text-xs text-muted-foreground">
                    {item.where}
                    {item.where && item.age ? " · " : ""}
                    {item.age}
                  </p>
                )}
              </div>
              <Button asChild size="sm">
                <Link to={item.to} {...(item.search ? { search: item.search as never } : {})}>
                  {item.action}
                </Link>
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
