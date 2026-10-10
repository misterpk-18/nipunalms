import { Check, Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

/**
 * Live checks under a new-password field: each rule ticks as the person types, so they know what is still missing before
 * they press the button. `differsFrom` adds "different from your current password" (change password).
 */
export function PasswordChecklist({
  password,
  confirm,
  minLength,
  differsFrom,
}: {
  password: string;
  confirm: string;
  minLength: number;
  differsFrom?: string;
}) {
  const t = useT();
  const rules = [
    { key: "length", ok: password.length >= minLength, label: t("ruleLength", { n: minLength }) },
    ...(differsFrom !== undefined ? [{ key: "differs", ok: password.length > 0 && password !== differsFrom, label: t("ruleDiffers") }] : []),
    { key: "match", ok: password.length > 0 && password === confirm, label: t("ruleMatch") },
  ];
  return (
    <ul className="space-y-1 text-sm" aria-label="Password rules">
      {rules.map((rule) => (
        <li key={rule.key} className={cn("flex items-center gap-2", rule.ok ? "text-success" : "text-muted-foreground")}>
          {rule.ok ? <Check className="size-4" aria-hidden /> : <Circle className="size-3.5" aria-hidden />}
          <span>{rule.label}</span>
          <span className="sr-only">{rule.ok ? "done" : "not yet"}</span>
        </li>
      ))}
    </ul>
  );
}

/** True when every rule above holds: the button stays disabled until then. */
export const passwordReady = (password: string, confirm: string, minLength: number, differsFrom?: string) =>
  password.length >= minLength && password === confirm && (differsFrom === undefined || password !== differsFrom);
