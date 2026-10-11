/** Setup & health: every connection and security setting in one checklist, with a plain state and an owner. */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { adminApi, adminKeys, SETUP_STATES, type SetupItem, type SetupState } from "@/api/admin";
import { EmptyState } from "@/components/lms/empty-state";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { istDateTime, useCanAdminister } from "./format";
import { MeetHealth } from "./meet-health";
import { SetupDialog } from "./setup-dialog";

function Row({ item, canEdit, onEdit }: { item: SetupItem; canEdit: boolean; onEdit: () => void }) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 py-3" data-setup={item.code}>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">{item.name}</h3>
          <StatusBadge domain="setup" code={item.state} />
        </div>
        <p className="text-sm text-muted-foreground">{item.requirement}</p>
        <p className="text-xs text-muted-foreground">
          Owner: {item.owner.full_name ?? <span>no one yet{item.owner.label ? ` (${item.owner.label})` : ""}</span>}
          {item.last_checked_at ? ` · last checked ${istDateTime(item.last_checked_at)}` : " · never checked"}
        </p>
        {item.evidence && <p className="text-xs text-muted-foreground">How it was checked: {item.evidence}</p>}
        {item.notes && <p className="text-xs text-muted-foreground">{item.notes}</p>}
      </div>
      {canEdit && (
        <Button variant="outline" size="sm" onClick={onEdit} aria-label={`Update ${item.name}`}>
          <Pencil className="size-3.5" aria-hidden /> Update
        </Button>
      )}
    </li>
  );
}

export function AdminSetup() {
  const query = useQuery({ queryKey: adminKeys.setup, queryFn: adminApi.setup });
  const canEdit = useCanAdminister();
  const [filter, setFilter] = useState<SetupState | "all">("all");
  const [editing, setEditing] = useState<SetupItem | null>(null);

  const groups = useMemo(() => {
    const shown = (query.data?.items ?? []).filter((i) => filter === "all" || i.state === filter);
    const map = new Map<string, SetupItem[]>();
    for (const item of shown) map.set(item.group, [...(map.get(item.group) ?? []), item]);
    return [...map.entries()];
  }, [query.data, filter]);

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHead title="Setup & health" description="See what is connected and working, who owns each item and what still needs doing before go-live." />
      <QueryView query={query} skeleton="cards">
        {({ summary, help }) => (
          <>
            <div role="group" aria-label="Show" className="flex flex-wrap gap-2">
              {(["all", ...SETUP_STATES] as const).map((key) => {
                const count = key === "all" ? summary.total : summary.counts[key];
                return (
                  <button
                    key={key}
                    type="button"
                    aria-pressed={filter === key}
                    onClick={() => setFilter(key)}
                    className={cn(
                      "tap rounded-full border px-3.5 py-1.5 text-sm font-medium",
                      filter === key ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-accent",
                    )}
                  >
                    {key === "all" ? "All" : key}
                    <span className={cn("ml-2 rounded-full px-1.5 text-xs", filter === key ? "bg-primary-foreground/20" : "bg-primary/10 text-primary")}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
            {groups.length === 0 ? (
              <EmptyState
                reason="Nothing is in this state."
                action={
                  <Button size="sm" variant="outline" onClick={() => setFilter("all")}>
                    Show everything
                  </Button>
                }
              />
            ) : (
              groups.map(([group, items]) => (
                <Section key={group} title={group}>
                  <ul className="divide-y">
                    {items.map((item) => (
                      <Row key={item.key} item={item} canEdit={canEdit} onEdit={() => setEditing(item)} />
                    ))}
                  </ul>
                </Section>
              ))
            )}
            <HowThisWorks>
              {SETUP_STATES.map((state) => (
                <p key={state}>
                  <strong>{state}.</strong> {help[state]}
                </p>
              ))}
              <p>Marking something Working needs a note of how you checked it. A setting is never counted as live on its own say-so.</p>
            </HowThisWorks>
          </>
        )}
      </QueryView>
      <MeetHealth />
      {editing && <SetupDialog item={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
