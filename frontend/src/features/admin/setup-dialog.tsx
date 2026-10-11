/** Update one row of Setup & health: where it stands, who owns it, and how it was checked. */
import { useForm } from "react-hook-form";
import { adminApi, adminKeys, SETUP_STATES, type SetupItem, type SetupState } from "@/api/admin";
import { Field, NativeSelect, applyServerErrors } from "@/components/lms/forms";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";
import { statusInfo } from "@/lib/status";
import { FormDialog } from "./shared";
import { useAllStaff } from "./staff-options";

type Form = { state: SetupState; owner_user_id: string; evidence: string; notes: string };

export function SetupDialog({ item, onClose }: { item: SetupItem; onClose: () => void }) {
  const staff = useAllStaff();
  const form = useForm<Form>({
    values: { state: item.state, owner_user_id: item.owner.user_id ? String(item.owner.user_id) : "", evidence: item.evidence ?? "", notes: item.notes ?? "" },
  });
  const state = form.watch("state");
  const save = useApiMutation(
    (v: Form) => {
      const body = {
        ...(v.state !== item.state ? { state: v.state } : {}),
        owner_user_id: v.owner_user_id ? Number(v.owner_user_id) : null,
        evidence: v.evidence.trim() || null,
        notes: v.notes.trim() || null,
      };
      return (item.kind === "integration" ? adminApi.updateIntegration(item.id, body) : adminApi.updateControl(item.id, body)).then(() => undefined);
    },
    {
      success: `${item.name} updated`,
      invalidate: [[...adminKeys.setup], [...adminKeys.needsAction], ["nav", "counts"]],
      onSuccess: onClose,
      silentValidation: true,
      onError: (e) => applyServerErrors(form, e),
    },
  );
  const errors = form.formState.errors;
  return (
    <FormDialog
      title={`Update ${item.name}`}
      description={item.requirement}
      busy={save.isPending}
      onClose={onClose}
      onSubmit={form.handleSubmit((v) => save.mutate(v))}
    >
      <Field label="Where does it stand?" htmlFor="su-state" error={errors.state?.message} hint={statusInfo("setup", state).help}>
        <NativeSelect id="su-state" options={SETUP_STATES.map((s) => ({ value: s, label: s }))} {...form.register("state")} />
      </Field>
      <Field label="Owner" htmlFor="su-owner" error={errors.owner_user_id?.message} hint="The person who keeps this working.">
        <NativeSelect id="su-owner" placeholder="No owner yet" options={staff.options} {...form.register("owner_user_id")} />
      </Field>
      <Field
        label="How you checked it"
        htmlFor="su-evidence"
        error={errors.evidence?.message}
        hint={state === "Working" ? "Required to mark it Working: what you checked, when and how." : "Optional."}
      >
        <Textarea id="su-evidence" rows={3} {...form.register("evidence")} />
      </Field>
      <Field label="Notes" htmlFor="su-notes" error={errors.notes?.message}>
        <Textarea id="su-notes" rows={2} {...form.register("notes")} />
      </Field>
    </FormDialog>
  );
}
