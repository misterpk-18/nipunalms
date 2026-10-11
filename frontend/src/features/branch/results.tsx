/** Marks & results: what needs your review, what waits on a trainer, and what is published. */
import { useState } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, type ReviewQueueRow } from "@/api/assessments";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { EmptyState } from "@/components/lms/empty-state";
import { NativeSelect } from "@/components/lms/forms";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { useApiMutation } from "@/lib/mutation";
import { ResultsReviewDialog } from "./results-review";
import { countsText } from "./results-text";

type Group = "review" | "waiting" | "published";

const GROUPS: { key: Group; title: string; empty: string }[] = [
  { key: "review", title: "Needs your review", empty: "Nothing needs your review." },
  { key: "waiting", title: "Waiting on the trainer", empty: "Nothing is waiting on a trainer." },
  { key: "published", title: "Published", empty: "Nothing is published yet." },
];

const rowKey = (r: ReviewQueueRow) => `${r.kind}-${r.item_id}-${r.batch.batch_id}`;
const isUnready = (r: ReviewQueueRow) => r.state === "Configuration Pending";
const trainerGaps = (r: ReviewQueueRow) => (r.gap_details ?? []).filter((g) => g.owner === "trainer");

function groupOf(r: ReviewQueueRow): Group {
  if (isUnready(r)) return trainerGaps(r).length === 0 && (r.gap_details ?? []).length > 0 ? "review" : "waiting";
  if (r.counts.provisional > 0 || r.counts.moderated > 0) return "review";
  if (r.counts.awaiting_grading > 0) return "waiting";
  return "published";
}

function ApproveTestButton({ row }: { row: ReviewQueueRow }) {
  const approve = useApiMutation(() => assessmentsApi.approveTest(row.item_id), {
    success: `${row.title} is approved`,
    next: "The trainer can release it to students now.",
    view: { to: "/branch/results", label: "View marks & results" },
    invalidate: [["assessment-reviews"], ["tests"], ["branch"], ["nav"]],
  });
  return (
    <ConfirmDialog
      title={`Approve “${row.title}”?`}
      consequence="You are saying the questions and settings are right. The trainer can then release the test to students."
      confirmLabel="Approve test"
      onConfirm={() => approve.mutateAsync(undefined)}
    >
      <Button size="sm">Approve test</Button>
    </ConfirmDialog>
  );
}

function ResultCard({ row, onReview }: { row: ReviewQueueRow; onReview: (row: ReviewQueueRow) => void }) {
  const gaps = row.gap_details ?? [];
  const onlyApproval = isUnready(row) && gaps.length > 0 && gaps.every((g) => g.owner === "you");
  const hasMarks = row.counts.provisional + row.counts.moderated + row.counts.published > 0;
  return (
    <li className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium break-words">{row.title}</p>
          <p className="text-sm text-muted-foreground">
            {row.kind} · {row.type} ·{" "}
            <Link to="/branch/batches/$id" params={{ id: String(row.batch.batch_id) }} className="text-primary underline-offset-2 hover:underline">
              {row.batch.batch_code}
            </Link>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Tag tone="neutral">{row.kind}</Tag>
          <StatusBadge domain={isUnready(row) ? "test" : "result"} code={row.state} />
        </div>
      </div>
      {isUnready(row) ? (
        <div className="mt-2 space-y-1">
          <p className="text-sm text-muted-foreground">This test cannot be released yet. What is missing:</p>
          <ul className="list-disc space-y-0.5 pl-5 text-sm" aria-label="What is missing">
            {gaps.length > 0
              ? gaps.map((g) => (
                  <li key={g.text} className={g.owner === "you" ? "font-medium" : undefined}>
                    {g.owner === "you" ? g.owner_label : `${g.text} - ${g.owner_label}`}
                  </li>
                ))
              : (row.gaps ?? []).map((g) => <li key={g}>{g}</li>)}
          </ul>
        </div>
      ) : (
        <p className="mt-2 text-sm">{countsText(row.counts)}</p>
      )}
      {row.counts.awaiting_grading > 0 && !isUnready(row) && (
        <p className="mt-1 text-sm text-warning">
          {row.counts.awaiting_grading === 1
            ? "1 attempt is still being marked by the trainer."
            : `${row.counts.awaiting_grading} attempts are still being marked by the trainer.`}
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {onlyApproval && row.can_moderate && <ApproveTestButton row={row} />}
        {!isUnready(row) && hasMarks && (
          <Button size="sm" variant={groupOf(row) === "review" ? "default" : "outline"} onClick={() => onReview(row)}>
            Review marks
          </Button>
        )}
      </div>
    </li>
  );
}

export function BranchResults() {
  // The route declares no search schema, so read `?batch=` loosely.
  const search = useSearch({ strict: false }) as { batch?: unknown };
  const navigate = useNavigate();
  const batchId = Number(search.batch) > 0 ? Number(search.batch) : null;
  const setBatch = (id: number | null) =>
    void navigate({ to: "/branch/results", search: ((prev: Record<string, unknown>) => ({ ...prev, batch: id ?? undefined })) as never, replace: true });
  const [openKey, setOpenKey] = useState<string | null>(null);
  const query = useQuery({ queryKey: ["assessment-reviews"], queryFn: () => assessmentsApi.reviewQueue() });

  const open = (openKey && query.data?.find((r) => rowKey(r) === openKey)) || null;

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead title="Marks & results" description="Check the trainer's marks, then publish them to students." />
      <QueryView
        query={query}
        skeleton="cards"
        isEmpty={(rows) => rows.length === 0}
        empty="No tests or assignments have marks to check yet. They appear here once students hand in work or take a test."
        emptyAction={
          <Button asChild size="sm" variant="outline">
            <Link to="/branch/batches">Open Batches</Link>
          </Button>
        }
      >
        {(all) => {
          const batches = [...new Map(all.map((r) => [r.batch.batch_id, r.batch.batch_code])).entries()].sort((a, b) => a[1].localeCompare(b[1]));
          const rows = batchId === null ? all : all.filter((r) => r.batch.batch_id === batchId);
          return (
            <>
              <div className="flex flex-wrap items-center gap-3">
                <div className="w-full max-w-xs">
                  <NativeSelect
                    aria-label="Batch"
                    placeholder="All batches"
                    options={batches.map(([id, code]) => ({ value: id, label: code }))}
                    value={batchId ?? ""}
                    onChange={(e) => setBatch(e.target.value ? Number(e.target.value) : null)}
                  />
                </div>
                <p className="text-sm text-muted-foreground" role="status">
                  {GROUPS.map((g) => `${rows.filter((r) => groupOf(r) === g.key).length} ${g.title.toLowerCase()}`).join(" · ")}
                </p>
              </div>
              {rows.length === 0 ? (
                <EmptyState
                  reason="No tests or assignments with marks in this batch."
                  action={
                    <Button size="sm" variant="outline" onClick={() => setBatch(null)}>
                      Show all batches
                    </Button>
                  }
                />
              ) : (
                GROUPS.map((g) => {
                  const inGroup = rows.filter((r) => groupOf(r) === g.key);
                  if (inGroup.length === 0 && g.key !== "review") return null;
                  return (
                    <section key={g.key} aria-labelledby={`group-${g.key}`} className="space-y-2">
                      <h2 id={`group-${g.key}`} className="text-base font-semibold">
                        {g.title} <span className="text-sm font-normal text-muted-foreground">({inGroup.length})</span>
                      </h2>
                      {inGroup.length === 0 ? (
                        <p className="rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">{g.empty}</p>
                      ) : (
                        <ul className="space-y-3">
                          {inGroup.map((r) => (
                            <ResultCard key={rowKey(r)} row={r} onReview={(r) => setOpenKey(rowKey(r))} />
                          ))}
                        </ul>
                      )}
                    </section>
                  );
                })
              )}
            </>
          );
        }}
      </QueryView>
      <HowThisWorks>
        <p>Students see only published marks. Until you publish, the marks you see are the trainer's.</p>
        <p>"Change marks" needs a reason, and the reason is kept. A mark you change is the one students see when you publish.</p>
        <p>Attempts that still have written answers to mark are not published. The trainer marks them first.</p>
        <p>Approving questions for tests is now under Content &amp; questions.</p>
      </HowThisWorks>
      {open && <ResultsReviewDialog key={openKey} row={open} onClose={() => setOpenKey(null)} />}
    </div>
  );
}
