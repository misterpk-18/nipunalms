/** The submit checklist of a Draft version: what is done, what is left, where to go for it, and the Submit button last. */
import { Check, Circle } from "lucide-react";
import { isTopicItem, type Checklist, type ChecklistStep, type ChecklistStepKey, type ChecklistTopicItem } from "@/api/curriculum";
import { StepBar } from "@/components/lms/step-bar";
import { Section, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Where each step lives on the page (the ids sit on the matching blocks). */
export const STEP_TARGET: Record<ChecklistStepKey, string> = {
  tracks: "cv-tracks",
  modules: "cv-modules",
  topics: "cv-modules",
  hours: "cv-hours",
  rules: "cv-rules",
  assessments: "cv-assessments",
};

const GO_LABEL: Record<ChecklistStepKey, string> = {
  tracks: "Go to tracks",
  modules: "Go to modules",
  topics: "Fix topic details",
  hours: "Go to hours",
  rules: "Go to completion rules",
  assessments: "Go to required assessments",
};

/** The DOM id of a topic row, so the checklist can jump to it. */
export const topicDomId = (topicId: number) => `topic-${topicId}`;

export function scrollToId(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
  el.focus({ preventScroll: true });
}

function StepRow({
  step,
  current,
  onGo,
  onOpenTopic,
}: {
  step: ChecklistStep;
  current: boolean;
  onGo: (key: ChecklistStepKey) => void;
  onOpenTopic: (item: ChecklistTopicItem) => void;
}) {
  return (
    <li className={cn("rounded-lg border p-3", current && "border-primary/50 bg-primary/5")} data-step={step.key} data-done={step.done ? "true" : "false"}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
            {step.done ? <Check className="size-4 text-success" aria-hidden /> : <Circle className="size-4 text-muted-foreground" aria-hidden />}
            {step.label}
            <span className="sr-only">{step.done ? " (done)" : " (not done yet)"}</span>
            {!step.required && <Tag>Recommended</Tag>}
          </p>
          {!step.done && <p className="mt-1 text-sm text-muted-foreground">{step.hint}</p>}
        </div>
        {!step.done && (
          <Button size="sm" variant={current ? "default" : "outline"} onClick={() => onGo(step.key)}>
            {GO_LABEL[step.key]}
          </Button>
        )}
      </div>
      {!step.done && step.items.length > 0 && (
        <ul className="mt-2 space-y-1 text-sm">
          {step.items.map((item, i) =>
            isTopicItem(item) ? (
              <li key={item.topic_id}>
                <button
                  type="button"
                  className="text-left underline decoration-dotted underline-offset-2 hover:decoration-solid"
                  onClick={() => onOpenTopic(item)}
                >
                  {item.module_title} &gt; {item.title}
                </button>
                <span className="text-muted-foreground"> needs {item.missing.join(", ")}</span>
              </li>
            ) : (
              <li key={`${item.title}-${i}`} className="text-muted-foreground">
                {step.key === "modules" ? `${item.title} has no topics yet` : `${item.title} is not pinned yet`}
              </li>
            ),
          )}
        </ul>
      )}
    </li>
  );
}

export function SubmitChecklist({
  checklist,
  canSubmit,
  submitting,
  onGo,
  onOpenTopic,
  onSubmit,
}: {
  checklist: Checklist;
  canSubmit: boolean;
  submitting: boolean;
  onGo: (key: ChecklistStepKey) => void;
  onOpenTopic: (item: ChecklistTopicItem) => void;
  onSubmit: () => void;
}) {
  const { steps, ready, next } = checklist;
  const nextStep = steps.find((s) => s.key === next);
  const todo = steps.filter((s) => s.required && !s.done).map((s) => s.label);
  const bar = [...steps.map((s) => ({ label: s.label, done: s.done })), { label: "Submit", done: false }];
  return (
    <Section title="Before you submit" id="cv-checklist">
      <div className="space-y-3">
        <StepBar
          steps={bar}
          next={
            nextStep && (
              <Button size="sm" onClick={() => onGo(nextStep.key)}>
                Next: {nextStep.label}
              </Button>
            )
          }
        />
        <ol className="space-y-2" aria-label="Submit checklist">
          {steps.map((s) => (
            <StepRow key={s.key} step={s} current={s.key === next} onGo={onGo} onOpenTopic={onOpenTopic} />
          ))}
        </ol>
        <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/40 p-3">
          <Button disabled={!ready || !canSubmit || submitting} onClick={onSubmit} aria-describedby="cv-submit-reason">
            Submit for review
          </Button>
          <p id="cv-submit-reason" className="min-w-0 flex-1 text-sm text-muted-foreground">
            {ready
              ? "Everything required is done. The Founder / CEO or a Super Admin will review it."
              : todo.length
                ? `Not ready yet. Still to do: ${todo.join(", ")}.`
                : "Not ready yet. Fix the items above first."}
          </p>
        </div>
      </div>
    </Section>
  );
}
