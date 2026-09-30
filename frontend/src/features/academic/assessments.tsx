import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, type Result, type ReviewQueueRow } from "@/api/assessments";
import { DataTable, Note, PageHead, PillTabs, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { QuestionBank } from "@/features/trainer/question-bank";
import { useApiMutation } from "@/lib/mutation";

const REFRESH = [["assessment-reviews"], ["results"], ["tests"], ["assignments"]];

function ResultRow({ result }: { result: Result }) {
  const [marks, setMarks] = useState("");
  const [reason, setReason] = useState("");
  const moderate = useApiMutation(() => assessmentsApi.moderate(result.result_id, Number(marks), reason), { success: "Marks moderated", invalidate: REFRESH });
  const published = result.status === "Published";
  return (
    <li className="rounded-lg border p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <strong>{result.student.full_name}</strong>
        <StatusBadge>{result.status}</StatusBadge>
        <span>
          Trainer {result.provisional_marks} / {result.max_marks}
          {result.moderated_marks && ` · Moderated ${result.moderated_marks}`}
          {result.final_marks && ` · Published ${result.final_marks}`}
        </span>
      </div>
      {result.moderation_reason && <p className="mt-1 text-muted-foreground">Reason: {result.moderation_reason}</p>}
      {!published && (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <Input
            aria-label={`Moderated marks for ${result.student.full_name}`}
            className="w-28"
            inputMode="decimal"
            placeholder="New marks"
            value={marks}
            onChange={(e) => setMarks(e.target.value)}
          />
          <Input
            aria-label={`Reason for ${result.student.full_name}`}
            className="min-w-48 flex-1"
            placeholder="Reason for the adjustment"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <Button size="sm" variant="outline" disabled={!marks || reason.length < 5 || moderate.isPending} onClick={() => moderate.mutate(undefined)}>
            Moderate
          </Button>
        </div>
      )}
    </li>
  );
}

function ResultsDialog({ row, onClose }: { row: ReviewQueueRow | null; onClose: () => void }) {
  const filter = row ? (row.kind === "Assignment" ? { assignment_id: row.item_id } : { test_id: row.item_id }) : {};
  const query = useQuery({
    queryKey: ["results", "staff", row?.kind, row?.item_id],
    queryFn: () => assessmentsApi.results({ ...filter, batch_id: row!.batch.batch_id }),
    enabled: row !== null,
  });
  return (
    <Dialog open={row !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{row?.title}: results</DialogTitle>
          <DialogDescription>Marks are provisional until you publish. A moderation change needs a reason and is audited.</DialogDescription>
        </DialogHeader>
        <QueryView query={query} isEmpty={(p) => p.data.length === 0} empty="No results yet.">
          {(page) => (
            <ul className="space-y-2">
              {page.data.map((r) => (
                <ResultRow key={`${r.result_id}-${r.status}-${r.moderated_marks}`} result={r} />
              ))}
            </ul>
          )}
        </QueryView>
      </DialogContent>
    </Dialog>
  );
}

function Moderation() {
  const query = useQuery({ queryKey: ["assessment-reviews"], queryFn: () => assessmentsApi.reviewQueue() });
  const [open, setOpen] = useState<ReviewQueueRow | null>(null);
  const publish = useApiMutation(
    (row: ReviewQueueRow) => assessmentsApi.publish(row.kind === "Assignment" ? { assignment_id: row.item_id } : { test_id: row.item_id }),
    { success: (r) => `${r.published} result${r.published === 1 ? "" : "s"} published to students`, invalidate: REFRESH },
  );
  const approve = useApiMutation((row: ReviewQueueRow) => assessmentsApi.approveTest(row.item_id), { success: "Test approved", invalidate: REFRESH });
  return (
    <QueryView query={query} isEmpty={(rows) => rows.length === 0} empty="No assessments need review.">
      {(rows) => (
        <DataTable
          caption="Assessment reviews"
          rows={rows}
          getKey={(r) => `${r.kind}-${r.item_id}-${r.batch.batch_id}`}
          cols={[
            { h: "Item", c: (r) => <span className="font-medium">{r.title}</span> },
            { h: "Type", c: (r) => <StatusBadge tone="info">{r.type}</StatusBadge> },
            { h: "Batch", c: (r) => <span className="font-mono text-xs">{r.batch.batch_code}</span> },
            {
              h: "Results",
              c: (r) =>
                r.state === "Configuration Pending"
                  ? (r.gaps?.join("; ") ?? "")
                  : `${r.counts.provisional} provisional · ${r.counts.moderated} moderated · ${r.counts.published} published`,
            },
            { h: "State", c: (r) => <StatusBadge>{r.state}</StatusBadge> },
            {
              h: "Action",
              c: (r) => (
                <div className="flex flex-wrap gap-2">
                  {r.state === "Configuration Pending" && r.gaps?.length === 1 && r.gaps[0] === "Academic Coordinator approval" && r.can_moderate && (
                    <Button size="sm" onClick={() => approve.mutate(r)}>
                      Approve test
                    </Button>
                  )}
                  {r.state !== "Configuration Pending" && (
                    <Button size="sm" variant="outline" onClick={() => setOpen(r)}>
                      Review marks
                    </Button>
                  )}
                  {r.can_moderate && r.state !== "Published" && r.state !== "Configuration Pending" && (
                    <Button size="sm" onClick={() => publish.mutate(r)}>
                      Publish
                    </Button>
                  )}
                </div>
              ),
            },
          ]}
        />
      )}
    </QueryView>
  );
}

const TABS = ["Results & moderation", "Questions to approve"] as const;

export function AcademicAssessments() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Results & moderation");
  return (
    <div className="mx-auto max-w-6xl">
      <PageHead title="Assignment / Assessment Review" description="Moderate assessments and publish academic results." />
      <PillTabs tabs={TABS} value={tab} onChange={setTab} label="Review areas" />
      {tab === "Results & moderation" ? (
        <>
          <Moderation />
          <div className="mt-4">
            <Note>Students see only Published results. Publication is separate from any later answer release.</Note>
          </div>
        </>
      ) : (
        <QuestionBank canApprove initialStatus="Draft" />
      )}
    </div>
  );
}
