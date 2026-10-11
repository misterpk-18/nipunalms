/** AI controls: Ask Nipuna ON or OFF for students, staff and everyone. The Super Admin and the Founder can both switch it off and bring it back. */
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Power } from "lucide-react";
import { adminApi, adminKeys, type AiAudience, type AiControl, type AiStatus } from "@/api/admin";
import { list } from "@/api/client";
import { Field, NativeSelect } from "@/components/lms/forms";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { DataTable, PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { fmtDateTime } from "@/features/shared/format";
import { cn } from "@/lib/utils";
import { audienceName, RestoreDialog, SwitchOffDialog } from "./ai-switch-dialogs";
import { FormDialog, Pager } from "./shared";

type Card = { key: string; audience: AiAudience; title: string; state: "On" | "Off"; control: AiControl | null; via: string | null };
type Dialog =
  | { kind: "off"; audience: AiAudience; branch?: { branch_id: number; branch_name: string } }
  | { kind: "restore"; control: AiControl; label: string }
  | { kind: "branch" };

const cardsOf = (status: AiStatus): Card[] => [
  ...status.audiences.map((a) => ({
    key: a.audience,
    audience: a.audience,
    title: a.label,
    state: a.state,
    control: a.control,
    via: a.via_all ? "Off because all AI is off" : null,
  })),
  { key: "All", audience: "All" as const, title: "All AI", state: status.all.state, control: status.all.control, via: null },
];

function StateCard({ card, canSwitch, onOff, onRestore }: { card: Card; canSwitch: boolean; onOff: () => void; onRestore: () => void }) {
  const off = card.state === "Off";
  return (
    <div className={cn("rounded-xl border bg-card p-4 shadow-sm", off && "border-danger/40")} data-ai={card.key}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">{card.title}</h3>
          <p className="text-xs text-muted-foreground">{card.audience === "All" ? "Every assistant, company-wide" : "Company-wide"}</p>
        </div>
        <span
          className={cn("rounded-full px-3 py-1 text-sm font-bold", off ? "bg-danger-soft text-danger" : "bg-success-soft text-success")}
          aria-label={`${card.title} is ${card.state}`}
        >
          {off ? "OFF" : "ON"}
        </span>
      </div>
      {off && card.control && (
        <p className="mt-3 text-sm text-muted-foreground">
          {card.via ?? card.control.reason}
          <span className="block text-xs">
            Switched off by {card.control.disabled_by_name} on {fmtDateTime(card.control.disabled_at)}
            {card.via ? `: ${card.control.reason}` : ""}
          </span>
        </p>
      )}
      <div className="mt-3">
        {!canSwitch ? null : off ? (
          card.control && !card.via ? (
            <Button size="sm" onClick={onRestore}>
              <Power className="size-3.5" aria-hidden /> Switch back on
            </Button>
          ) : (
            <p className="text-xs text-muted-foreground">Switch All AI back on to bring this one back.</p>
          )
        ) : (
          <Button size="sm" variant="destructive" onClick={onOff}>
            <Power className="size-3.5" aria-hidden /> Switch off
          </Button>
        )}
      </div>
    </div>
  );
}

function History() {
  const [page, setPage] = useState(1);
  const branches = useQuery({ queryKey: ["reference", "branches"], queryFn: adminApi.branches, staleTime: 5 * 60_000 });
  const query = useQuery({
    queryKey: ["admin", "ai-history", page],
    queryFn: () => list<AiControl>("/ai-controls", { page, per_page: 10 }),
    placeholderData: keepPreviousData,
  });
  const branchName = (id: number | null) => (id === null ? "Company-wide" : (branches.data?.find((b) => b.branch_id === id)?.branch_name ?? `Branch ${id}`));
  return (
    <Section title="History">
      <QueryView query={query} isEmpty={(p) => p.data.length === 0} empty="AI has never been switched off.">
        {(result) => (
          <>
            <DataTable
              caption="AI switch history"
              rows={result.data}
              getKey={(c) => c.control_id}
              cols={[
                { h: "What", c: (c) => audienceName(c.audience).replace(/^./, (x) => x.toUpperCase()) },
                { h: "Where", c: (c) => branchName(c.branch_id) },
                { h: "Why", c: (c) => [c.reason, c.remediation && `Being done: ${c.remediation}`].filter(Boolean).join(" · ") },
                { h: "Switched off", c: (c) => `${c.disabled_by_name}, ${fmtDateTime(c.disabled_at)}` },
                {
                  h: "Now",
                  c: (c) =>
                    c.active ? (
                      <StatusBadge domain="integration" code="Off" />
                    ) : (
                      <span className="text-sm">
                        Back on {fmtDateTime(c.restored_at)} by {c.restored_by_name}
                        {c.restoration_note ? `: ${c.restoration_note}` : ""}
                      </span>
                    ),
                },
              ]}
            />
            <Pager meta={result.meta} onPage={setPage} />
          </>
        )}
      </QueryView>
    </Section>
  );
}

/** "Only one branch": pick the assistant and the branch, then the usual reason dialog. */
function BranchPicker({
  onPick,
  onClose,
}: {
  onPick: (audience: AiAudience, branch: { branch_id: number; branch_name: string }) => void;
  onClose: () => void;
}) {
  const branches = useQuery({ queryKey: ["reference", "branches"], queryFn: adminApi.branches, staleTime: 5 * 60_000 });
  const [audience, setAudience] = useState<AiAudience>("Student");
  const [branchId, setBranchId] = useState("");
  const branch = branches.data?.find((b) => String(b.branch_id) === branchId);
  return (
    <FormDialog
      title="Switch off at one branch"
      description="Only the people at that branch lose it. The rest of the company keeps it."
      submitLabel="Next"
      busy={!branch}
      onClose={onClose}
      onSubmit={() => branch && onPick(audience, { branch_id: branch.branch_id, branch_name: branch.branch_name })}
    >
      <Field label="Which assistant" htmlFor="ai-branch-audience">
        <NativeSelect
          id="ai-branch-audience"
          value={audience}
          onChange={(e) => setAudience(e.target.value as AiAudience)}
          options={[
            { value: "Student", label: "Student assistant" },
            { value: "Staff", label: "Staff assistant" },
          ]}
        />
      </Field>
      <Field label="Which branch" htmlFor="ai-branch">
        <NativeSelect
          id="ai-branch"
          placeholder="Pick a branch"
          value={branchId}
          onChange={(e) => setBranchId(e.target.value)}
          options={(branches.data ?? []).map((b) => ({ value: b.branch_id, label: b.branch_name }))}
        />
      </Field>
    </FormDialog>
  );
}

export function AiControlsPage() {
  const query = useQuery({ queryKey: adminKeys.aiStatus, queryFn: adminApi.aiStatus });
  const [dialog, setDialog] = useState<Dialog | null>(null);
  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHead title="AI controls" description="Switch Ask Nipuna off for students, staff or everyone, and bring it back once it is safe." />
      <QueryView query={query} skeleton="cards">
        {(status) => (
          <>
            <div className="grid gap-4 md:grid-cols-3">
              {cardsOf(status).map((card) => (
                <StateCard
                  key={card.key}
                  card={card}
                  canSwitch={status.can_switch}
                  onOff={() => setDialog({ kind: "off", audience: card.audience })}
                  onRestore={() => card.control && setDialog({ kind: "restore", control: card.control, label: card.title.toLowerCase() })}
                />
              ))}
            </div>
            <Section
              title="Only at one branch"
              actions={
                status.can_switch ? (
                  <Button size="sm" variant="outline" onClick={() => setDialog({ kind: "branch" })}>
                    Switch off at a branch
                  </Button>
                ) : undefined
              }
            >
              {status.branches.length === 0 ? (
                <p className="text-sm text-muted-foreground">No branch has its own switch. Everything above applies to every branch.</p>
              ) : (
                <ul className="divide-y">
                  {status.branches.map((c) => (
                    <li key={c.control_id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                      <div className="text-sm">
                        <span className="font-medium">{audienceName(c.audience).replace(/^./, (x) => x.toUpperCase())}</span> is off at{" "}
                        <BranchName id={c.branch_id} />
                        <span className="block text-xs text-muted-foreground">
                          {c.reason} · {c.disabled_by_name}, {fmtDateTime(c.disabled_at)}
                        </span>
                      </div>
                      {status.can_switch && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setDialog({ kind: "restore", control: c, label: `${audienceName(c.audience)} at this branch` })}
                        >
                          Switch back on
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          </>
        )}
      </QueryView>
      <History />
      <HowThisWorks>
        <p>Switching AI off takes effect straight away. People it covers see that Ask Nipuna is unavailable; nothing else in the LMS changes.</p>
        <p>The Super Admin and the Founder can each switch it off and bring it back. Every switch is written to the audit log with the reason.</p>
        <p>Switching all AI off is company-wide, so it asks you to type a confirmation first.</p>
      </HowThisWorks>
      {dialog?.kind === "off" && (
        <SwitchOffDialog audience={dialog.audience} {...(dialog.branch ? { branch: dialog.branch } : {})} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === "restore" && <RestoreDialog control={dialog.control} label={dialog.label} onClose={() => setDialog(null)} />}
      {dialog?.kind === "branch" && (
        <BranchPicker onClose={() => setDialog(null)} onPick={(audience, branch) => setDialog({ kind: "off", audience, branch })} />
      )}
    </div>
  );
}

function BranchName({ id }: { id: number | null }) {
  const branches = useQuery({ queryKey: ["reference", "branches"], queryFn: adminApi.branches, staleTime: 5 * 60_000 });
  return <span className="font-medium">{id === null ? "every branch" : (branches.data?.find((b) => b.branch_id === id)?.branch_name ?? `branch ${id}`)}</span>;
}
