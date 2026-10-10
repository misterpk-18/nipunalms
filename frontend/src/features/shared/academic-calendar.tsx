/** The Nipuna Academic Calendar (Module 15 §9): company holidays set centrally, branch closures approved by the Branch
 * Manager. Approved closures that fall on scheduled classes ask the Branch Managers for replacements; nothing moves by itself. */
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/api/admin";
import { list, post } from "@/api/client";
import type { BranchRef, DateOnly, DateTime, UserRef } from "@/api/types";
import { useAuth } from "@/auth/auth";
import { DataTable, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { FormDialog } from "@/features/shared/attendance-parts";
import { fmtDate } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";

type Closure = {
  closure_id: number;
  kind: "Company Holiday" | "Branch Closure";
  branch: BranchRef | null;
  starts_on: DateOnly;
  ends_on: DateOnly;
  title: string;
  reason: string | null;
  status: "Pending" | "Approved" | "Rejected";
  requested_by: UserRef;
  requested_at: DateTime;
  decided_by: UserRef | null;
  decision_note: string | null;
};

const calendarApi = {
  list: () => list<Closure>("/calendar/closures", { per_page: 100 }),
  create: (body: { kind: string; branch_id: number | null; starts_on: string; ends_on: string; title: string; reason?: string }) =>
    post<Closure>("/calendar/closures", body),
  decide: (id: number, decision: string, note?: string) => post<Closure>(`/calendar/closures/${id}/decision`, { decision, note }),
};
const KEY = ["calendar", "closures"];

export function AcademicCalendar() {
  const { hasRole, profile } = useAuth();
  const central = hasRole("FOUNDER_CEO", "SUPER_ADMIN");
  const proposer = hasRole("BRANCH_MANAGER", "SUPER_ADMIN");
  const approver = hasRole("BRANCH_MANAGER", "SUPER_ADMIN");
  const closures = useQuery({ queryKey: KEY, queryFn: calendarApi.list });
  const branches = useQuery({ queryKey: ["reference", "branches"], queryFn: adminApi.branches, enabled: central });
  const branchOptions = central ? (branches.data ?? []) : (profile?.allowed_branches ?? []);
  const create = useApiMutation(calendarApi.create, {
    invalidate: [KEY],
    success: (c) => (c.status === "Approved" ? "Added to the calendar." : "Proposed; the Branch Manager approves it."),
  });
  const decide = useApiMutation((v: { id: number; decision: string; note?: string }) => calendarApi.decide(v.id, v.decision, v.note), {
    invalidate: [KEY],
    success: (c) => `Closure ${c.status.toLowerCase()}.`,
  });
  const kinds = [...(central ? ["Company Holiday"] : []), ...(proposer ? ["Branch Closure"] : [])];

  return (
    <div className="space-y-3">
      {kinds.length > 0 && (
        <FormDialog
          trigger={<Button variant="outline">Add to the calendar</Button>}
          title="Add a holiday or closure"
          description="Weekends and bank holidays are not closed unless they are added here. A branch closure needs the Branch Manager's approval."
          submitLabel="Add"
          fields={[
            { name: "kind", label: "Kind", kind: "select", options: kinds, required: true, initial: kinds[0] },
            {
              name: "branch",
              label: "Branch (for a branch closure)",
              kind: "select",
              options: branchOptions.map((b) => b.branch_name),
              initial: branchOptions[0]?.branch_name,
            },
            { name: "starts_on", label: "From", kind: "date", required: true },
            { name: "ends_on", label: "To (inclusive)", kind: "date", required: true },
            { name: "title", label: "Title", kind: "text", required: true },
            { name: "reason", label: "Reason", kind: "textarea" },
          ]}
          onSubmit={(v) =>
            create.mutateAsync({
              kind: v["kind"]!,
              branch_id: v["kind"] === "Branch Closure" ? (branchOptions.find((b) => b.branch_name === v["branch"])?.branch_id ?? null) : null,
              starts_on: v["starts_on"]!,
              ends_on: v["ends_on"]!,
              title: v["title"]!,
              reason: v["reason"] || undefined,
            })
          }
        />
      )}
      <QueryView query={closures} isEmpty={(p) => p.data.length === 0} empty="No holidays or closures are published.">
        {(page) => (
          <DataTable
            caption="Academic Calendar"
            rows={page.data}
            getKey={(c) => c.closure_id}
            cols={[
              { h: "Dates", c: (c) => (c.starts_on === c.ends_on ? fmtDate(c.starts_on) : `${fmtDate(c.starts_on)} – ${fmtDate(c.ends_on)}`) },
              { h: "What", c: (c) => [c.title, c.reason].filter(Boolean).join(" — ") },
              { h: "Applies to", c: (c) => c.branch?.branch_name ?? "Every branch" },
              { h: "Status", c: (c) => <StatusBadge>{c.status}</StatusBadge> },
              {
                h: "",
                c: (c) =>
                  approver && c.status === "Pending" ? (
                    <FormDialog
                      trigger={<Button size="sm">Decide</Button>}
                      title={`Branch closure: ${c.title}`}
                      description="Approving closes the branch on these dates; Branch Managers are asked to replace affected classes."
                      submitLabel="Record decision"
                      fields={[
                        { name: "decision", label: "Decision", kind: "select", options: ["Approved", "Rejected"], required: true, initial: "Approved" },
                        { name: "note", label: "Note (required to reject)", kind: "textarea" },
                      ]}
                      onSubmit={(v) => decide.mutateAsync({ id: c.closure_id, decision: v["decision"]!, note: v["note"] || undefined })}
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
