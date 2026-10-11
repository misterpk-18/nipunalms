/** Issues: one inbox for everything wrong or stuck. Filters live in the address; "Go fix it" opens the screen that fixes it. */
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { ChevronDown } from "lucide-react";
import { issuesApi, type Issue, type IssueType } from "@/api/issues";
import { useActing } from "@/auth/acting";
import { NativeSelect } from "@/components/lms/forms";
import { EmptyState } from "@/components/lms/empty-state";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, QueryView, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { fmtDate, ageText } from "@/features/shared/format";
import { ReasonDialog } from "@/features/shared/reason-dialog";
import { useApiMutation } from "@/lib/mutation";
import { cn } from "@/lib/utils";
import { AssignDialog } from "@/features/admin/issue-assign";
import { BranchPicker } from "./my-work";

const PER_PAGE = 20;

const TYPE_CHIPS: { key: IssueType | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "students", label: "Students" },
  { key: "classes", label: "Classes" },
  { key: "recordings", label: "Recordings" },
  { key: "support", label: "Student support" },
  { key: "results", label: "Marks and results" },
  { key: "access", label: "Access extensions" },
  { key: "system", label: "Sync and setup" },
];

const AGES = [
  { value: "today", label: "Opened today" },
  { value: "over_2", label: "Older than 2 days" },
  { value: "over_7", label: "Older than 7 days" },
  { value: "over_30", label: "Older than 30 days" },
];
const OWNERS = [
  { value: "me", label: "Mine" },
  { value: "none", label: "Nobody yet" },
];

type Params = { type?: string; age?: string; owner?: string; page?: number };

/** The filters and the page number, kept in the address so a refresh or a shared link shows the same list. */
function useIssueParams() {
  const raw = useSearch({ strict: false }) as Record<string, unknown>;
  const navigate = useNavigate();
  const str = (v: unknown, allowed: readonly string[]) => (typeof v === "string" && allowed.includes(v) ? v : undefined);
  const params: Params = {
    ...(str(
      raw["type"],
      TYPE_CHIPS.map((c) => c.key),
    ) && raw["type"] !== "all"
      ? { type: raw["type"] as string }
      : {}),
    ...(str(
      raw["age"],
      AGES.map((a) => a.value),
    )
      ? { age: raw["age"] as string }
      : {}),
    ...(str(
      raw["owner"],
      OWNERS.map((o) => o.value),
    )
      ? { owner: raw["owner"] as string }
      : {}),
    ...(Number(raw["page"]) > 1 ? { page: Number(raw["page"]) } : {}),
  };
  const set = (next: Params) => {
    const merged = { ...raw, ...next } as Record<string, unknown>;
    for (const k of Object.keys(merged)) if (merged[k] === undefined || merged[k] === "" || merged[k] === 1) delete merged[k];
    void navigate({ to: ".", search: (() => merged) as never, replace: true });
  };
  return { params, set };
}

function Notes({ issue }: { issue: Issue }) {
  const notes = useQuery({ queryKey: ["issues", "notes", issue.source, issue.source_id], queryFn: () => issuesApi.notes(issue) });
  return (
    <QueryView query={notes} skeleton="detail" isEmpty={(n) => n.length === 0} empty="No notes yet.">
      {(rows) => (
        <ul className="space-y-2 border-l-2 pl-3">
          {rows.map((n) => (
            <li key={n.step_id} className="text-sm">
              <p className="whitespace-pre-wrap break-words">{n.reason}</p>
              <p className="text-xs text-muted-foreground">
                {n.logged_by.full_name} · {fmtDate(n.logged_at)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </QueryView>
  );
}

function IssueRow({ issue, canNote, canAssign }: { issue: Issue; canNote: boolean; canAssign: boolean }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const note = useApiMutation((text: string) => issuesApi.addNote(issue, text), {
    success: "Note added. You now own this issue.",
    invalidate: [["issues"]],
    onSuccess: () => setOpen(true),
  });
  const fix = () => void navigate({ to: issue.go_fix.to, ...(issue.go_fix.search ? { search: issue.go_fix.search as never } : {}) });
  return (
    <li className="rounded-xl border bg-card p-4 shadow-sm" data-issue={issue.id}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Tag tone="info">{issue.type_label}</Tag>
            {issue.branch && <span className="text-xs text-muted-foreground">{issue.branch.branch_name}</span>}
          </div>
          <h3 className="break-words text-sm font-semibold">{issue.title}</h3>
          {issue.detail && <p className="break-words text-sm text-muted-foreground">{issue.detail}</p>}
          <p className="text-xs text-muted-foreground">
            {issue.owner ? `Owner: ${issue.owner.full_name}` : "Nobody yet"} · {issue.age_days === 0 ? "Opened today" : `Open for ${ageText(issue.age_days)}`}
            {issue.step_count > 0 ? ` · ${issue.step_count} note${issue.step_count === 1 ? "" : "s"}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={fix}>
            Go fix it
          </Button>
          {canAssign && issue.can_assign && (
            <Button size="sm" variant="outline" onClick={() => setAssigning(true)} aria-label={`Assign ${issue.title}`}>
              Assign
            </Button>
          )}
          {canNote && issue.can_note && (
            <ReasonDialog
              trigger={
                <Button size="sm" variant="outline">
                  Add note
                </Button>
              }
              title="Add a note"
              description={`${issue.title}. Say what was done or what happens next. You become the owner of this issue.`}
              label="Note"
              confirmLabel="Add note"
              busy={note.isPending}
              onSubmit={(text) => note.mutateAsync(text)}
            />
          )}
        </div>
      </div>
      {assigning && <AssignDialog issue={issue} onClose={() => setAssigning(false)} />}
      {issue.step_count > 0 && (
        <div className="mt-3">
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
            className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-2 hover:underline"
          >
            Notes ({issue.step_count})
            <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} aria-hidden />
          </button>
          {open && (
            <div className="mt-2">
              <Notes issue={issue} />
            </div>
          )}
        </div>
      )}
    </li>
  );
}

/** The list with its filters and paging. The Super Admin's view reuses it with `canAssign` (hand an issue to someone) and no branch pick. */
export function IssuesList({ canNote = true, canAssign = false, branchScoped = true }: { canNote?: boolean; canAssign?: boolean; branchScoped?: boolean }) {
  const { params, set } = useIssueParams();
  const acting = useActing("branch");
  const branchId = branchScoped ? acting.branchId : null;
  const page = params.page ?? 1;
  const query = useQuery({
    queryKey: ["issues", "list", params, branchId],
    queryFn: () => issuesApi.list({ type: params.type, age: params.age, owner: params.owner, branch_id: branchId, page, per_page: PER_PAGE }),
    placeholderData: keepPreviousData,
  });
  const filtered = !!(params.type || params.age || params.owner);
  const clear = () => set({ type: undefined, age: undefined, owner: undefined, page: undefined });
  return (
    <div className="space-y-4">
      <QueryView query={query} skeleton="table">
        {(result) => {
          const counts = result.meta.counts;
          const active = params.type ?? "all";
          return (
            <>
              <div role="group" aria-label="Kind of issue" className="flex flex-wrap gap-2">
                {TYPE_CHIPS.filter((c) => c.key === "all" || c.key === active || (counts?.[c.key] ?? 0) > 0).map((c) => (
                  <button
                    key={c.key}
                    type="button"
                    aria-pressed={active === c.key}
                    onClick={() => set({ type: c.key === "all" ? undefined : c.key, page: undefined })}
                    className={cn(
                      "tap rounded-full border px-3.5 py-1.5 text-sm font-medium",
                      active === c.key ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-accent",
                    )}
                  >
                    {c.label}
                    <span className={cn("ml-2 rounded-full px-1.5 text-xs", active === c.key ? "bg-primary-foreground/20" : "bg-primary/10 text-primary")}>
                      {counts?.[c.key] ?? 0}
                    </span>
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap gap-3">
                <div className="w-full sm:w-56">
                  <NativeSelect
                    aria-label="Age"
                    placeholder="Any age"
                    options={AGES}
                    value={params.age ?? ""}
                    onChange={(e) => set({ age: e.target.value || undefined, page: undefined })}
                  />
                </div>
                <div className="w-full sm:w-56">
                  <NativeSelect
                    aria-label="Owner"
                    placeholder="Anyone"
                    options={OWNERS}
                    value={params.owner ?? ""}
                    onChange={(e) => set({ owner: e.target.value || undefined, page: undefined })}
                  />
                </div>
                {filtered && (
                  <Button variant="ghost" onClick={clear}>
                    Clear filters
                  </Button>
                )}
              </div>
              {result.data.length === 0 ? (
                <EmptyState
                  reason={
                    filtered
                      ? "Nothing matches these filters. Nothing is wrong here, or the filters are too narrow."
                      : "Nothing is wrong right now. Problems with students, classes, recordings, support and marks appear here as they happen."
                  }
                  action={
                    filtered ? (
                      <Button size="sm" variant="outline" onClick={clear}>
                        Clear filters
                      </Button>
                    ) : undefined
                  }
                />
              ) : (
                <ul className="space-y-3" aria-label="Issues">
                  {result.data.map((issue) => (
                    <IssueRow key={issue.id} issue={issue} canNote={canNote} canAssign={canAssign} />
                  ))}
                </ul>
              )}
              {result.meta.total > 0 && (
                <nav aria-label="Pages" className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm text-muted-foreground">
                    {result.meta.total} issue{result.meta.total === 1 ? "" : "s"} · Page {result.meta.page} of {Math.max(result.meta.pages, 1)}
                  </p>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" disabled={result.meta.page <= 1} onClick={() => set({ page: result.meta.page - 1 })}>
                      Previous
                    </Button>
                    <Button variant="outline" size="sm" disabled={result.meta.page >= result.meta.pages} onClick={() => set({ page: result.meta.page + 1 })}>
                      Next
                    </Button>
                  </div>
                </nav>
              )}
            </>
          );
        }}
      </QueryView>
    </div>
  );
}

export function BranchIssues() {
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead
        title="Issues"
        description="Everything that is wrong or stuck, in one list. Press Go fix it to open the screen that solves it."
        actions={<BranchPicker />}
      />
      <IssuesList />
      <HowThisWorks>
        <p>An issue stays here until what caused it is fixed; it then leaves the list by itself.</p>
        <p>Add note records what you did or will do. The person who adds a note becomes the owner, so nobody else has to chase it.</p>
      </HowThisWorks>
    </div>
  );
}
