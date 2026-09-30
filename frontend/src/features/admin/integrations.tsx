import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminApi, adminKeys, type Integration } from "@/api/admin";
import { Note, PageHead, QueryView, Section } from "@/components/lms/ui";
import { ReadinessDialog, ReadinessTable, type ReadinessRow } from "./readiness-table";
import { useCanAdminister } from "./format";

function toRow(i: Integration): ReadinessRow {
  return {
    key: i.integration_code,
    item: i.integration_name,
    requirement: i.requirement,
    configuration_status: i.configuration_status,
    verification_status: i.verification_status,
    owner: i.owner,
    evidence: i.evidence,
    notes: i.notes,
    verified_at: i.verified_at,
    last_checked_at: i.last_checked_at,
  };
}

/** Integration Readiness: what each connection needs, whether it is configured, and whether it was seen working. */
export function AdminIntegrations() {
  const query = useQuery({ queryKey: adminKeys.integrations, queryFn: adminApi.integrations });
  const canEdit = useCanAdminister();
  const [editing, setEditing] = useState<Integration | null>(null);

  return (
    <>
      <PageHead title="Integration Readiness" description="Requirement, configuration and operational verification per integration." />
      <div className="space-y-4">
        <Section>
          <QueryView query={query} isEmpty={(rows) => rows.length === 0}>
            {(rows) => (
              <>
                <ReadinessTable
                  caption="Integrations"
                  rows={rows.map(toRow)}
                  {...(canEdit ? { onEdit: (row: ReadinessRow) => setEditing(rows.find((i) => i.integration_code === row.key) ?? null) } : {})}
                />
                {editing && (
                  <ReadinessDialog
                    row={toRow(editing)}
                    save={(body) => adminApi.updateIntegration(editing.integration_id, body)}
                    invalidate={[adminKeys.integrations]}
                    onClose={() => setEditing(null)}
                  />
                )}
              </>
            )}
          </QueryView>
        </Section>
        <Note>
          Configuration and operational verification are separate: a connection is Verified only with an evidence note from a successful check. Until then the
          LMS records Pending Verification / Integration Unavailable instead of calling the service — nothing here is Live Verified without evidence.
        </Note>
      </div>
    </>
  );
}
