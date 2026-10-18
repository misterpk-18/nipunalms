/** The main button of a student's suggested next step, and the actions behind it. Used by the Student accounts list and the student's page. */
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { LinkIcon, RotateCcw } from "lucide-react";
import { adminApi, adminKeys, type ActivationIssued, type SuggestedStep } from "@/api/admin";
import { Button } from "@/components/ui/button";
import { useApiMutation } from "@/lib/mutation";
import { SecretDialog } from "@/features/shared/form-parts";
import { areaLink, areaTo, type CentralArea } from "@/features/shared/central-area";
import { istDateTime, whatsappLine } from "./format";

/** The list, the open student and the home all change with any account action. */
export const ACCOUNT_KEYS = () => [[...adminKeys.studentsAll], ["admin", "student"], [...adminKeys.needsAction], ["nav", "counts"]];

export function NextStepButton({ area, studentId, step, size = "sm" }: { area: CentralArea; studentId: number; step: SuggestedStep; size?: "sm" | "default" }) {
  const { canEdit } = area;
  const [issued, setIssued] = useState<ActivationIssued | null>(null);
  const issue = useApiMutation(() => adminApi.issueActivation(studentId), { invalidate: ACCOUNT_KEYS(), onSuccess: setIssued });
  const reactivate = useApiMutation(() => adminApi.reactivateStudent(studentId), { success: "Account reactivated", invalidate: ACCOUNT_KEYS() });
  if (!step.action || !step.action_label) return null;

  if (step.action === "issues")
    return (
      <Button asChild size={size}>
        <Link to={areaTo(area, "/issues")}>{step.action_label}</Link>
      </Button>
    );
  if (step.action === "open")
    return (
      <Button asChild size={size}>
        <Link {...areaLink(area, "/students/$id", { id: String(studentId) })}>
          {step.action_label}
        </Link>
      </Button>
    );
  if (!canEdit) return null;
  return (
    <>
      {step.action === "send_link" ? (
        <Button size={size} disabled={issue.isPending} onClick={() => issue.mutate()}>
          <LinkIcon className="size-3.5" aria-hidden /> {step.action_label}
        </Button>
      ) : (
        <Button size={size} disabled={reactivate.isPending} onClick={() => reactivate.mutate()}>
          <RotateCcw className="size-3.5" aria-hidden /> {step.action_label}
        </Button>
      )}
      {issued && (
        <SecretDialog
          title="Activation link ready"
          description={`${whatsappLine(issued.whatsapp, issued.student_code)} It works once, expires ${istDateTime(issued.expires_at)} and is shown only now. Any earlier link no longer works.`}
          secrets={[{ label: "Activation link", value: `${window.location.origin}${issued.activation_path}` }]}
          onClose={() => setIssued(null)}
        />
      )}
    </>
  );
}
