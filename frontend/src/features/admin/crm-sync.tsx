/** CRM sync: what the CRM sent that did not go through (first, with the reason and Retry), every update, and what the LMS sends back. */
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { adminApi, adminKeys, CRM_EVENT_STATUSES, OUTBOX_STATUSES, type CrmEvent, type EventFilters, type OutboxFilters } from "@/api/admin";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/lms/forms";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { DataTable, Grid, KeyValue, PageHead, PillTabs, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { EmptyState } from "@/components/lms/empty-state";
import { useApiMutation } from "@/lib/mutation";
import { FilterField, Pager } from "@/features/shared/form-parts";
import { istDateTime } from "./format";
import { pageOf, useUrlParams } from "@/features/shared/url-params";

const TABS = ["Needs attention", "All updates", "Sent to the CRM"] as const;
type Tab = (typeof TABS)[number];
const TAB_KEYS: Record<Tab, string> = { "Needs attention": "attention", "All updates": "all", "Sent to the CRM": "sent" };

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

/** Retry one failed update. It says whether it went through; if not, the reason stays on the row. */
function useRetry() {
  return useApiMutation((id: number) => adminApi.retryEvent(id), {
    success: "The CRM update went through",
    invalidate: [[...adminKeys.syncAll], [...adminKeys.needsAction], ["nav", "counts"]],
  });
}

/** `canEdit` (Retry) comes from the route; Super Admin and Founder both retry. */
export function AdminCrmSync({ canEdit }: { canEdit: boolean }) {
  const summary = useQuery({ queryKey: adminKeys.syncSummary, queryFn: adminApi.syncSummary });
  const [params, setParams] = useUrlParams();
  const tab = TABS.find((t) => TAB_KEYS[t] === params["tab"]) ?? TABS[0];
  const openId = params["event"] ? Number(params["event"]) : null;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead
        title="CRM sync"
        description="See what the CRM sent that did not go through, retry it once the cause is fixed, and check what is waiting to go back. Admissions and finance stay in the CRM."
      />
      <QueryView query={summary} skeleton="cards">
        {(s) => (
          <Grid cols={4}>
            <Counter label="Need attention" value={s.needs_attention} {...(s.needs_attention > 0 ? { tone: "danger" as const } : {})} />
            <Counter label="Applied" value={s.events["Applied"] ?? 0} />
            <Counter label="Waiting to go to the CRM" value={s.pending_outbox} {...(s.pending_outbox > 0 ? { tone: "warning" as const } : {})} />
            <Counter label="Last update received" value={istDateTime(s.last_event_received_at)} />
          </Grid>
        )}
      </QueryView>
      <Section>
        <PillTabs
          tabs={TABS}
          value={tab}
          onChange={(t) => setParams({ tab: TAB_KEYS[t] === "attention" ? undefined : TAB_KEYS[t], page: undefined })}
          label="CRM sync"
          counts={{ "Needs attention": summary.data?.needs_attention ?? 0 }}
        />
        {tab === "Needs attention" && <Attention canEdit={canEdit} params={params} setParams={setParams} />}
        {tab === "All updates" && <AllUpdates canEdit={canEdit} />}
        {tab === "Sent to the CRM" && <SentValues />}
      </Section>
      <HowThisWorks>
        <p>
          A failed update keeps its reason. Most often the CRM sent something that refers to a course or branch the LMS had not received yet: press Retry once
          that has arrived.
        </p>
        <p>Retry tries the same update again. If it fails again the reason is updated on the row; the technical details hold what the CRM sent.</p>
        <p>Values going back to the CRM are not sent by the LMS yet: they wait there and the CRM collects them.</p>
      </HowThisWorks>
      {openId !== null && <EventDialog canEdit={canEdit} id={openId} onClose={() => setParams({ event: undefined })} />}
    </div>
  );
}

function EventRow({ event, canRetry, onOpen }: { event: CrmEvent; canRetry: boolean; onOpen: () => void }) {
  const retry = useRetry();
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 py-3" data-event={event.event_id}>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">{event.summary}</h3>
          <StatusBadge domain="crmEvent" code={event.status} />
        </div>
        <p className="text-sm text-muted-foreground">
          {event.plain_cause ?? (event.status === "Received" ? "The LMS received it but did not finish applying it." : "Nothing is wrong with this one.")}
        </p>
        <p className="text-xs text-muted-foreground">
          Received {istDateTime(event.received_at)}
          {event.retries > 0 ? ` · tried again ${event.retries} time${event.retries === 1 ? "" : "s"}` : ""}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={onOpen} aria-label={`Details of ${event.summary}`}>
          Details
        </Button>
        {canRetry && event.can_retry && (
          <Button size="sm" disabled={retry.isPending} onClick={() => retry.mutate(event.crm_event_id)} aria-label={`Retry ${event.summary}`}>
            <RefreshCw className="size-3.5" aria-hidden /> Retry
          </Button>
        )}
      </div>
    </li>
  );
}

function Attention({ canEdit, params, setParams }: { canEdit: boolean; params: Record<string, string | undefined>; setParams: (patch: Record<string, string | undefined>) => void }) {
  const page = pageOf(params);
  const query = useQuery({
    queryKey: adminKeys.syncEvents({ attention: "true", page }),
    queryFn: () => adminApi.syncEvents({ attention: "true", page }),
    placeholderData: keepPreviousData,
  });
  return (
    <QueryView
      query={query}
      isEmpty={(p) => p.data.length === 0}
      empty="Nothing needs attention. Every update the CRM sent has been applied."
      emptyAction={
        <Button size="sm" variant="outline" onClick={() => setParams({ tab: "all" })}>
          See all updates
        </Button>
      }
    >
      {(result) => (
        <>
          <ul className="divide-y" aria-label="Updates that need attention">
            {result.data.map((event) => (
              <EventRow key={event.crm_event_id} event={event} canRetry={canEdit} onOpen={() => setParams({ event: String(event.crm_event_id) })} />
            ))}
          </ul>
          <Pager meta={result.meta} onPage={(p) => setParams({ page: String(p) })} />
        </>
      )}
    </QueryView>
  );
}

function AllUpdates({ canEdit }: { canEdit: boolean }) {
  const [, setParams] = useUrlParams();
  const [filters, setFilters] = useState<EventFilters>({});
  const summary = useQuery({ queryKey: adminKeys.syncSummary, queryFn: adminApi.syncSummary });
  const query = useQuery({ queryKey: adminKeys.syncEvents(filters), queryFn: () => adminApi.syncEvents(filters), placeholderData: keepPreviousData });
  const retry = useRetry();
  return (
    <>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <FilterField label="Status">
          <NativeSelect
            aria-label="Update status"
            placeholder="All"
            value={filters.status ?? ""}
            options={CRM_EVENT_STATUSES.map((s) => ({ value: s, label: s }))}
            onChange={(e) => setFilters({ ...filters, status: e.target.value, page: 1 })}
          />
        </FilterField>
        <FilterField label="Kind of update">
          <NativeSelect
            aria-label="Kind of update"
            placeholder="All"
            value={filters.event_type ?? ""}
            options={(summary.data?.event_types ?? []).map((t) => ({ value: t, label: t }))}
            onChange={(e) => setFilters({ ...filters, event_type: e.target.value, page: 1 })}
          />
        </FilterField>
        <FilterField label="Reference contains">
          <Input aria-label="Reference contains" value={filters.q ?? ""} onChange={(e) => setFilters({ ...filters, q: e.target.value, page: 1 })} />
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
            <Input
              aria-label="Received to"
              type="date"
              value={filters.to ?? ""}
              min={filters.from}
              onChange={(e) => setFilters({ ...filters, to: e.target.value, page: 1 })}
            />
          </FilterField>
        </div>
      </div>
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No updates match.">
        {(page) => (
          <>
            <DataTable
              caption="CRM updates"
              rows={page.data}
              getKey={(e) => e.crm_event_id}
              cols={[
                {
                  h: "Update",
                  c: (e) => (
                    <>
                      <div className="font-medium">{e.summary}</div>
                      <div className="text-xs text-muted-foreground">{e.plain_cause ?? ""}</div>
                    </>
                  ),
                },
                { h: "Status", c: (e) => <StatusBadge domain="crmEvent" code={e.status} /> },
                { h: "Received", c: (e) => istDateTime(e.received_at) },
                {
                  h: "Actions",
                  c: (e) => (
                    <div className="flex flex-wrap gap-1.5">
                      <Button variant="outline" size="sm" onClick={() => setParams({ event: String(e.crm_event_id) })} aria-label={`Details of ${e.summary}`}>
                        Details
                      </Button>
                      {canEdit && e.can_retry && e.status === "Failed" && (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={retry.isPending}
                          onClick={() => retry.mutate(e.crm_event_id)}
                          aria-label={`Retry ${e.summary}`}
                        >
                          <RefreshCw className="size-3.5" aria-hidden /> Retry
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
    </>
  );
}

function Json({ value }: { value: unknown }) {
  return <pre className="max-h-64 overflow-auto rounded-lg border bg-muted p-3 text-xs">{JSON.stringify(value, null, 2)}</pre>;
}

/** One update: a plain summary first, then (folded away) exactly what the CRM sent and what the LMS did with it. */
function EventDialog({ canEdit, id, onClose }: { canEdit: boolean; id: number; onClose: () => void }) {
  const query = useQuery({ queryKey: adminKeys.syncEvent(id), queryFn: () => adminApi.syncEvent(id) });
  const retry = useRetry();
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] w-[calc(100vw-1.5rem)] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>CRM update</DialogTitle>
          <DialogDescription>What the CRM sent and what the LMS did with it.</DialogDescription>
        </DialogHeader>
        <QueryView query={query} skeleton="detail">
          {(e: CrmEvent) => (
            <div className="space-y-3">
              <p className="text-sm font-medium">{e.summary}</p>
              <KeyValue
                items={[
                  ["Status", <StatusBadge key="s" domain="crmEvent" code={e.status} />],
                  ["Received", istDateTime(e.received_at)],
                  ["Applied", e.processed_at ? istDateTime(e.processed_at) : "Not yet"],
                  ["Tried again", e.retries === 0 ? "Never" : `${e.retries} time${e.retries === 1 ? "" : "s"}`],
                ]}
              />
              {e.plain_cause && <p className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">{e.plain_cause}</p>}
              {canEdit && e.can_retry && e.status === "Failed" && (
                <Button size="sm" disabled={retry.isPending} onClick={() => retry.mutate(e.crm_event_id, { onSuccess: onClose })}>
                  <RefreshCw className="size-3.5" aria-hidden /> Retry
                </Button>
              )}
              <HowThisWorks title="Technical details">
                <KeyValue
                  items={[
                    ["Kind", e.event_type],
                    [
                      "Reference",
                      <span key="id" className="font-mono">
                        {e.event_id}
                      </span>,
                    ],
                    ["Version", `v${e.source_version}`],
                    ["Occurred", istDateTime(e.occurred_at)],
                  ]}
                />
                {e.error && <p className="break-words font-mono text-xs text-foreground">{e.error}</p>}
                <h3 className="text-sm font-semibold text-foreground">What the CRM sent</h3>
                <Json value={e.payload} />
                {e.result != null && (
                  <>
                    <h3 className="text-sm font-semibold text-foreground">What the LMS did</h3>
                    <Json value={e.result} />
                  </>
                )}
              </HowThisWorks>
            </div>
          )}
        </QueryView>
      </DialogContent>
    </Dialog>
  );
}

function SentValues() {
  const [filters, setFilters] = useState<OutboxFilters>({});
  const summary = useQuery({ queryKey: adminKeys.syncSummary, queryFn: adminApi.syncSummary });
  const query = useQuery({ queryKey: adminKeys.syncOutbox(filters), queryFn: () => adminApi.syncOutbox(filters), placeholderData: keepPreviousData });
  return (
    <>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <FilterField label="Status">
          <NativeSelect
            aria-label="Sent value status"
            placeholder="All"
            value={filters.status ?? ""}
            options={OUTBOX_STATUSES.map((s) => ({ value: s, label: s }))}
            onChange={(e) => setFilters({ ...filters, status: e.target.value, page: 1 })}
          />
        </FilterField>
        <FilterField label="Kind of value">
          <NativeSelect
            aria-label="Sent value type"
            placeholder="All"
            value={filters.event_type ?? ""}
            options={(summary.data?.outbox_event_types ?? []).map((t) => ({ value: t, label: t }))}
            onChange={(e) => setFilters({ ...filters, event_type: e.target.value, page: 1 })}
          />
        </FilterField>
      </div>
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="Nothing is waiting to go to the CRM.">
        {(page) => (
          <>
            <DataTable
              caption="Values sent to the CRM"
              rows={page.data}
              getKey={(r) => r.outbox_id}
              cols={[
                { h: "Value", c: (r) => <div className="font-medium">{r.event_type}</div> },
                { h: "Status", c: (r) => <StatusBadge domain="crmEvent" code={r.status} /> },
                { h: "Tries", c: (r) => r.attempts },
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
