import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { CalendarPlus, RefreshCw, ScrollText, UserPlus } from "lucide-react";
import { adminApi, adminKeys, type NeedsAction } from "@/api/admin";
import { GettingStartedCard } from "@/components/lms/getting-started";
import { NeedsYouList, type NeedsYouItem } from "@/components/lms/needs-you-list";
import { PageHead, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { useApiMutation } from "@/lib/mutation";
import { ageText } from "@/features/shared/format";

/** Retry on a failed CRM update, right from the home: it either goes through or says why not. */
function RetryButton({ eventId }: { eventId: number }) {
  const retry = useApiMutation((id: number) => adminApi.retryEvent(id), {
    success: "The CRM update went through",
    invalidate: [[...adminKeys.needsAction], [...adminKeys.syncAll]],
  });
  return (
    <Button size="sm" disabled={retry.isPending} onClick={() => retry.mutate(eventId)}>
      <RefreshCw className="size-3.5" aria-hidden /> Retry
    </Button>
  );
}

function toItems(data: NeedsAction, canRetry: boolean): NeedsYouItem[] {
  return data.rows.map((row) => ({
    id: row.key,
    what: row.what,
    where: row.where,
    age: row.age_days === null ? undefined : row.age_days === 0 ? "today" : `waiting ${ageText(row.age_days)}`,
    to: row.to,
    search: row.search,
    action: row.action,
    ...(row.retry && canRetry ? { extra: <RetryButton eventId={row.retry.crm_event_id} /> } : {}),
  }));
}

/** The Setup checklist: what is not Working yet. It disappears when everything is. */
function SetupChecklist({ data }: { data: NeedsAction["setup"] }) {
  if (data.done) return null;
  const working = data.total - data.open;
  return (
    <section aria-label="Setup checklist" className="rounded-xl border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Setup checklist</h2>
          <p className="text-xs text-muted-foreground">
            {working} of {data.total} are working. The rest need setting up or checking before go-live.
          </p>
        </div>
        <Button asChild size="sm">
          <Link to="/admin/setup">Open Setup &amp; health</Link>
        </Button>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuemin={0} aria-valuemax={data.total} aria-valuenow={working}>
        <div className="h-full bg-primary" style={{ width: `${(working / Math.max(data.total, 1)) * 100}%` }} />
      </div>
      <ul className="mt-3 divide-y">
        {data.items.slice(0, 6).map((item) => (
          <li key={item.key} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
            <span className="min-w-0 truncate">
              {item.name} <span className="text-xs text-muted-foreground">· {item.owner}</span>
            </span>
            <StatusBadge domain="setup" code={item.state} />
          </li>
        ))}
      </ul>
      {data.items.length > 6 && <p className="mt-2 text-xs text-muted-foreground">and {data.items.length - 6} more on Setup &amp; health.</p>}
    </section>
  );
}

const QUICK = [
  { to: "/admin/users", search: { add: "1" }, label: "Add staff user", icon: UserPlus },
  { to: "/admin/students", search: { attention: "true" }, label: "Student accounts needing attention", icon: RefreshCw },
  { to: "/admin/calendar", search: { add: "1" }, label: "Add holiday or closure", icon: CalendarPlus },
  { to: "/admin/audit", search: {}, label: "See what changed lately", icon: ScrollText },
] as const;

export function AdminDashboard({ canEdit }: { canEdit: boolean }) {
  const query = useQuery({ queryKey: adminKeys.needsAction, queryFn: adminApi.needsAction, refetchInterval: 60_000 });
  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHead title="Super Admin home" description="See what needs doing across the LMS and jump straight to it." />
      <GettingStartedCard />
      <QueryView query={query} skeleton="cards">
        {(data) => (
          <>
            <NeedsYouList
              title="Needs action"
              items={toItems(data, canEdit)}
              empty="Nothing needs you right now. Failed CRM updates, unowned issues and locked accounts will show up here."
            />
            <SetupChecklist data={data.setup} />
          </>
        )}
      </QueryView>
      {canEdit && (
        <section aria-label="Quick actions" className="rounded-xl border bg-card p-4 shadow-sm sm:p-5">
          <h2 className="mb-3 text-base font-semibold">Quick actions</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            {QUICK.map(({ to, search, label, icon: Icon }) => (
              <Button key={label} asChild variant="outline" className="h-auto justify-start py-2.5">
                <Link to={to} search={search as never}>
                  <Icon className="size-4" aria-hidden /> {label}
                </Link>
              </Button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
