import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { SUPPORT_CATEGORIES, supportApi, type SupportCategory } from "@/api/support";
import { Field, NativeSelect, applyServerErrors } from "@/components/lms/forms";
import { DataTable, Note, PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";
import { SupportDesk } from "@/features/shared/support-desk";

type Values = { student_id: string; category: SupportCategory; details: string };

/** Trainer support: flag a student's problem to the right owner, and follow the requests the trainer owns or raised. */
export function TrainerSupport() {
  const [flagging, setFlagging] = useState(false);
  const students = useQuery({ queryKey: ["support", "assigned-students"], queryFn: supportApi.assignedStudents });
  const form = useForm<Values>({ defaultValues: { student_id: "", category: "Academic", details: "" } });
  const flag = useApiMutation(
    (values: Values) => supportApi.raise({ student_id: Number(values.student_id), category: values.category, details: values.details }),
    {
      success: (request) => `Support flag ${request.request_code} raised. Owner: ${request.owner.label}`,
      invalidate: [["support"]],
      silentValidation: true,
      onSuccess: () => {
        form.reset();
        setFlagging(false);
      },
      onError: (error) => applyServerErrors(form, error),
    },
  );

  return (
    <>
      <PageHead
        title="Student support flags"
        description="Open requests for your assigned students."
        actions={<Button onClick={() => setFlagging(true)}>Flag a student</Button>}
      />
      <div className="space-y-4">
        <Section title="Support requests">
          <SupportDesk mode="staff" caption="Support flags" empty="No open support flags for your students." base={{ mine: true }} />
        </Section>
        <Section title="Students with an open flag">
          <QueryView query={students} isEmpty={(rows) => rows.every((r) => r.open_requests.length === 0)} empty="None of your students has an open request.">
            {(rows) => (
              <DataTable
                caption="Flagged students"
                rows={rows.filter((r) => r.open_requests.length > 0)}
                getKey={(r) => r.student.student_id}
                cols={[
                  { h: "Student", c: (r) => r.student.full_name },
                  { h: "Batch", c: (r) => <span className="font-mono text-xs">{r.batch.batch_code}</span> },
                  { h: "Support flag", c: (r) => <StatusBadge>{r.flag}</StatusBadge> },
                ]}
              />
            )}
          </QueryView>
        </Section>
        <Note>Contact details and finance are not visible to trainers.</Note>
      </div>

      <Dialog open={flagging} onOpenChange={setFlagging}>
        <DialogContent>
          <form onSubmit={form.handleSubmit((values) => flag.mutate(values))} noValidate className="space-y-3">
            <DialogHeader>
              <DialogTitle>Flag a student</DialogTitle>
              <DialogDescription>The request goes to the right owner by category. The student is told you raised it.</DialogDescription>
            </DialogHeader>
            <Field label="Student" htmlFor="flag-student" error={form.formState.errors.student_id?.message}>
              <NativeSelect
                id="flag-student"
                placeholder="Choose a student"
                {...form.register("student_id", { required: "Required" })}
                options={[...new Map((students.data ?? []).map((r) => [r.student.student_id, r.student])).values()].map((s) => ({
                  value: s.student_id,
                  label: `${s.full_name} (${s.student_code})`,
                }))}
              />
            </Field>
            <Field label="Category" htmlFor="flag-category">
              <NativeSelect id="flag-category" {...form.register("category")} options={SUPPORT_CATEGORIES.map((c) => ({ value: c, label: c }))} />
            </Field>
            <Field label="Details" htmlFor="flag-details" error={form.formState.errors.details?.message}>
              <Textarea
                id="flag-details"
                rows={3}
                {...form.register("details", { required: "Required", minLength: { value: 3, message: "Add a few words" } })}
              />
            </Field>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFlagging(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={flag.isPending}>
                Raise flag
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
