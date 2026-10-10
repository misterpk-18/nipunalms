import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { Check, Circle, X } from "lucide-react";
import { useGettingStarted } from "@/api/nav";
import type { Workspace } from "@/api/types";
import { useActing } from "@/auth/acting";
import { useAuth } from "@/auth/auth";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const storageKey = (userId: number, workspace: Workspace) => `nipunalms.gettingStarted.${userId}.${workspace}`;

function wasDismissed(userId: number, workspace: Workspace) {
  try {
    return window.localStorage.getItem(storageKey(userId, workspace)) === "1";
  } catch {
    return false;
  }
}

/**
 * The "Getting started" card at the top of a role's home: a short checklist that ticks itself as the steps are done, with the
 * next undone step as a button. It disappears once every step is done; dismissing it earlier is remembered in this browser.
 */
export type GettingStartedLabels = { title: string; dismiss: string; go: string; steps?: Record<string, string> };
const ENGLISH: GettingStartedLabels = { title: "Getting started", dismiss: "Dismiss", go: "Go" };

export function GettingStartedCard({ workspace, labels = ENGLISH }: { workspace: Workspace; labels?: GettingStartedLabels }) {
  const { title, dismiss, go } = labels;
  const { profile } = useAuth();
  const userId = profile?.user.user_id ?? 0;
  const { branchId } = useActing(workspace);
  const [hidden, setHidden] = useState(() => wasDismissed(userId, workspace));
  const query = useGettingStarted(workspace, branchId);
  const card = query.data;
  // Nothing left to get started with: the card goes away on its own
  if (hidden || !card || card.steps.length === 0 || card.complete) return null;

  const next = card.steps.find((s) => !s.done);
  const close = () => {
    try {
      window.localStorage.setItem(storageKey(userId, workspace), "1");
    } catch {
      // storage blocked: the card then returns on the next visit
    }
    setHidden(true);
  };

  return (
    <section aria-label={title} className="rounded-xl border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">{title}</h2>
          <p className="text-xs text-muted-foreground">
            {card.steps.filter((s) => s.done).length} / {card.steps.length}
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={close} aria-label={dismiss}>
          <X className="size-4" aria-hidden />
          <span className="hidden sm:inline">{dismiss}</span>
        </Button>
      </div>
      <ol className="mt-3 space-y-1.5">
        {card.steps.map((step) => (
          <li key={step.key} className="flex items-center gap-2.5 text-sm">
            {step.done ? (
              <Check className="size-4 shrink-0 text-success" aria-label="Done" />
            ) : (
              <Circle className="size-4 shrink-0 text-muted-foreground" aria-label="To do" />
            )}
            <span className={cn(step.done && "text-muted-foreground line-through")}>{labels.steps?.[step.key] ?? step.label}</span>
            {step === next && (
              <Button asChild size="sm" variant="outline" className="ml-auto">
                <Link to={step.to}>{go}</Link>
              </Button>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
