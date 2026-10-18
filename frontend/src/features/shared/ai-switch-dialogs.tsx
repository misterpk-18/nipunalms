/** The two questions the AI controls page asks: why switch it off (company-wide needs a typed confirmation), and what checks passed before it comes back. */
import { useState } from "react";
import { adminApi, adminKeys, type AiAudience, type AiControl } from "@/api/admin";
import { Field } from "@/components/lms/forms";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";
import { FormDialog } from "@/features/shared/form-parts";

export const CONFIRM_PHRASE = "SWITCH OFF";
const INVALIDATE = [[...adminKeys.aiStatus], ["admin", "ai-history"], [...adminKeys.needsAction]];

export const audienceName = (audience: AiAudience) =>
  audience === "All" ? "all AI" : audience === "Student" ? "the student assistant" : "the staff assistant";

export function SwitchOffDialog({
  audience,
  branch,
  onClose,
}: {
  audience: AiAudience;
  /** Set to switch off for one branch only; company-wide (no branch) needs the typed confirmation. */
  branch?: { branch_id: number; branch_name: string };
  onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  const [remediation, setRemediation] = useState("");
  const [typed, setTyped] = useState("");
  const companyWide = !branch;
  const off = useApiMutation(adminApi.switchAiOff, {
    success: `${audienceName(audience)} is switched off${branch ? ` at ${branch.branch_name}` : ""}`,
    next: "People it covers see that it is unavailable until you switch it back on.",
    invalidate: INVALIDATE,
    onSuccess: onClose,
  });
  const ready = reason.trim().length >= 3 && (!companyWide || typed.trim() === CONFIRM_PHRASE);
  return (
    <FormDialog
      title={`Switch off ${audienceName(audience)}${branch ? ` at ${branch.branch_name}` : ""}`}
      description={
        companyWide
          ? `This stops ${audienceName(audience)} for everyone in the company, now. Nobody it covers can use it until you switch it back on.`
          : `Only people at ${branch.branch_name} lose it. The rest of the company is not affected.`
      }
      submitLabel="Switch off"
      destructive
      busy={off.isPending || !ready}
      onClose={onClose}
      onSubmit={() =>
        off.mutate({
          audience,
          branch_id: branch?.branch_id ?? null,
          reason: reason.trim(),
          ...(remediation.trim() ? { remediation: remediation.trim() } : {}),
        })
      }
    >
      <Field label="Why are you switching it off?" htmlFor="ai-reason" hint="Written to the audit log.">
        <Textarea id="ai-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
      <Field label="What is being done about it? (optional)" htmlFor="ai-remediation">
        <Textarea id="ai-remediation" rows={2} value={remediation} onChange={(e) => setRemediation(e.target.value)} />
      </Field>
      {companyWide && (
        <Field label={`Type ${CONFIRM_PHRASE} to confirm`} htmlFor="ai-confirm">
          <Input id="ai-confirm" autoComplete="off" value={typed} onChange={(e) => setTyped(e.target.value)} />
        </Field>
      )}
    </FormDialog>
  );
}

export function RestoreDialog({ control, label, onClose }: { control: AiControl; label: string; onClose: () => void }) {
  const [note, setNote] = useState("");
  const restore = useApiMutation((v: { id: number; note: string }) => adminApi.restoreAi(v.id, v.note), {
    success: `${label} is back on`,
    invalidate: INVALIDATE,
    onSuccess: onClose,
  });
  return (
    <FormDialog
      title={`Switch ${label} back on`}
      description="Do this only after the checks pass. Say which, so the audit log shows why it was safe."
      submitLabel="Switch back on"
      busy={restore.isPending || note.trim().length < 3}
      onClose={onClose}
      onSubmit={() => restore.mutate({ id: control.control_id, note: note.trim() })}
    >
      <Field label="Checks that passed" htmlFor="ai-note">
        <Textarea id="ai-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
    </FormDialog>
  );
}
