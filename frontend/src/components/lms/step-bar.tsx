import type { ReactNode } from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export type Step = { label: string; done: boolean };

/**
 * A setup in order (a batch: Created → Trainer → Ready → Confirmed → Students → Classes): finished steps are ticked, the
 * first unfinished one is the current step, and `next` is the one action that moves it on.
 */
export function StepBar({ steps, next }: { steps: Step[]; next?: ReactNode }) {
  const current = steps.findIndex((step) => !step.done);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-3">
      <ol className="flex flex-wrap items-center gap-x-1 gap-y-2" aria-label="Steps">
        {steps.map((step, i) => (
          <li key={step.label} aria-current={i === current ? "step" : undefined} className="flex items-center gap-1 text-sm">
            <span
              className={cn(
                "grid size-6 place-items-center rounded-full border text-xs font-semibold",
                step.done && "border-success bg-success-soft text-success",
                i === current && "border-primary bg-primary text-primary-foreground",
                !step.done && i !== current && "text-muted-foreground",
              )}
            >
              {step.done ? <Check className="size-3.5" aria-hidden /> : i + 1}
            </span>
            <span className={cn(i === current ? "font-semibold" : step.done ? "text-foreground" : "text-muted-foreground")}>{step.label}</span>
            {i < steps.length - 1 && <span className="mx-1 text-muted-foreground" aria-hidden>→</span>}
          </li>
        ))}
      </ol>
      {next && <div>{next}</div>}
    </div>
  );
}
