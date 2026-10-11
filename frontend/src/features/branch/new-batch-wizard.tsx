/** A new batch in three short steps: Course, then Mode, dates and timetable, then Trainer. Opens the batch page when done. */
import { useState, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi } from "@/api/delivery";
import { useAuth } from "@/auth/auth";
import { useActing } from "@/auth/acting";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field, NativeSelect } from "@/components/lms/forms";
import { DayToggles } from "@/features/shared/delivery-ui";
import { timetableBody } from "@/features/academic/timetable";
import { useApiMutation } from "@/lib/mutation";
import { cn } from "@/lib/utils";

const STEPS = ["Course", "Mode, dates and timetable", "Trainer"] as const;
const MODES = ["Classroom", "Live Online", "Hybrid"].map((m) => ({ value: m, label: m }));

type Values = {
  course_id: string;
  branch_id: string;
  capacity: string;
  mode: string;
  planned_start: string;
  planned_end: string;
  schedule_days: string;
  start_time: string;
  end_time: string;
  location: string;
  trainer: string;
};

const EMPTY: Values = {
  course_id: "",
  branch_id: "",
  capacity: "25",
  mode: "Classroom",
  planned_start: "",
  planned_end: "",
  schedule_days: "",
  start_time: "",
  end_time: "",
  location: "",
  trainer: "",
};

/** What is wrong with a step's answers, in plain words (empty when it can go on). */
export function stepProblems(step: number, v: Values): string[] {
  const problems: string[] = [];
  if (step === 0) {
    if (!v.course_id) problems.push("Choose the course.");
    if (!v.branch_id) problems.push("Choose the branch.");
    if (!(Number(v.capacity) >= 1)) problems.push("Seats must be at least 1.");
  }
  if (step === 1) {
    if (v.planned_start && v.planned_end && v.planned_end < v.planned_start) problems.push("The end date is before the start date.");
    if ((v.start_time && !v.end_time) || (!v.start_time && v.end_time)) problems.push("Give both the start and the end time, or neither.");
    if (v.start_time && v.end_time && v.end_time <= v.start_time) problems.push("The class must end after it starts.");
  }
  return problems;
}

export function NewBatchWizard({
  trigger,
  defaultCourseId,
  open: controlledOpen,
  onOpenChange,
}: {
  trigger?: ReactNode;
  defaultCourseId?: number;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const { profile } = useAuth();
  const { branchId } = useActing("branch");
  const navigate = useNavigate();
  const branches = profile?.allowed_branches ?? [];
  const initial = (): Values => ({
    ...EMPTY,
    course_id: defaultCourseId ? String(defaultCourseId) : "",
    branch_id: String(branchId ?? (branches.length === 1 ? branches[0]!.branch_id : "")),
  });
  const [ownOpen, setOwnOpen] = useState(false);
  const open = controlledOpen ?? ownOpen;
  const [step, setStepNow] = useState(0);
  const [tried, setTried] = useState(false);
  const setStep = (n: number) => {
    setStepNow(n);
    setTried(false);
  };
  const [v, setV] = useState<Values>(initial);
  const set = (patch: Partial<Values>) => setV((prev) => ({ ...prev, ...patch }));
  const courses = useQuery({ queryKey: ["delivery", "courses"], queryFn: deliveryApi.courses });
  const trainers = useQuery({
    queryKey: ["delivery", "trainers", Number(v.branch_id)],
    queryFn: () => deliveryApi.staff("TRAINER", Number(v.branch_id)),
    enabled: step === 2 && Number(v.branch_id) > 0,
  });

  const create = useApiMutation(
    async () => {
      const batch = await deliveryApi.createBatch({
        course_id: Number(v.course_id),
        branch_id: Number(v.branch_id),
        capacity: Number(v.capacity),
        mode: v.mode,
        planned_start: v.planned_start || undefined,
        planned_end: v.planned_end || undefined,
        ...timetableBody({
          schedule_days: v.schedule_days,
          start_time: v.start_time,
          end_time: v.end_time,
          location: v.mode === "Live Online" ? "" : v.location,
        }),
      });
      if (v.trainer) await deliveryApi.assignTrainer(batch.batch_id, { trainer_user_id: Number(v.trainer), role: "Lead" });
      return batch;
    },
    {
      success: "Batch created",
      next: "Finish the setup on the batch page, then confirm it.",
      invalidate: [["delivery"], ["branch"], ["nav"]],
      onSuccess: (batch) => {
        setOpen(false);
        void navigate({ to: "/branch/batches/$id", params: { id: String(batch.batch_id) } });
      },
    },
  );

  const setOpen = (next: boolean) => {
    if (next) {
      setStep(0);
      setV(initial());
    }
    setOwnOpen(next);
    onOpenChange?.(next);
  };
  const problems = stepProblems(step, v);
  const course = (courses.data ?? []).find((c) => String(c.course_id) === v.course_id);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger !== undefined ? (
        trigger && <DialogTrigger asChild>{trigger}</DialogTrigger>
      ) : (
        <DialogTrigger asChild>
          <Button>New batch</Button>
        </DialogTrigger>
      )}
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New batch</DialogTitle>
          <DialogDescription>
            Step {step + 1} of {STEPS.length}: {STEPS[step]}. The course's approved curriculum is used. Nothing is final: you can change all of this on the
            batch page.
          </DialogDescription>
        </DialogHeader>
        <ol className="flex gap-1.5" aria-label="Steps">
          {STEPS.map((label, i) => (
            <li key={label} aria-current={i === step ? "step" : undefined} className={cn("h-1.5 flex-1 rounded-full", i <= step ? "bg-primary" : "bg-muted")}>
              <span className="sr-only">{label}</span>
            </li>
          ))}
        </ol>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (problems.length > 0) return setTried(true);
            if (step < STEPS.length - 1) setStep(step + 1);
            else create.mutate(undefined);
          }}
        >
          {step === 0 && (
            <>
              <Field label="Course *" htmlFor="nb-course">
                <NativeSelect
                  id="nb-course"
                  placeholder="Choose a course"
                  options={(courses.data ?? []).map((c) => ({ value: c.course_id, label: `${c.course_code} — ${c.title}` }))}
                  value={v.course_id}
                  onChange={(e) => set({ course_id: e.target.value })}
                />
              </Field>
              {branches.length !== 1 && (
                <Field label="Branch *" htmlFor="nb-branch">
                  <NativeSelect
                    id="nb-branch"
                    placeholder="Choose a branch"
                    options={branches.map((b) => ({ value: b.branch_id, label: b.branch_name }))}
                    value={v.branch_id}
                    onChange={(e) => set({ branch_id: e.target.value })}
                  />
                </Field>
              )}
              <Field label="Seats *" htmlFor="nb-capacity" hint="How many students the batch can take">
                <Input id="nb-capacity" type="number" min={1} value={v.capacity} onChange={(e) => set({ capacity: e.target.value })} />
              </Field>
            </>
          )}
          {step === 1 && (
            <>
              <Field label="Mode" htmlFor="nb-mode">
                <NativeSelect id="nb-mode" options={MODES} value={v.mode} onChange={(e) => set({ mode: e.target.value })} />
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Starts on" htmlFor="nb-start">
                  <Input id="nb-start" type="date" value={v.planned_start} onChange={(e) => set({ planned_start: e.target.value })} />
                </Field>
                <Field label="Ends on" htmlFor="nb-end">
                  <Input id="nb-end" type="date" value={v.planned_end} onChange={(e) => set({ planned_end: e.target.value })} />
                </Field>
              </div>
              <Field label="Teaching days" htmlFor="nb-days">
                <DayToggles id="nb-days" value={v.schedule_days} onChange={(days) => set({ schedule_days: days })} />
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Class starts (IST)" htmlFor="nb-from">
                  <Input id="nb-from" type="time" value={v.start_time} onChange={(e) => set({ start_time: e.target.value })} />
                </Field>
                <Field label="Class ends (IST)" htmlFor="nb-to">
                  <Input id="nb-to" type="time" value={v.end_time} onChange={(e) => set({ end_time: e.target.value })} />
                </Field>
              </div>
              {v.mode !== "Live Online" && (
                <Field label="Room" htmlFor="nb-room" hint="The classroom or lab">
                  <Input id="nb-room" value={v.location} onChange={(e) => set({ location: e.target.value })} />
                </Field>
              )}
              <p className="text-xs text-muted-foreground">Dates, days and times can be left for later, but the batch cannot be confirmed without them.</p>
            </>
          )}
          {step === 2 && (
            <>
              <Field label="Lead trainer" htmlFor="nb-trainer" hint="You can also assign the trainer later from the batch page">
                <NativeSelect
                  id="nb-trainer"
                  placeholder="I will assign one later"
                  options={(trainers.data ?? []).map((t) => ({ value: t.user_id, label: t.full_name }))}
                  value={v.trainer}
                  onChange={(e) => set({ trainer: e.target.value })}
                />
              </Field>
              <dl className="rounded-lg border bg-muted/40 p-3 text-sm">
                <div className="flex gap-2">
                  <dt className="text-muted-foreground">Course</dt>
                  <dd>{course ? `${course.course_code} — ${course.title}` : "—"}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="text-muted-foreground">Seats and mode</dt>
                  <dd>
                    {v.capacity} · {v.mode}
                  </dd>
                </div>
                <div className="flex gap-2">
                  <dt className="text-muted-foreground">Timetable</dt>
                  <dd>
                    {[v.schedule_days.replaceAll(",", ", "), v.start_time && v.end_time ? `${v.start_time}–${v.end_time}` : ""].filter(Boolean).join(" · ") ||
                      "Not set yet"}
                  </dd>
                </div>
              </dl>
            </>
          )}
          {tried && problems.length > 0 && (
            <ul role="alert" className="list-disc pl-5 text-sm text-danger">
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
          <DialogFooter className="gap-2 sm:justify-between">
            <Button type="button" variant="ghost" disabled={step === 0 || create.isPending} onClick={() => setStep(step - 1)}>
              Back
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {step < STEPS.length - 1 ? "Next" : "Create batch"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
