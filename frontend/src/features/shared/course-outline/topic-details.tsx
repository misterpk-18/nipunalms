/** Outline, class, minutes, weight, evidence and prerequisites of one topic. Opens from the topic row. */
import { useState } from "react";
import { coursesApi } from "@/api/courses";
import type { ModuleContent, TopicRow } from "@/api/delivery";
import { Field, NativeSelect } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { serverMessage, topicChoices, useCourseMutation } from "./mutation";
import { TopicMultiPicker } from "./pickers";

function TopicForm({ topic, modules, onDone }: { topic: TopicRow; modules: ModuleContent[]; onDone: () => void }) {
  const [form, setForm] = useState({
    topic_class: topic.topic_class as string,
    outcome: topic.outcome ?? "",
    instructional_minutes: topic.instructional_minutes?.toString() ?? "",
    independent_minutes: topic.independent_minutes?.toString() ?? "",
    weight: topic.weight?.toString() ?? "",
    evidence: topic.evidence ?? "",
    activities: topic.activities ?? "",
  });
  const [depends, setDepends] = useState<number[]>(topic.depends_on);
  const [error, setError] = useState<string | null>(null);
  const save = useCourseMutation((body: Record<string, unknown>) => coursesApi.updateTopic(topic.topic_id, body), `Saved ${topic.title}`, {
    silentValidation: true,
  });
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const number = (value: string) => (value.trim() ? Number(value) : null);
  const choices = topicChoices(modules).filter((c) => c.topic_id !== topic.topic_id);
  return (
    <form
      className="space-y-3"
      onSubmit={async (event) => {
        event.preventDefault();
        setError(null);
        try {
          await save.mutateAsync({
            topic_class: form.topic_class,
            outcome: form.outcome.trim() || null,
            instructional_minutes: number(form.instructional_minutes),
            independent_minutes: number(form.independent_minutes),
            weight: number(form.weight),
            evidence: form.evidence.trim() || null,
            activities: form.activities.trim() || null,
            depends_on: depends,
          });
          onDone();
        } catch (e) {
          setError(serverMessage(e));
        }
      }}
    >
      {error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      <Field label="Class" htmlFor="td-class" hint="Only Required topics count towards a student's required learning.">
        <NativeSelect
          id="td-class"
          value={form.topic_class}
          options={["Required", "Recommended", "Optional"].map((c) => ({ value: c, label: c }))}
          onChange={(e) => set("topic_class")(e.target.value)}
        />
      </Field>
      <Field label="Learning outcome" htmlFor="td-outcome" hint="What a student can do after this topic.">
        <Textarea id="td-outcome" rows={3} value={form.outcome} onChange={(e) => set("outcome")(e.target.value)} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Estimated minutes taught" htmlFor="td-instr">
          <Input id="td-instr" type="number" min={0} value={form.instructional_minutes} onChange={(e) => set("instructional_minutes")(e.target.value)} />
        </Field>
        <Field label="Estimated self-study minutes" htmlFor="td-indep">
          <Input id="td-indep" type="number" min={0} value={form.independent_minutes} onChange={(e) => set("independent_minutes")(e.target.value)} />
        </Field>
      </div>
      <Field label="Progress weight" htmlFor="td-weight" hint="How much of the course this topic is worth when progress is counted.">
        <Input id="td-weight" type="number" min={0} step="any" value={form.weight} onChange={(e) => set("weight")(e.target.value)} />
      </Field>
      <Field label="Evidence of completion" htmlFor="td-evidence" hint="What shows the topic was learned (a task, a quiz, a demo).">
        <Textarea id="td-evidence" rows={2} value={form.evidence} onChange={(e) => set("evidence")(e.target.value)} />
      </Field>
      <Field label="Activities" htmlFor="td-activities">
        <Textarea id="td-activities" rows={2} value={form.activities} onChange={(e) => set("activities")(e.target.value)} />
      </Field>
      <Field label="Topics to learn first (optional)" hint="Only where a student really needs one topic before this one.">
        <TopicMultiPicker label="Topics to learn first" choices={choices} value={depends} onChange={setDepends} />
      </Field>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={save.isPending}>
          Save topic
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Outcome, class, minutes, weight, evidence and prerequisites of one topic. */
export function TopicDetails({
  topic,
  modules,
  editable,
  open,
  onOpenChange,
}: {
  topic: TopicRow;
  modules: ModuleContent[];
  editable: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [own, setOwn] = useState(false);
  const isOpen = open ?? own;
  const setOpen = (next: boolean) => {
    setOwn(next);
    onOpenChange?.(next);
  };
  if (!editable) return null;
  return (
    <Dialog open={isOpen} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="ghost" aria-label={`Details of topic ${topic.title}`}>
          Details
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Topic: {topic.title}</DialogTitle>
          <DialogDescription>
            A Required topic needs an outcome, estimated minutes, a progress weight and evidence for the hours and progress to be counted.
          </DialogDescription>
        </DialogHeader>
        <TopicForm topic={topic} modules={modules} onDone={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  );
}

export function topicSummary(t: TopicRow) {
  const parts = [t.outcome, t.instructional_minutes !== null ? `${t.instructional_minutes} min taught` : null, t.weight ? `weight ${t.weight}` : null];
  return parts.filter(Boolean).join(" · ");
}
