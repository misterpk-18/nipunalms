/** AI controls (Module 24 §11): switch an assistant off with scope and reason, and restore it once the checks pass. */
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/api/admin";
import { list, post } from "@/api/client";
import type { DateTime } from "@/api/types";
import { useAuth } from "@/auth/auth";
import { DataTable, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { FormDialog } from "@/features/shared/attendance-parts";
import { fmtDateTime } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";

type AiControl = {
  control_id: number;
  audience: "All" | "Student" | "Staff";
  branch_id: number | null;
  reason: string;
  remediation: string | null;
  disabled_at: DateTime;
  restored_at: DateTime | null;
  restoration_note: string | null;
  active: boolean;
};

const aiControlsApi = {
  list: () => list<AiControl>("/ai-controls", { per_page: 50 }),
  disable: (body: { audience: string; branch_id: number | null; reason: string; remediation?: string }) => post<AiControl>("/ai-controls", body),
  restore: (id: number, restoration_note: string) => post<AiControl>(`/ai-controls/${id}/restore`, { restoration_note }),
};

const KEY = ["ai-controls"];

export function AiControls() {
  const { hasRole } = useAuth();
  const founder = hasRole("FOUNDER_CEO");
  const controls = useQuery({ queryKey: KEY, queryFn: aiControlsApi.list });
  const branches = useQuery({ queryKey: ["reference", "branches"], queryFn: adminApi.branches });
  const branchName = (id: number | null) => (id === null ? "Company-wide" : (branches.data?.find((b) => b.branch_id === id)?.branch_name ?? `Branch ${id}`));
  const disable = useApiMutation(aiControlsApi.disable, { invalidate: [KEY], success: "AI switched off for that scope." });
  const restore = useApiMutation((v: { id: number; note: string }) => aiControlsApi.restore(v.id, v.note), { invalidate: [KEY], success: "AI restored." });
  const audiences = founder ? ["Student", "Staff", "All"] : ["Student", "Staff"];
  const branchOptions = ["Company-wide", ...(branches.data ?? []).map((b) => b.branch_name)];

  return (
    <div className="space-y-3">
      <FormDialog
        trigger={<Button variant="destructive">Switch AI off</Button>}
        title="Switch Ask Nipuna off"
        description={
          founder
            ? "Choose who it is switched off for. All switches every assistant off company-wide."
            : "Switch the student or staff assistant off, company-wide or at one branch. Only the Founder / CEO can switch all AI off."
        }
        submitLabel="Switch off"
        destructive
        fields={[
          { name: "audience", label: "Assistant", kind: "select", options: audiences, required: true, initial: "Student" },
          { name: "branch", label: "Scope", kind: "select", options: branchOptions, required: true, initial: "Company-wide" },
          { name: "reason", label: "Reason", kind: "textarea", required: true },
          { name: "remediation", label: "What is being done about it", kind: "textarea" },
        ]}
        onSubmit={(v) =>
          disable.mutateAsync({
            audience: v["audience"]!,
            branch_id: v["branch"] === "Company-wide" ? null : (branches.data?.find((b) => b.branch_name === v["branch"])?.branch_id ?? null),
            reason: v["reason"]!,
            remediation: v["remediation"] || undefined,
          })
        }
      />
      <QueryView query={controls} isEmpty={(p) => p.data.length === 0} empty="AI has not been switched off.">
        {(page) => (
          <DataTable
            caption="AI controls"
            rows={page.data}
            getKey={(c) => c.control_id}
            cols={[
              { h: "Assistant", c: (c) => (c.audience === "All" ? "All AI" : `${c.audience} assistant`) },
              { h: "Scope", c: (c) => branchName(c.branch_id) },
              { h: "Reason", c: (c) => [c.reason, c.remediation && `Remediation: ${c.remediation}`].filter(Boolean).join(" · ") },
              { h: "Switched off", c: (c) => fmtDateTime(c.disabled_at) },
              {
                h: "State",
                c: (c) =>
                  c.active ? (
                    <StatusBadge>Off</StatusBadge>
                  ) : (
                    `Restored ${fmtDateTime(c.restored_at)} — ${c.restoration_note ?? ""}`
                  ),
              },
              {
                h: "",
                c: (c) =>
                  c.active && (c.audience !== "All" || founder) ? (
                    <FormDialog
                      trigger={
                        <Button size="sm" variant="outline">
                          Restore
                        </Button>
                      }
                      title="Restore AI"
                      description="Restore only after the checks pass; record which."
                      submitLabel="Restore"
                      fields={[{ name: "note", label: "Checks that passed", kind: "textarea", required: true }]}
                      onSubmit={(v) => restore.mutateAsync({ id: c.control_id, note: v["note"]! })}
                    />
                  ) : null,
              },
            ]}
          />
        )}
      </QueryView>
    </div>
  );
}

