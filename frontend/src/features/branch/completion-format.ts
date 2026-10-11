/** Words for the completion pipeline. */
import type { PipelineCheck } from "@/api/completion-pipeline";

/** Rupees the way staff say them: "Rs 5,000". */
export function rupees(amount: string | number | null | undefined): string {
  const n = Number(amount);
  if (amount === null || amount === undefined || Number.isNaN(n)) return "an unknown amount";
  return `Rs ${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

/** "Attendance 82% of 75% needed", "Missed classes made up: none still to do", "Trainer recommends complete". */
export function checkText(c: PipelineCheck): string {
  if (c.key === "recoveries") return c.ok ? `${c.label}: none still to do` : `${c.label}: ${c.value} still to do`;
  if (c.unit === "%") {
    if (c.value === null || c.value === "") return `${c.label}: no figure yet (${c.threshold}% needed)`;
    return `${c.label} ${Math.round(Number(c.value))}% of ${c.threshold}% needed`;
  }
  return c.label;
}
