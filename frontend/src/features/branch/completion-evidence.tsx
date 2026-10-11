/** The evidence behind a completion decision, one line per check against the course's own threshold. Never merged into one score. */
import { CheckCircle2, XCircle } from "lucide-react";
import type { PipelineCheck } from "@/api/completion-pipeline";
import { checkText } from "./completion-format";

export function EvidenceList({ checks }: { checks: PipelineCheck[] }) {
  return (
    <ul className="space-y-1.5 text-sm" aria-label="Evidence against the course thresholds">
      {checks.map((c) => {
        const Icon = c.ok ? CheckCircle2 : XCircle;
        return (
          <li key={c.key} className="flex items-start gap-2">
            <Icon className={c.ok ? "mt-0.5 size-4 shrink-0 text-success" : "mt-0.5 size-4 shrink-0 text-danger"} aria-hidden />
            <span className="min-w-0">
              <span className="sr-only">{c.ok ? "Met: " : "Not met: "}</span>
              {checkText(c)}
              {c.detail && c.key !== "recoveries" && <span className="block text-xs text-muted-foreground">{c.detail}</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
