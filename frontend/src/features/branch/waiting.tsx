/** Waiting for a batch: every student with an admission and no seat yet, the batches that could take them and a one-click Allocate. */
import { useState } from "react";
import { Link, useSearch } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { branchApi } from "@/api/branch";
import { useAuth } from "@/auth/auth";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, QueryView } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { WaitingStudent } from "@/features/shared/waiting-student";

/** `manage` comes from the route (Branch Manager). */
export function BranchWaiting({ manage }: { manage: boolean }) {
  const { branchId, allowedBranches: branches } = useAuth();
  const initial = (useSearch({ strict: false }) as { q?: string }).q ?? "";
  const [q, setQ] = useState(initial);
  const search = q.trim();
  const query = useQuery({
    queryKey: ["branch", "waiting", branchId, search],
    queryFn: () => branchApi.waiting({ branch_id: branchId, q: search || undefined }),
  });
  const total = query.data?.meta.total;
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead
        title="Waiting for a batch"
        description="Students who have joined and have no batch yet. Each one shows the batches that could take them; allocate in one click."
      />
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 rounded-xl border bg-card px-4 py-2" role="status">
          <Users className="size-5 text-muted-foreground" aria-hidden />
          <span className="text-2xl font-semibold tabular-nums">{total ?? "…"}</span>
          <span className="text-sm text-muted-foreground">{total === 1 ? "student waiting" : "students waiting"}</span>
        </div>
        <Input
          className="max-w-sm"
          aria-label="Search the waiting list"
          placeholder="Search by name, mobile or admission number"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <QueryView
        query={query}
        skeleton="cards"
        isEmpty={(page) => page.data.length === 0}
        empty={
          search ? "No waiting student matches that search." : "Nobody is waiting for a batch. New admissions from the CRM appear here until they have a seat."
        }
        emptyAction={
          manage ? (
            <Button asChild size="sm" variant="outline">
              <Link to="/branch/batches">Open Batches</Link>
            </Button>
          ) : undefined
        }
      >
        {(page) => (
          <ul className="space-y-3" aria-label="Students waiting for a batch">
            {page.data.map((row) => (
              <WaitingStudent key={row.enrolment.enrolment_id} row={row} manage={manage} withBranch={branches.length > 1 && branchId === null} studentBase="/branch" />
            ))}
          </ul>
        )}
      </QueryView>
      {query.data && query.data.meta.pages > 1 && (
        <p className="text-xs text-muted-foreground">
          Showing the {query.data.data.length} students who have waited longest. Allocate some, or search for a name.
        </p>
      )}
      <HowThisWorks>
        <p>A batch is offered when it teaches the student's course at their branch and has a seat left. Closed, on-hold and full batches are not listed.</p>
        <p>
          "Allocate…" with dots means the check found something to look at, such as a different class mode or a timetable clash. You see it before you confirm.
        </p>
        <p>A student's Joining Date is set at the first class they attend (marked Present or Late), not when they are allocated.</p>
      </HowThisWorks>
    </div>
  );
}
