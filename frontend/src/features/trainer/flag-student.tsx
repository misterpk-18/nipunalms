import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { SUPPORT_CATEGORIES, supportApi, type SupportCategory } from "@/api/support";
import { Field, NativeSelect, applyServerErrors } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";

type Values = { student_id: string; category: SupportCategory; details: string };
export type FlagTarget = { student_id: number; student_code: string; full_name: string };

/**
 * Raise a support request about a student. With `student` the student is already chosen (a row, a student page);
 * without one the trainer picks from their students. The request goes to the owner for its category and the student is told.
 */
export function FlagStudentDialog({ open, onOpenChange, student }: { open: boolean; onOpenChange: (open: boolean) => void; student?: FlagTarget | undefined }) {
  const students = useQuery({ queryKey: ["support", "assigned-students"], queryFn: supportApi.assignedStudents, enabled: open && !student });
  const form = useForm<Values>({ defaultValues: { student_id: student ? String(student.student_id) : "", category: "Academic", details: "" } });
  const flag = useApiMutation(
    (values: Values) => supportApi.raise({ student_id: Number(values.student_id), category: values.category, details: values.details }),
    {
      success: (request) => `${request.request_code} raised for ${request.student.full_name}`,
      next: (request) => `It is with ${request.owner.label}. The student is told you raised it.`,
      view: { to: "/trainer/support", label: "Open Support" },
      invalidate: [["support"], ["trainer"]],
      silentValidation: true,
      onSuccess: () => {
        form.reset({ student_id: student ? String(student.student_id) : "", category: "Academic", details: "" });
        onOpenChange(false);
      },
      onError: (error) => applyServerErrors(form, error),
    },
  );
  const choices = [...new Map((students.data ?? []).map((r) => [r.student.student_id, r.student])).values()];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={form.handleSubmit((values) => flag.mutate(values))} noValidate className="space-y-3">
          <DialogHeader>
            <DialogTitle>{student ? `Flag ${student.full_name}` : "Raise a support request"}</DialogTitle>
            <DialogDescription>
              Tell the right person about a problem. The request goes to the owner for its category (your Branch Manager for most), and the student is told you
              raised it.
            </DialogDescription>
          </DialogHeader>
          {student ? (
            <p className="text-sm">
              Student: <span className="font-medium">{student.full_name}</span> <span className="font-mono text-xs">{student.student_code}</span>
            </p>
          ) : (
            <Field label="Student" htmlFor="flag-student" error={form.formState.errors.student_id?.message}>
              <NativeSelect
                id="flag-student"
                placeholder="Choose a student"
                {...form.register("student_id", { required: "Choose a student" })}
                options={choices.map((s) => ({ value: s.student_id, label: `${s.full_name} (${s.student_code})` }))}
              />
            </Field>
          )}
          <Field label="What is it about?" htmlFor="flag-category">
            <NativeSelect id="flag-category" {...form.register("category")} options={SUPPORT_CATEGORIES.map((c) => ({ value: c, label: c }))} />
          </Field>
          <Field label="Details" htmlFor="flag-details" error={form.formState.errors.details?.message}>
            <Textarea
              id="flag-details"
              rows={3}
              {...form.register("details", { required: "Say what the problem is", minLength: { value: 3, message: "Add a few words" } })}
            />
          </Field>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={flag.isPending}>
              Raise request
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
