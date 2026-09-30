import { useState } from "react";
import { useExceptions } from "@/api/exceptions";
import { useAuth } from "@/auth/auth";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, Note, PageHead, QueryView, StatusBadge } from "@/components/lms/ui";
import { ageText } from "@/features/shared/format";
import { ItemCell, OwnerCell, RecoveryStepButton } from "@/features/shared/recovery-step";

/** One queue across slices for the coordinator's branch: curriculum mapping, allocation, recordings, support, results, provisioning. */
export function AcademicExceptions() {
  const [source, setSource] = useState("");
  const { hasRole } = useAuth();
  const canLog = hasRole("ACADEMIC_COORDINATOR", "SUPER_ADMIN");
  const query = useExceptions({ per_page: 100, source });
  const sourceOptions = ["CURRICULUM_MAPPING", "ALLOCATION", "PROVISIONING", "RECORDING", "SUPPORT", "RESULTS", "ACCESS_EXCEPTION"];

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHead title="Exception / Recovery queue" description="Open exceptions from every academic area at your branch. Each needs a named recovery owner." />
      <div className="max-w-64">
        <NativeSelect
          aria-label="Exception type"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          placeholder="All types"
          options={sourceOptions.map((s) => ({
            value: s,
            label: s
              .replace(/_/g, " ")
              .toLowerCase()
              .replace(/^./, (c) => c.toUpperCase()),
          }))}
        />
      </div>
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No exception is open. Resolved items leave the queue automatically.">
        {(page) => {
          const manyBranches = new Set(page.data.map((i) => i.branch?.branch_id)).size > 1;
          return (
            <DataTable
              caption="Exceptions"
              rows={page.data}
              getKey={(i) => `${i.source}-${i.source_id}`}
              cols={[
                { h: "ID", c: (i) => i.reference },
                { h: "Type", c: (i) => <ItemCell item={i} /> },
                ...(manyBranches ? [{ h: "Branch", c: (i: (typeof page.data)[number]) => i.branch?.branch_name ?? "All branches" }] : []),
                { h: "Recovery owner", c: (i) => <OwnerCell item={i} /> },
                { h: "State", c: (i) => <StatusBadge>{i.state}</StatusBadge> },
                { h: "Age", c: (i) => ageText(i.age_days) },
                { h: "Action", c: (i) => (canLog ? <RecoveryStepButton item={i} /> : <span className="text-xs text-muted-foreground">Read only</span>) },
              ]}
            />
          );
        }}
      </QueryView>
      <Note>
        An item leaves this queue when the screen that owns it resolves it. Logging a recovery step records what is being done and names you as owner.
      </Note>
    </div>
  );
}
