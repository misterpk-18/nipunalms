/** Readiness table (integrations and security controls): requirement, configuration, operational verification, evidence, owner. */
import { useForm } from "react-hook-form";
import { Pencil } from "lucide-react";
import { CONFIGURATION_STATUSES, VERIFICATION_STATUSES, type ConfigurationStatus, type ReadinessUpdate, type VerificationStatus } from "@/api/admin";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, NativeSelect, applyServerErrors } from "@/components/lms/forms";
import { DataTable, StatusBadge, type Tone } from "@/components/lms/ui";
import { useApiMutation } from "@/lib/mutation";
import { FormDialog } from "./shared";
import { istDateTime } from "./format";

export type ReadinessRow = {
  key: string;
  item: string;
  group?: string;
  requirement: string;
  configuration_status: ConfigurationStatus;
  verification_status: VerificationStatus;
  owner: string;
  evidence: string | null;
  notes: string | null;
  verified_at: string | null;
  last_checked_at: string | null;
};

const CONFIGURATION_TONE: Record<ConfigurationStatus, Tone> = {
  "Not Configured": "neutral",
  "Configuration Pending": "warning",
  Configured: "success",
  Misconfigured: "danger",
};

const VERIFICATION_TONE: Record<VerificationStatus, Tone> = {
  "Not Verified": "neutral",
  "Pending Verification": "warning",
  Verified: "success",
  Failed: "danger",
};

export function ReadinessTable({ rows, caption, onEdit }: { rows: ReadinessRow[]; caption: string; onEdit?: (row: ReadinessRow) => void }) {
  return (
    <DataTable
      caption={caption}
      rows={rows}
      getKey={(r) => r.key}
      cols={[
        {
          h: "Item",
          c: (r) => (
            <>
              <div className="font-medium">{r.item}</div>
              {r.group && <div className="text-xs text-muted-foreground">{r.group}</div>}
              {r.notes && <div className="text-xs text-muted-foreground">{r.notes}</div>}
            </>
          ),
        },
        { h: "Requirement", c: (r) => <span className="text-sm">{r.requirement}</span> },
        { h: "Configuration", c: (r) => <StatusBadge tone={CONFIGURATION_TONE[r.configuration_status]}>{r.configuration_status}</StatusBadge> },
        {
          h: "Operational verification",
          c: (r) => (
            <>
              <StatusBadge tone={VERIFICATION_TONE[r.verification_status]}>{r.verification_status}</StatusBadge>
              {r.evidence && <div className="mt-1 text-xs text-muted-foreground">Evidence: {r.evidence}</div>}
              {r.verified_at && <div className="text-xs text-muted-foreground">Verified {istDateTime(r.verified_at)}</div>}
            </>
          ),
        },
        { h: "Owner", c: (r) => r.owner },
        { h: "Last check", c: (r) => istDateTime(r.last_checked_at) },
        ...(onEdit
          ? [
              {
                h: "Action",
                c: (r: ReadinessRow) => (
                  <Button variant="outline" size="sm" onClick={() => onEdit(r)} aria-label={`Update ${r.item}`}>
                    <Pencil className="size-3.5" /> Update
                  </Button>
                ),
              },
            ]
          : []),
      ]}
    />
  );
}

type UpdateForm = { configuration_status: ConfigurationStatus; verification_status: VerificationStatus; owner: string; evidence: string; notes: string };

/** Update dialog: "Verified" needs a Configured setup and an evidence note (the server enforces both). */
export function ReadinessDialog({
  row,
  save,
  invalidate,
  onClose,
}: {
  row: ReadinessRow;
  save: (body: ReadinessUpdate) => Promise<unknown>;
  invalidate: readonly (readonly string[])[];
  onClose: () => void;
}) {
  const form = useForm<UpdateForm>({
    values: {
      configuration_status: row.configuration_status,
      verification_status: row.verification_status,
      owner: row.owner,
      evidence: row.evidence ?? "",
      notes: row.notes ?? "",
    },
  });
  const mutation = useApiMutation(
    (v: UpdateForm) =>
      save({ configuration_status: v.configuration_status, verification_status: v.verification_status, owner: v.owner, evidence: v.evidence, notes: v.notes }),
    {
      success: `${row.item} updated`,
      invalidate: invalidate.map((k) => [...k]),
      onSuccess: onClose,
      silentValidation: true,
      onError: (e) => applyServerErrors(form, e),
    },
  );
  const errors = form.formState.errors;
  return (
    <FormDialog
      title={`Update ${row.item}`}
      description="Verified means it was seen working, not just set up: record how in the evidence note."
      onClose={onClose}
      busy={mutation.isPending}
      onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Configuration" htmlFor="rd-config" error={errors.configuration_status?.message}>
          <NativeSelect id="rd-config" options={CONFIGURATION_STATUSES.map((s) => ({ value: s, label: s }))} {...form.register("configuration_status")} />
        </Field>
        <Field label="Operational verification" htmlFor="rd-verify" error={errors.verification_status?.message}>
          <NativeSelect id="rd-verify" options={VERIFICATION_STATUSES.map((s) => ({ value: s, label: s }))} {...form.register("verification_status")} />
        </Field>
      </div>
      <Field label="Owner" htmlFor="rd-owner" error={errors.owner?.message}>
        <Input id="rd-owner" {...form.register("owner", { required: "Required" })} />
      </Field>
      <Field label="Evidence" htmlFor="rd-evidence" error={errors.evidence?.message} hint="What was checked, when and by whom — required for Verified">
        <Textarea id="rd-evidence" rows={3} {...form.register("evidence")} />
      </Field>
      <Field label="Notes" htmlFor="rd-notes" error={errors.notes?.message}>
        <Textarea id="rd-notes" rows={2} {...form.register("notes")} />
      </Field>
    </FormDialog>
  );
}
