import { useMemo } from "react";
import { useExceptions, type ExceptionItem } from "@/api/exceptions";
import { useAuth } from "@/auth/auth";
import { DataTable, Note, PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { ageText } from "@/features/shared/format";
import { ItemCell, OwnerCell, RecoveryStepButton } from "@/features/shared/recovery-step";

function byQueue(rows: ExceptionItem[]): [string, ExceptionItem[]][] {
  const groups = new Map<string, ExceptionItem[]>();
  for (const row of rows) groups.set(row.queue, [...(groups.get(row.queue) ?? []), row]);
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

/** Every open exception across all branches, grouped by the queue it belongs to. */
export function AdminExceptions() {
  const { hasRole } = useAuth();
  const canLog = hasRole("SUPER_ADMIN");
  const query = useExceptions({ per_page: 100 });
  const groups = useMemo(() => byQueue(query.data?.data ?? []), [query.data]);

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHead
        title="Exception Queues — all branches"
        description="Meet / recording, access, CRM/LMS sync, provisioning and academic exceptions in one place."
      />
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No exception is open in any queue.">
        {(page) => (
          <>
            <p className="text-sm text-muted-foreground">
              {page.meta.total} open · {page.data.filter((i) => i.awaiting_owner).length} awaiting a named owner
            </p>
            {groups.map(([queue, rows]) => (
              <Section key={queue} title={`${queue} (${rows.length})`}>
                <DataTable
                  caption={queue}
                  rows={rows}
                  getKey={(i) => `${i.source}-${i.source_id}`}
                  cols={[
                    { h: "ID", c: (i) => i.reference },
                    { h: "Item", c: (i) => <ItemCell item={i} /> },
                    { h: "Branch", c: (i) => i.branch?.branch_name ?? "All branches" },
                    { h: "Owner", c: (i) => <OwnerCell item={i} /> },
                    { h: "State", c: (i) => <StatusBadge>{i.state}</StatusBadge> },
                    { h: "Age", c: (i) => ageText(i.age_days) },
                    { h: "Action", c: (i) => (canLog ? <RecoveryStepButton item={i} /> : <span className="text-xs text-muted-foreground">Read only</span>) },
                  ]}
                />
              </Section>
            ))}
          </>
        )}
      </QueryView>
      <Note>The queue reads each slice's own records; resolving an item where it lives removes it here. Recovery steps are audited.</Note>
    </div>
  );
}
