/** Batches: every batch at the branch, what each needs next, and a short wizard to create one. Each row opens the batch page. */
import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { type Batch, deliveryApi } from "@/api/delivery";
import { useAuth } from "@/auth/auth";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, PageHead, QueryView, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { BranchFilter } from "@/features/shared/branch-filter";
import { StateBadge } from "@/features/shared/delivery-ui";
import { NewBatchWizard } from "./new-batch-wizard";

const CLOSED = ["Completed", "Cancelled", "Archived"];
const SHOW = [
  { value: "open", label: "Open batches" },
  { value: "all", label: "All batches" },
  { value: "closed", label: "Finished or cancelled" },
];

/** The next thing a batch needs, in a few words (the batch page says it exactly). */
export function nextStep(b: Batch): { text: string; tone: "warning" | "info" | "neutral" } {
  if (CLOSED.includes(b.state)) return { text: b.state_label, tone: "neutral" };
  if (b.state === "On Hold") return { text: "On hold", tone: "neutral" };
  if (!b.trainers.some((t) => t.role === "Lead")) return { text: "Assign a lead trainer", tone: "warning" };
  if (b.state === "Forming") return { text: "Finish setup and confirm", tone: "warning" };
  if (b.state === "Proposed") return { text: "Confirm the batch", tone: "warning" };
  if (b.allocated_count === 0) return { text: "Add students", tone: "info" };
  return { text: "Running", tone: "neutral" };
}

/**
 * Batches at one branch (Branch Manager: `manage`, the session's branch) or across branches (Super Admin and Founder: read-only, with a branch
 * filter). `basePath` is the role's list route; each row opens `${basePath}/$id`.
 */
export function BatchList({
  basePath,
  manage,
  branchFilter,
  search = {},
}: {
  basePath: string;
  manage: boolean;
  branchFilter: boolean;
  search?: { new?: 1; course?: number };
}) {
  const { branchId: sessionBranch } = useAuth();
  const navigate = useNavigate();
  const [filterBranch, setFilterBranch] = useState<number | null>(null);
  const branchId = branchFilter ? filterBranch : sessionBranch;
  const [show, setShow] = useState("open");
  const [q, setQ] = useState("");
  const text = q.trim();
  const query = useQuery({
    queryKey: ["delivery", "batches", "branch-list", branchId, text],
    queryFn: () => deliveryApi.batches({ branch_id: branchId, q: text || undefined }),
  });
  const wizardOpen = search.new === 1;
  const open = (id: number) => `${basePath}/${id}`;
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead
        title="Batches"
        description={
          manage
            ? "Every batch at your branch and what each one needs next. Open a batch to confirm it, add students and create its classes."
            : "Every batch in every branch, read-only. Branch Managers run their own batches; open one to see its students, classes and requests."
        }
        actions={
          <>
            {manage && (
              <NewBatchWizard
                {...(search.course ? { defaultCourseId: search.course } : {})}
                open={wizardOpen || undefined}
                onOpenChange={(open) => {
                  if (wizardOpen && !open) void navigate({ to: ".", search: {} as never, replace: true });
                }}
              />
            )}
          </>
        }
      />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {branchFilter && <BranchFilter value={filterBranch} onChange={setFilterBranch} />}
        <NativeSelect aria-label="Show" options={SHOW} value={show} onChange={(e) => setShow(e.target.value)} />
        <Input aria-label="Search batches" placeholder="Search by batch name, code or course" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <QueryView
        query={query}
        isEmpty={(page) => page.data.length === 0}
        empty={manage ? "There are no batches yet. Create one to start putting students in classes." : "There are no batches yet."}
        emptyAction={manage ? <NewBatchWizard /> : undefined}
      >
        {(page) => {
          const rows = page.data.filter((b) => (show === "all" ? true : show === "closed" ? CLOSED.includes(b.state) : !CLOSED.includes(b.state)));
          return (
            <DataTable
              caption="Batches"
              rows={rows}
              getKey={(b) => b.batch_id}
              empty="No batch matches this view."
              cols={[
                {
                  h: "Batch",
                  c: (b) => (
                    <Link to={open(b.batch_id)} className="font-medium text-primary underline-offset-2 hover:underline">
                      {b.display_name ?? b.batch_code}
                      <span className="block font-mono text-xs font-normal text-muted-foreground">{b.batch_code}</span>
                    </Link>
                  ),
                },
                { h: "Course", c: (b) => b.course.title },
                { h: "Trainer", c: (b) => b.trainers.map((t) => t.full_name).join(", ") || <span className="text-warning">None yet</span> },
                { h: "Seats", c: (b) => `${b.allocated_count} of ${b.capacity}` },
                { h: "State", c: (b) => <StateBadge label={b.state_label} /> },
                { h: "Next", c: (b) => <Tag tone={nextStep(b).tone}>{nextStep(b).text}</Tag> },
                {
                  h: "",
                  c: (b) => (
                    <Button asChild size="sm" variant="outline">
                      <Link to={open(b.batch_id)} aria-label={`Open ${b.display_name ?? b.batch_code}`}>
                        Open
                      </Link>
                    </Button>
                  ),
                },
              ]}
            />
          );
        }}
      </QueryView>
      {manage && (
        <HowThisWorks>
          <p>
            A batch starts as a Draft. Give it a lead trainer, its dates, days, times and room, then confirm it. After that you add students from Waiting for a
            batch and create its classes from the timetable.
          </p>
          <p>You confirm a batch yourself. If something looks off but you accept it, you write down why and the reason is kept on record.</p>
          <p>Changing the start, mode, days, times or end of a confirmed batch that has students needs each student's agreement first.</p>
        </HowThisWorks>
      )}
    </div>
  );
}
