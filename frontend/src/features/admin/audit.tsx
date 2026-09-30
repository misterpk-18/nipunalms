import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminApi, adminKeys, type AuditEntry, type AuditFilters } from "@/api/admin";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, Note, PageHead, QueryView, Section } from "@/components/lms/ui";
import { FilterField, Pager } from "./shared";
import { istDateTime } from "./format";

function Changes({ entry }: { entry: AuditEntry }) {
  const keys = [...new Set([...Object.keys(entry.old_values ?? {}), ...Object.keys(entry.new_values ?? {})])];
  if (keys.length === 0) return <span className="text-muted-foreground">—</span>;
  return (
    <ul className="space-y-0.5 text-xs">
      {keys.map((key) => (
        <li key={key} className="break-words">
          <span className="font-medium">{key}</span>
          {entry.old_values && key in entry.old_values && <span className="text-muted-foreground"> {JSON.stringify(entry.old_values[key])} →</span>}{" "}
          {entry.new_values && key in entry.new_values ? JSON.stringify(entry.new_values[key]) : ""}
        </li>
      ))}
    </ul>
  );
}

/** Audit Log: the append-only history of sensitive changes, filtered by actor, entity, action and date (IST). */
export function AdminAudit() {
  const [filters, setFilters] = useState<AuditFilters>({});
  const facets = useQuery({ queryKey: adminKeys.auditFacets, queryFn: adminApi.auditFacets });
  const staff = useQuery({ queryKey: adminKeys.users({ page: 1 }), queryFn: () => adminApi.users({ page: 1 }) });
  const query = useQuery({ queryKey: adminKeys.audit(filters), queryFn: () => adminApi.audit(filters) });
  const set = (patch: Partial<AuditFilters>) => setFilters({ ...filters, ...patch, page: 1 });

  return (
    <>
      <PageHead title="Audit Log" description="Who changed what, when and why. Entries can be added but never changed or deleted." />
      <div className="space-y-4">
        <Section>
          <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <FilterField label="Actor">
              <NativeSelect
                aria-label="Actor"
                placeholder="Anyone"
                value={filters.actor_user_id ?? ""}
                options={(staff.data?.data ?? []).map((u) => ({ value: u.user_id, label: u.full_name }))}
                onChange={(e) => set({ actor_user_id: e.target.value })}
              />
            </FilterField>
            <FilterField label="Entity">
              <NativeSelect
                aria-label="Entity"
                placeholder="All entities"
                value={filters.entity_type ?? ""}
                options={(facets.data?.entity_types ?? []).map((t) => ({ value: t, label: t }))}
                onChange={(e) => set({ entity_type: e.target.value })}
              />
            </FilterField>
            <FilterField label="Action">
              <NativeSelect
                aria-label="Action"
                placeholder="All actions"
                value={filters.action ?? ""}
                options={(facets.data?.actions ?? []).map((a) => ({ value: a, label: a }))}
                onChange={(e) => set({ action: e.target.value })}
              />
            </FilterField>
            <FilterField label="Entity ID">
              <Input aria-label="Entity ID" value={filters.entity_id ?? ""} onChange={(e) => set({ entity_id: e.target.value })} />
            </FilterField>
            <FilterField label="From (IST)">
              <Input aria-label="From date" type="date" value={filters.from ?? ""} onChange={(e) => set({ from: e.target.value })} />
            </FilterField>
            <FilterField label="To (IST)">
              <Input aria-label="To date" type="date" value={filters.to ?? ""} onChange={(e) => set({ to: e.target.value })} />
            </FilterField>
          </div>
          <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No audit entries match.">
            {(page) => (
              <>
                <DataTable
                  caption="Audit log"
                  rows={page.data}
                  getKey={(a) => a.audit_id}
                  cols={[
                    { h: "When", c: (a) => istDateTime(a.occurred_at) },
                    {
                      h: "Actor",
                      c: (a) =>
                        a.actor ? (
                          <>
                            <div className="font-medium">{a.actor.full_name}</div>
                            <div className="text-xs text-muted-foreground">{a.actor.email}</div>
                          </>
                        ) : (
                          <span className="text-muted-foreground">System</span>
                        ),
                    },
                    { h: "Action", c: (a) => <span className="font-mono text-xs">{a.action}</span> },
                    { h: "Entity", c: (a) => `${a.entity_type} ${a.entity_id}` },
                    { h: "Changes", c: (a) => <Changes entry={a} /> },
                    { h: "Reason", c: (a) => a.reason ?? "—" },
                  ]}
                />
                <Pager meta={page.meta} onPage={(p) => setFilters({ ...filters, page: p })} />
              </>
            )}
          </QueryView>
        </Section>
        <Note>Times are shown in IST. Password values, tokens and other secrets are never written to the audit log.</Note>
      </div>
    </>
  );
}
