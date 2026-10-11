/** My work: what needs the Branch Manager today, most pressing first, one button per row. The Branch home leads with it. */
import { useQuery } from "@tanstack/react-query";
import { branchApi, type WorkRow } from "@/api/branch";
import { useActing } from "@/auth/acting";
import { NativeSelect } from "@/components/lms/forms";
import { NeedsYouList, type NeedsYouItem } from "@/components/lms/needs-you-list";
import { QueryView } from "@/components/lms/ui";
import { ageText } from "@/features/shared/format";

const DAY_MS = 86_400_000;

/** How long it has waited ("Oldest waiting 3 days"); support rows carry the earliest reply deadline instead. */
function ageOf(row: WorkRow): string | undefined {
  if (!row.oldest_at) return undefined;
  const ms = Date.now() - new Date(row.oldest_at).getTime();
  if (row.key === "support") {
    const hours = Math.round(Math.abs(ms) / 3_600_000);
    return ms >= 0
      ? `Earliest reply was due ${hours < 1 ? "just now" : `${hours} hour${hours === 1 ? "" : "s"} ago`}`
      : `Earliest reply is due in ${hours} hour${hours === 1 ? "" : "s"}`;
  }
  return `Oldest waiting ${ageText(Math.max(Math.floor(ms / DAY_MS), 0))}`;
}

export const workItems = (rows: WorkRow[]): NeedsYouItem[] =>
  rows.map((r) => ({
    id: r.key,
    what: r.what,
    where: r.where ?? undefined,
    age: ageOf(r),
    to: r.to,
    ...(r.search ? { search: r.search } : {}),
    action: r.action,
  }));

/** The branch pick of the header's "Acting as" menu, repeated on the page for people with more than one branch. */
export function BranchPicker({ label = "Branch" }: { label?: string }) {
  const { branches, canPick, branchId, setBranchId } = useActing("branch");
  if (!canPick) return null;
  return (
    <div className="w-full max-w-xs">
      <NativeSelect
        aria-label={label}
        placeholder="All branches"
        options={branches.map((b) => ({ value: b.branch_id, label: b.branch_name }))}
        value={branchId ?? ""}
        onChange={(e) => setBranchId(e.target.value ? Number(e.target.value) : null)}
      />
    </div>
  );
}

export function MyWork() {
  const { branchId } = useActing("branch");
  const query = useQuery({ queryKey: ["branch", "my-work", branchId], queryFn: () => branchApi.myWork(branchId), refetchInterval: 60_000 });
  return (
    <QueryView query={query} skeleton="cards">
      {(work) => (
        <NeedsYouList
          title="My work today"
          items={workItems(work.rows)}
          empty={`Nothing needs you right now at ${work.scope.label}. New students waiting for a batch, requests and deadlines appear here.`}
        />
      )}
    </QueryView>
  );
}
