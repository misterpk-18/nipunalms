/** Assign an issue: pick the member of staff who should fix it and say what you expect. They are told. */
import { useState } from "react";
import { adminKeys } from "@/api/admin";
import { issuesApi, type Issue } from "@/api/issues";
import { Field, NativeSelect } from "@/components/lms/forms";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";
import { FormDialog } from "./form-parts";
import { useAllStaff } from "./staff-options";

export function AssignDialog({ issue, onClose }: { issue: Issue; onClose: () => void }) {
  const staff = useAllStaff();
  const [who, setWho] = useState("");
  const [note, setNote] = useState("");
  const name = staff.options.find((o) => String(o.value) === who)?.label.replace(/ \(.*\)$/, "") ?? "them";
  const assign = useApiMutation(() => issuesApi.assign(issue, Number(who), note.trim() || undefined), {
    success: `Assigned to ${name}`,
    next: "They are told, and the issue shows them as its owner.",
    invalidate: [["issues"], [...adminKeys.needsAction], ["nav", "counts"]],
    onSuccess: onClose,
  });
  return (
    <FormDialog
      title="Assign this issue"
      description={issue.title}
      submitLabel="Assign"
      busy={assign.isPending || !who}
      onClose={onClose}
      onSubmit={() => assign.mutate()}
    >
      <Field label="Who should fix it?" htmlFor="as-who">
        <NativeSelect id="as-who" placeholder="Pick a person" value={who} onChange={(e) => setWho(e.target.value)} options={staff.options} />
      </Field>
      <Field label="What do you expect? (optional)" htmlFor="as-note">
        <Textarea id="as-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
    </FormDialog>
  );
}
