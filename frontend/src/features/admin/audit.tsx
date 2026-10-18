/** Audit log: who did what, in plain sentences, with a link to the person or record. The raw before / after sits under Details. */
import { Fragment, useMemo } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type CentralArea } from "@/features/shared/central-area";
import { Download } from "lucide-react";
import { adminApi, adminKeys, type AuditEntry, type AuditFilters } from "@/api/admin";
import { EmptyState } from "@/components/lms/empty-state";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { NativeSelect } from "@/components/lms/forms";
import { PageHead, QueryView } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { errorMessage } from "@/api/client";
import { cn } from "@/lib/utils";
import { istDateTime } from "./format";
import { FilterField, Pager } from "@/features/shared/form-parts";
import { pageOf, useUrlParams, type Params } from "@/features/shared/url-params";

const istDay = (date: Date) => date.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
const lastSevenDays = () => ({ from: istDay(new Date(Date.now() - 6 * 86_400_000)), to: istDay(new Date()) });
const humanise = (action: string) => {
  const text = action.replace(/_/g, " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
};

/** The URL's parameters as the API's filters. */
function filtersOf(p: Params): AuditFilters {
  return {
    ...(p["preset"] ? { preset: p["preset"] } : {}),
    ...(p["actor"] ? { actor_user_id: p["actor"] } : {}),
    ...(p["type"] ? { entity_type: p["type"] } : {}),
    ...(p["id"] ? { entity_id: p["id"] } : {}),
    ...(p["action"] ? { action: p["action"] } : {}),
    ...(p["from"] ? { from: p["from"] } : {}),
    ...(p["to"] ? { to: p["to"] } : {}),
    page: pageOf(p),
  };
}

/** The sentence with the record's name turned into a link when there is a screen for it. */
/** The API names `/admin` and `/branch` screens; a Super Admin or Founder gets the equivalent under their own prefix, or no link when there is none. */
function areaLink(link: NonNullable<AuditEntry["link"]>, base: CentralArea["base"]) {
  if (link.to.startsWith("/admin")) return { ...link, to: `${base}${link.to.slice("/admin".length)}` };
  if (link.to.startsWith("/branch/batches")) return { ...link, to: `${base}${link.to.slice("/branch".length)}` };
  return null;
}

function Sentence({ entry, base }: { entry: AuditEntry; base: CentralArea["base"] }) {
  const { sentence, target } = entry;
  const link = entry.link ? areaLink(entry.link, base) : null;
  if (!target || !link || !sentence.includes(target)) return <>{sentence}</>;
  const at = sentence.indexOf(target);
  return (
    <>
      {sentence.slice(0, at)}
      <Link
        to={link.to}
        {...(link.params ? { params: link.params as never } : {})}
        {...(link.search ? { search: link.search as never } : {})}
        className="font-medium text-primary underline-offset-2 hover:underline"
      >
        {target}
      </Link>
      {sentence.slice(at + target.length)}
    </>
  );
}

function Changes({ entry }: { entry: AuditEntry }) {
  const keys = [...new Set([...Object.keys(entry.old_values ?? {}), ...Object.keys(entry.new_values ?? {})])];
  return (
    <div className="space-y-2 text-xs">
      <p className="text-muted-foreground">
        {humanise(entry.action)} · {entry.entity_type.replace(/_/g, " ")} {entry.entity_id}
        {entry.actor?.email ? ` · ${entry.actor.email}` : ""}
      </p>
      {entry.reason && <p>Reason given: {entry.reason}</p>}
      {keys.length > 0 && (
        <ul className="space-y-0.5">
          {keys.map((key) => (
            <li key={key} className="break-words">
              <span className="font-medium">{key}</span>
              {entry.old_values && key in entry.old_values && <span className="text-muted-foreground"> {JSON.stringify(entry.old_values[key])} →</span>}{" "}
              {entry.new_values && key in entry.new_values ? JSON.stringify(entry.new_values[key]) : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AdminAudit({ area }: { area: CentralArea }) {
  const [params, setParams] = useUrlParams();
  const filters = filtersOf(params);
  const facets = useQuery({ queryKey: adminKeys.auditFacets, queryFn: adminApi.auditFacets, staleTime: 60_000 });
  const query = useQuery({ queryKey: adminKeys.audit(filters), queryFn: () => adminApi.audit(filters), placeholderData: keepPreviousData });
  const recent = lastSevenDays();
  const isRecent = params["from"] === recent.from && params["to"] === recent.to;
  const advanced = !!(params["actor"] || params["type"] || params["id"] || params["action"]);
  const filtered = !!(params["preset"] || params["from"] || params["to"] || advanced);
  const actions = useMemo(() => (facets.data?.actions ?? []).map((a) => ({ value: a, label: humanise(a) })), [facets.data]);

  const download = async () => {
    try {
      await adminApi.exportAudit(filters);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const set = (patch: Params) => setParams({ ...patch, page: undefined });

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead
        title="Audit log"
        description="Who changed what and when, in plain words. Entries are added but never changed or removed."
        actions={
          <Button variant="outline" onClick={() => void download()}>
            <Download className="size-4" aria-hidden /> Download CSV
          </Button>
        }
      />
      <div className="flex flex-wrap gap-2" role="group" aria-label="Quick filters">
        {[{ key: undefined, label: "Everything" }, ...(facets.data?.presets ?? []).map((p) => ({ key: p.key as string | undefined, label: p.label }))].map(
          (chip) => (
            <button
              key={chip.label}
              type="button"
              aria-pressed={params["preset"] === chip.key}
              onClick={() => set({ preset: chip.key })}
              className={cn(
                "tap rounded-full border px-3.5 py-1.5 text-sm font-medium",
                params["preset"] === chip.key ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-accent",
              )}
            >
              {chip.label}
            </button>
          ),
        )}
        <span className="mx-1 hidden w-px bg-border sm:block" aria-hidden />
        <button
          type="button"
          aria-pressed={isRecent}
          onClick={() => set(isRecent ? { from: undefined, to: undefined } : recent)}
          className={cn(
            "tap rounded-full border px-3.5 py-1.5 text-sm font-medium",
            isRecent ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-accent",
          )}
        >
          Last 7 days
        </button>
      </div>
      <details className="rounded-xl border bg-card p-4 shadow-sm" open={advanced}>
        <summary className="cursor-pointer text-sm font-medium">More filters</summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <FilterField label="Who did it">
            <NativeSelect
              aria-label="Who did it"
              placeholder="Anyone"
              value={params["actor"] ?? ""}
              options={(facets.data?.actors ?? []).map((a) => ({ value: a.user_id, label: a.full_name }))}
              onChange={(e) => set({ actor: e.target.value })}
            />
          </FilterField>
          <FilterField label="Kind of record">
            <NativeSelect
              aria-label="Kind of record"
              placeholder="All"
              value={params["type"] ?? ""}
              options={(facets.data?.entity_types ?? []).map((t) => ({ value: t, label: humanise(t) }))}
              onChange={(e) => set({ type: e.target.value })}
            />
          </FilterField>
          <FilterField label="What was done">
            <NativeSelect
              aria-label="What was done"
              placeholder="Anything"
              value={params["action"] ?? ""}
              options={actions}
              onChange={(e) => set({ action: e.target.value })}
            />
          </FilterField>
          <FilterField label="Record number">
            <Input aria-label="Record number" value={params["id"] ?? ""} onChange={(e) => set({ id: e.target.value })} />
          </FilterField>
          <FilterField label="From (IST)">
            <Input aria-label="From date" type="date" value={params["from"] ?? ""} max={params["to"]} onChange={(e) => set({ from: e.target.value })} />
          </FilterField>
          <FilterField label="To (IST)">
            <Input aria-label="To date" type="date" value={params["to"] ?? ""} min={params["from"]} onChange={(e) => set({ to: e.target.value })} />
          </FilterField>
        </div>
      </details>
      <QueryView
        query={query}
        isEmpty={(page) => page.data.length === 0}
        empty="Nothing matches these filters."
        emptyAction={
          filtered ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                setParams({
                  preset: undefined,
                  actor: undefined,
                  type: undefined,
                  id: undefined,
                  action: undefined,
                  from: undefined,
                  to: undefined,
                  page: undefined,
                })
              }
            >
              Clear filters
            </Button>
          ) : undefined
        }
      >
        {(page) => (
          <>
            <ul className="divide-y rounded-xl border bg-card shadow-sm" aria-label="Audit entries">
              {page.data.map((entry) => (
                <li key={entry.audit_id} className="px-4 py-3" data-audit={entry.audit_id}>
                  <p className="text-sm">
                    <Sentence entry={entry} base={area.base} />
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {istDateTime(entry.occurred_at)}
                    {entry.reason ? ` · ${entry.reason}` : ""}
                  </p>
                  <details className="mt-1">
                    <summary className="cursor-pointer text-xs text-primary">Details</summary>
                    <div className="mt-1.5 rounded-lg border bg-muted/40 p-2.5">
                      <Changes entry={entry} />
                    </div>
                  </details>
                </li>
              ))}
            </ul>
            <Pager meta={page.meta} onPage={(p) => setParams({ page: String(p) })} />
          </>
        )}
      </QueryView>
      <HowThisWorks>
        <p>Times are in IST. Passwords, tokens and other secrets are never written to the audit log.</p>
        <p>Download CSV saves what you are looking at (up to 5,000 entries, newest first) in a file Excel opens.</p>
      </HowThisWorks>
    </div>
  );
}
