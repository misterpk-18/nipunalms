import { useState } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useToGrade, type GradeItem } from "@/api/trainer";
import { EmptyState } from "@/components/lms/empty-state";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, PageHead, PillTabs, QueryView, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { fmtDate, fmtDateTime } from "@/features/shared/format";

const TABS = ["All", "Assignments", "Tests"] as const;
type Tab = (typeof TABS)[number];

/** How long the work has waited, in plain words. */
export function waited(submittedAt: string | null): string {
  if (!submittedAt) return "—";
  const hours = Math.floor((Date.now() - new Date(submittedAt).getTime()) / 3_600_000);
  if (hours < 1) return "Just now";
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"}`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"}`;
}

export function StateTag({ item }: { item: GradeItem }) {
  if (item.kind === "attempt") return <Tag tone="warning">{`${item.to_mark} answer${item.to_mark === 1 ? "" : "s"} to mark`}</Tag>;
  return item.started ? <Tag tone="info">Review started</Tag> : <Tag tone="neutral">Not started</Tag>;
}

export function DueLine({ item }: { item: GradeItem }) {
  if (!item.review_due) return <span className="text-muted-foreground">No target</span>;
  return item.review_due.overdue ? (
    <span className="font-medium text-destructive">Overdue since {fmtDate(item.review_due.due_on)}</span>
  ) : (
    <span>Review by {fmtDate(item.review_due.due_on)}</span>
  );
}

export function TrainerToGrade() {
  const { batch } = useSearch({ from: "/trainer/to-grade/" });
  const navigate = useNavigate();
  const query = useToGrade(batch);
  const [tab, setTab] = useState<Tab>("All");

  return (
    <div className="mx-auto max-w-6xl">
      <PageHead
        title="To grade"
        description="Hand-ins and test answers waiting for your marks, overdue and oldest first."
        actions={
          query.data && query.data.items[0] ? (
            <Button asChild>
              <Link
                to="/trainer/to-grade/$kind/$id"
                params={{ kind: query.data.items[0].kind, id: String(query.data.items[0].id) }}
                search={batch ? { batch } : {}}
              >
                Start with the first
              </Link>
            </Button>
          ) : undefined
        }
      />
      <QueryView
        query={query}
        isEmpty={(data) => data.counts.total === 0 && !batch}
        empty="Nothing is waiting for your marks. New hand-ins and test answers show up here as soon as students submit them."
        emptyAction={
          <div className="flex flex-wrap justify-center gap-2">
            <Button asChild size="sm">
              <Link to="/trainer/assignments">Open Assignments</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to="/trainer/assessments">Open Assessments</Link>
            </Button>
          </div>
        }
      >
        {(data) => {
          const rows = data.items.filter((i) => (tab === "All" ? true : tab === "Assignments" ? i.kind === "submission" : i.kind === "attempt"));
          return (
            <>
              <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
                <PillTabs
                  label="Kind of work"
                  tabs={TABS}
                  value={tab}
                  onChange={setTab}
                  counts={{ All: data.counts.total, Assignments: data.counts.submissions, Tests: data.counts.attempts }}
                />
                <div className="w-full sm:w-56">
                  <Label htmlFor="grade-batch">Batch</Label>
                  <NativeSelect
                    id="grade-batch"
                    placeholder="All my batches"
                    value={batch ?? ""}
                    onChange={(e) => void navigate({ to: "/trainer/to-grade", search: e.target.value ? { batch: Number(e.target.value) } : {} })}
                    options={data.batches.map((b) => ({ value: b.batch_id, label: b.batch_code }))}
                  />
                </div>
              </div>
              {data.counts.overdue > 0 && (
                <p className="mb-3 text-sm font-medium text-destructive">
                  {data.counts.overdue} {data.counts.overdue === 1 ? "item is" : "items are"} past the review target and listed first.
                </p>
              )}
              {rows.length === 0 ? (
                <EmptyState
                  reason={batch ? "Nothing is waiting in this batch." : `No ${tab === "Tests" ? "test answers" : "hand-ins"} are waiting.`}
                  action={
                    batch ? (
                      <Button asChild size="sm" variant="outline">
                        <Link to="/trainer/to-grade">Show all my batches</Link>
                      </Button>
                    ) : undefined
                  }
                />
              ) : (
                <DataTable
                  caption="Work to grade"
                  rows={rows}
                  getKey={(i) => i.key}
                  cols={[
                    { h: "Student", c: (i) => <span className="font-medium">{i.student.full_name}</span> },
                    {
                      h: "Work",
                      c: (i) => (
                        <>
                          <div>{i.title}</div>
                          <div className="text-xs text-muted-foreground">
                            {i.type} · {i.batch.batch_code}
                          </div>
                        </>
                      ),
                    },
                    {
                      h: "Waiting",
                      c: (i) => (
                        <>
                          <div title={fmtDateTime(i.submitted_at)}>{waited(i.submitted_at)}</div>
                          {i.is_late && <div className="text-xs text-muted-foreground">Handed in late</div>}
                        </>
                      ),
                    },
                    { h: "Target", c: (i) => <DueLine item={i} /> },
                    { h: "State", c: (i) => <StateTag item={i} /> },
                    {
                      h: "",
                      c: (i) => (
                        <Button asChild size="sm" aria-label={`Grade ${i.title} by ${i.student.full_name}`}>
                          <Link to="/trainer/to-grade/$kind/$id" params={{ kind: i.kind, id: String(i.id) }} search={batch ? { batch } : {}}>
                            Grade
                          </Link>
                        </Button>
                      ),
                    },
                  ]}
                />
              )}
              <div className="mt-4">
                <HowThisWorks>
                  <p>
                    Marks you save stay provisional until your Branch Manager publishes them, so students do not see them yet. The review target is 3, 5 or 7
                    working days from the hand-in, depending on the kind of work. Open an item to read it, mark it and move straight on to the next.
                  </p>
                </HowThisWorks>
              </div>
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
