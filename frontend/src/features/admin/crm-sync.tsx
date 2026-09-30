import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { adminApi, adminKeys, CRM_EVENT_STATUSES, OUTBOX_STATUSES, type CrmEvent, type CrmOutboxRow, type EventFilters, type OutboxFilters } from "@/api/admin";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, Grid, KeyValue, Note, PageHead, PillTabs, QueryView, Section, StatusBadge, type Tone } from "@/components/lms/ui";
import { useApiMutation } from "@/lib/mutation";
import { FilterField, Pager } from "./shared";
import { istDateTime, useCanAdminister } from "./format";

const EVENT_TONE: Record<CrmEvent["status"], Tone> = { Received: "info", Applied: "success", "Ignored — stale": "neutral", Failed: "danger" };
const OUTBOX_TONE: Record<CrmOutboxRow["status"], Tone> = { Pending: "warning", Delivered: "success", Failed: "danger" };

const TABS = ["Inbox (events from the CRM)", "Outbox (values for the CRM)"] as const;

function Counter({ label, value, tone }: { label: string; value: number | string; tone?: "danger" | "warning" }) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={
          tone === "danger" ? "text-2xl font-semibold text-danger" : tone === "warning" ? "text-2xl font-semibold text-warning" : "text-2xl font-semibold"
        }
      >
        {value}
      </div>
    </div>
  );
}

/** CRM Sync: the inbox of events the CRM posted (with retry of failed ones) and the outbox of values queued for the CRM. */
export function AdminCrmSync() {
  const summary = useQuery({ queryKey: adminKeys.syncSummary, queryFn: adminApi.syncSummary });
  const [tab, setTab] = useState<(typeof TABS)[number]>(TABS[0]);

  return (
    <>
      <PageHead title="CRM Sync" description="Events received from the CRM and values queued for it. The CRM stays authoritative for admissions and finance." />
      <div className="space-y-4">
        <QueryView query={summary}>
          {(s) => (
            <Grid cols={4}>
              <Counter label="Failed events" value={s.failed_events} {...(s.failed_events > 0 ? { tone: "danger" as const } : {})} />
              <Counter label="Applied events" value={s.events["Applied"] ?? 0} />
              <Counter label="Pending outbox" value={s.pending_outbox} {...(s.pending_outbox > 0 ? { tone: "warning" as const } : {})} />
              <Counter label="Last event received" value={istDateTime(s.last_event_received_at)} />
            </Grid>
          )}
        </QueryView>
        <Section>
          <PillTabs tabs={TABS} value={tab} onChange={setTab} label="CRM sync" />
          {tab === TABS[0] ? <Inbox /> : <Outbox />}
        </Section>
        <Note>
          Failed events keep their error and can be retried once the cause (for example a course that had not arrived yet) is fixed. Outbox delivery to the CRM
          is not connected yet: rows stay Pending and the CRM can pull them.
        </Note>
      </div>
    </>
  );
}

function Inbox() {
  const canEdit = useCanAdminister();
  const [filters, setFilters] = useState<EventFilters>({});
  const [openId, setOpenId] = useState<number | null>(null);
  const summary = useQuery({ queryKey: adminKeys.syncSummary, queryFn: adminApi.syncSummary });
  const query = useQuery({ queryKey: adminKeys.syncEvents(filters), queryFn: () => adminApi.syncEvents(filters) });
  const retry = useApiMutation((id: number) => adminApi.retryEvent(id), {
    success: (e) => `Event ${e.event_id} applied`,
    invalidate: [[...adminKeys.syncAll]],
  });

  return (
    <>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <FilterField label="Status">
          <NativeSelect
            aria-label="Event status"
            placeholder="All"
            value={filters.status ?? ""}
            options={CRM_EVENT_STATUSES.map((s) => ({ value: s, label: s }))}
            onChange={(e) => setFilters({ ...filters, status: e.target.value, page: 1 })}
          />
        </FilterField>
        <FilterField label="Type">
          <NativeSelect
            aria-label="Event type"
            placeholder="All"
            value={filters.event_type ?? ""}
            options={(summary.data?.event_types ?? []).map((t) => ({ value: t, label: t }))}
            onChange={(e) => setFilters({ ...filters, event_type: e.target.value, page: 1 })}
          />
        </FilterField>
        <FilterField label="Event ID contains">
          <Input aria-label="Event ID contains" value={filters.q ?? ""} onChange={(e) => setFilters({ ...filters, q: e.target.value, page: 1 })} />
        </FilterField>
        <div className="grid grid-cols-2 gap-2">
          <FilterField label="Received from">
            <Input
              aria-label="Received from"
              type="date"
              value={filters.from ?? ""}
              onChange={(e) => setFilters({ ...filters, from: e.target.value, page: 1 })}
            />
          </FilterField>
          <FilterField label="To">
            <Input aria-label="Received to" type="date" value={filters.to ?? ""} onChange={(e) => setFilters({ ...filters, to: e.target.value, page: 1 })} />
          </FilterField>
        </div>
      </div>
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No events match.">
        {(page) => (
          <>
            <DataTable
              caption="CRM events"
              rows={page.data}
              getKey={(e) => e.crm_event_id}
              cols={[
                {
                  h: "Event",
                  c: (e) => (
                    <>
                      <div className="font-medium">{e.event_type}</div>
                      <div className="font-mono text-xs text-muted-foreground">{e.event_id}</div>
                    </>
                  ),
                },
                { h: "Version", c: (e) => `v${e.source_version}` },
                { h: "Status", c: (e) => <StatusBadge tone={EVENT_TONE[e.status]}>{e.status}</StatusBadge> },
                {
                  h: "Result",
                  c: (e) =>
                    e.error ? (
                      <span className="text-xs text-danger">{e.error}</span>
                    ) : (
                      <span className="text-xs text-muted-foreground">{e.retries > 0 ? `${e.retries} retr${e.retries === 1 ? "y" : "ies"}` : "—"}</span>
                    ),
                },
                { h: "Received", c: (e) => istDateTime(e.received_at) },
                {
                  h: "Actions",
                  c: (e) => (
                    <div className="flex flex-wrap gap-1.5">
                      <Button variant="outline" size="sm" onClick={() => setOpenId(e.crm_event_id)} aria-label={`View ${e.event_id}`}>
                        View
                      </Button>
                      {canEdit && e.status === "Failed" && (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={retry.isPending}
                          onClick={() => retry.mutate(e.crm_event_id)}
                          aria-label={`Retry ${e.event_id}`}
                        >
                          <RefreshCw className="size-3.5" /> Retry
                        </Button>
                      )}
                    </div>
                  ),
                },
              ]}
            />
            <Pager meta={page.meta} onPage={(p) => setFilters({ ...filters, page: p })} />
          </>
        )}
      </QueryView>
      {openId !== null && <EventDialog id={openId} onClose={() => setOpenId(null)} />}
    </>
  );
}

function Json({ value }: { value: unknown }) {
  return <pre className="max-h-64 overflow-auto rounded-lg border bg-muted p-3 text-xs">{JSON.stringify(value, null, 2)}</pre>;
}

function EventDialog({ id, onClose }: { id: number; onClose: () => void }) {
  const query = useQuery({ queryKey: adminKeys.syncEvent(id), queryFn: () => adminApi.syncEvent(id) });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] w-[calc(100vw-1.5rem)] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>CRM event</DialogTitle>
          <DialogDescription>The payload exactly as the CRM sent it, and what the LMS did with it.</DialogDescription>
        </DialogHeader>
        <QueryView query={query}>
          {(e: CrmEvent) => (
            <div className="space-y-3">
              <KeyValue
                items={[
                  ["Type", e.event_type],
                  [
                    "Event ID",
                    <span key="id" className="font-mono">
                      {e.event_id}
                    </span>,
                  ],
                  [
                    "Status",
                    <StatusBadge key="s" tone={EVENT_TONE[e.status]}>
                      {e.status}
                    </StatusBadge>,
                  ],
                  ["Source version", `v${e.source_version}`],
                  ["Occurred at", istDateTime(e.occurred_at)],
                  ["Processed at", istDateTime(e.processed_at)],
                ]}
              />
              {e.error && <p className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">{e.error}</p>}
              <h3 className="text-sm font-semibold">Payload</h3>
              <Json value={e.payload} />
              {e.result != null && (
                <>
                  <h3 className="text-sm font-semibold">Result</h3>
                  <Json value={e.result} />
                </>
              )}
            </div>
          )}
        </QueryView>
      </DialogContent>
    </Dialog>
  );
}

function Outbox() {
  const [filters, setFilters] = useState<OutboxFilters>({});
  const summary = useQuery({ queryKey: adminKeys.syncSummary, queryFn: adminApi.syncSummary });
  const query = useQuery({ queryKey: adminKeys.syncOutbox(filters), queryFn: () => adminApi.syncOutbox(filters) });
  return (
    <>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <FilterField label="Status">
          <NativeSelect
            aria-label="Outbox status"
            placeholder="All"
            value={filters.status ?? ""}
            options={OUTBOX_STATUSES.map((s) => ({ value: s, label: s }))}
            onChange={(e) => setFilters({ ...filters, status: e.target.value, page: 1 })}
          />
        </FilterField>
        <FilterField label="Type">
          <NativeSelect
            aria-label="Outbox type"
            placeholder="All"
            value={filters.event_type ?? ""}
            options={(summary.data?.outbox_event_types ?? []).map((t) => ({ value: t, label: t }))}
            onChange={(e) => setFilters({ ...filters, event_type: e.target.value, page: 1 })}
          />
        </FilterField>
      </div>
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="The outbox is empty.">
        {(page) => (
          <>
            <DataTable
              caption="CRM outbox"
              rows={page.data}
              getKey={(r) => r.outbox_id}
              cols={[
                { h: "Value", c: (r) => <div className="font-medium">{r.event_type}</div> },
                { h: "Payload", c: (r) => <code className="break-all text-xs">{JSON.stringify(r.payload)}</code> },
                { h: "Status", c: (r) => <StatusBadge tone={OUTBOX_TONE[r.status]}>{r.status}</StatusBadge> },
                { h: "Attempts", c: (r) => r.attempts },
                { h: "Queued", c: (r) => istDateTime(r.created_at) },
                { h: "Delivered", c: (r) => istDateTime(r.delivered_at) },
              ]}
            />
            <Pager meta={page.meta} onPage={(p) => setFilters({ ...filters, page: p })} />
          </>
        )}
      </QueryView>
    </>
  );
}
