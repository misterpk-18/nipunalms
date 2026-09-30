import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminApi, adminKeys, type SecurityControl } from "@/api/admin";
import { Note, PageHead, QueryView, Section } from "@/components/lms/ui";
import { ReadinessDialog, ReadinessTable, type ReadinessRow } from "./readiness-table";
import { useCanAdminister } from "./format";

function toRow(c: SecurityControl): ReadinessRow {
  return {
    key: c.control_code,
    item: c.title,
    group: c.category,
    requirement: c.requirement,
    configuration_status: c.configuration_status,
    verification_status: c.verification_status,
    owner: c.owner,
    evidence: c.evidence,
    notes: c.notes,
    verified_at: c.verified_at,
    last_checked_at: c.last_checked_at,
  };
}

/** Security Readiness: each security requirement with configuration status, verification and evidence. */
export function AdminSecurity() {
  const query = useQuery({ queryKey: adminKeys.controls, queryFn: adminApi.controls });
  const canEdit = useCanAdminister();
  const [editing, setEditing] = useState<SecurityControl | null>(null);

  return (
    <>
      <PageHead title="Security Readiness" description="Security and access requirements with configuration and verification status." />
      <div className="space-y-4">
        <Section>
          <QueryView query={query} isEmpty={(rows) => rows.length === 0}>
            {(rows) => (
              <>
                <ReadinessTable
                  caption="Security requirements"
                  rows={rows.map(toRow)}
                  {...(canEdit ? { onEdit: (row: ReadinessRow) => setEditing(rows.find((c) => c.control_code === row.key) ?? null) } : {})}
                />
                {editing && (
                  <ReadinessDialog
                    row={toRow(editing)}
                    save={(body) => adminApi.updateControl(editing.control_id, body)}
                    invalidate={[adminKeys.controls]}
                    onClose={() => setEditing(null)}
                  />
                )}
              </>
            )}
          </QueryView>
        </Section>
        <Note>
          These are functional requirements until they are implemented and tested. The frontend workspace switcher is a UAT aid, not a security boundary: every
          endpoint enforces role, branch and record scope on the server. No WCAG conformance is claimed.
        </Note>
      </div>
    </>
  );
}
