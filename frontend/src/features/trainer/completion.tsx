/** Course completion for a trainer: recommend, for each student in my batches, whether the course is complete. The Branch Manager decides. */
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { certificatesApi, COMPLETION_DECISIONS, type CompletionDecision, type CompletionRow, certificateKeys } from "@/api/certificates";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormDialog } from "@/features/shared/attendance-parts";
import { Pager } from "@/features/shared/pager";
import { useApiMutation } from "@/lib/mutation";

const PER_PAGE = 20;
const REFRESH = [["completion"], ["nav"], ["trainer"]];
const OPTION_LABELS: Record<CompletionDecision, string> = {
  Complete: "Complete: the course is finished",
  "Not Yet": "Not yet complete",
  "Needs Recovery": "Needs recovery: something must be made up",
};

const percent = (value: number | null | undefined) => (value === null || value === undefined ? "no data yet" : `${Math.round(value)}%`);

function RecommendButton({ row }: { row: CompletionRow }) {
  const review = row.review;
  const name = row.student.full_name;
  const start = useApiMutation((enrolmentId: number) => certificatesApi.openReview(enrolmentId), {
    invalidate: REFRESH,
    success: `Review opened for ${name}`,
    next: "Now add your recommendation.",
  });
  const recommend = useApiMutation(
    (v: { id: number; recommendation: CompletionDecision; comment?: string }) => certificatesApi.recommendCompletion(v.id, v.recommendation, v.comment),
    { invalidate: REFRESH, success: `Recommendation sent for ${name}`, next: "The Branch Manager has been told and decides." },
  );
  if (review === null || review.status !== "Open") {
    return (
      <Button size="sm" disabled={!row.can_open || start.isPending} onClick={() => start.mutate(row.enrolment.enrolment_id)}>
        Start a review
      </Button>
    );
  }
  return (
    <FormDialog
      trigger={
        <Button size="sm" variant={review.trainer_recommendation ? "outline" : "default"}>
          {review.trainer_recommendation ? "Change recommendation" : "Recommend"}
        </Button>
      }
      title={`Recommend: ${name}`}
      description="Your recommendation informs the Branch Manager. It does not decide. Anything but Complete needs a note on what is missing."
      submitLabel="Send recommendation"
      fields={[
        { name: "recommendation", label: "Your recommendation", kind: "select", required: true, options: COMPLETION_DECISIONS, optionLabels: OPTION_LABELS },
        { name: "comment", label: "Note for the Branch Manager", kind: "textarea", hint: "Required unless you recommend Complete." },
      ]}
      onSubmit={(v) => {
        const comment = v["comment"]?.trim();
        return recommend.mutateAsync({ id: review.review_id, recommendation: v["recommendation"] as CompletionDecision, ...(comment ? { comment } : {}) });
      }}
    />
  );
}

function Row({ row }: { row: CompletionRow }) {
  const review = row.review;
  const open = review?.status === "Open";
  const evidence = row.evidence;
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 rounded-xl border bg-card p-4 shadow-sm">
      <div className="min-w-0 space-y-1">
        <p className="font-medium">
          {row.student.full_name} <span className="text-xs font-normal text-muted-foreground">{row.student.student_code}</span>
        </p>
        <p className="text-xs text-muted-foreground">{row.batch ? `Batch ${row.batch.batch_code}` : "No batch yet"} · {row.enrolment.course.title}</p>
        {evidence ? (
          <p className="text-sm text-muted-foreground">
            Attendance {percent(evidence.attendance.percent)} · Classes delivered {percent(evidence.delivery.percent)} · Required topics{" "}
            {percent(evidence.required_learning.percent)}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">No progress figures yet.</p>
        )}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {open ? <StatusBadge domain="completion" code="Review open" /> : review ? <Tag>Last decision: {review.decision}</Tag> : <Tag>No review yet</Tag>}
          {open && review?.trainer_recommendation && <Tag>You recommended: {review.trainer_recommendation}</Tag>}
        </div>
        {open && review?.trainer_comment && <p className="text-xs text-muted-foreground">Your note: {review.trainer_comment}</p>}
      </div>
      <RecommendButton row={row} />
    </li>
  );
}

export function TrainerCompletion() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: certificateKeys.completion({ status: "Active", q: q.trim(), page, per_page: PER_PAGE }),
    queryFn: () => certificatesApi.completion({ status: "Active", q: q.trim(), page, per_page: PER_PAGE }),
    placeholderData: keepPreviousData,
  });
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead
        title="Course completion"
        description="Tell the Branch Manager whether a student in your batches has completed the course. They make the decision."
      />
      <Input
        className="max-w-sm"
        aria-label="Search students"
        placeholder="Search by student name or Student ID"
        value={q}
        onChange={(e) => (setQ(e.target.value), setPage(1))}
      />
      <QueryView
        query={query}
        skeleton="cards"
        isEmpty={(r) => r.data.length === 0}
        empty={q.trim() ? "No student matches that search." : "No student in your batches is being taught right now. Students appear here once they have a seat."}
      >
        {(result) => (
          <div className="space-y-3">
            <ul className="space-y-3" aria-label="Students and their completion">
              {result.data.map((row) => (
                <Row key={row.enrolment.enrolment_id} row={row} />
              ))}
            </ul>
            <Pager meta={result.meta} onPage={setPage} noun="students" />
          </div>
        )}
      </QueryView>
      <HowThisWorks>
        <p>Start a review when a student looks ready, or when you think they are not. Then send your recommendation: Complete, Not yet, or Needs recovery.</p>
        <p>The Branch Manager needs your Complete recommendation before they can mark a course complete. You never decide it yourself.</p>
      </HowThisWorks>
    </div>
  );
}
