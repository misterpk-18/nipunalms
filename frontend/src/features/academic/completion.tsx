import { certificatesApi, COMPLETION_DECISIONS, useCompletionRows, type CompletionDecision, type CompletionRow } from "@/api/certificates";
import { DataTable, PageHead, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { AttendanceCell, CompletionNote, FormDialog } from "@/features/shared/attendance-parts";
import { percent } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";

const REFRESH = [["completion"], ["certificates"], ["progress"]];

function Actions({ row }: { row: CompletionRow }) {
  const open = useApiMutation(certificatesApi.openReview, { success: "Review opened.", invalidate: REFRESH });
  const recommend = useApiMutation(
    (v: { id: number; recommendation: CompletionDecision; comment?: string }) => certificatesApi.recommendCompletion(v.id, v.recommendation, v.comment),
    {
      success: "Recommendation recorded.",
      invalidate: REFRESH,
    },
  );
  const decide = useApiMutation(
    (v: { id: number; decision: CompletionDecision; reason?: string }) => certificatesApi.decideCompletion(v.id, v.decision, v.reason),
    {
      success: (r) => (r.decision === "Complete" ? "Completed. Certificate eligibility opened." : `Decision recorded: ${r.decision}.`),
      invalidate: REFRESH,
    },
  );
  const review = row.review;

  if (row.enrolment.status === "Completed" && (!review || review.status === "Decided")) return <span className="text-sm text-muted-foreground">Completed</span>;
  if (!review || review.status === "Decided") {
    return (
      <Button size="sm" variant="outline" disabled={open.isPending} onClick={() => open.mutate(row.enrolment.enrolment_id)}>
        Open review
      </Button>
    );
  }
  return (
    <div className="flex flex-wrap gap-2">
      <FormDialog
        trigger={
          <Button size="sm" variant="outline">
            Recommend
          </Button>
        }
        title={`Recommendation: ${row.student.full_name}`}
        description="The recommendation informs the Academic Coordinator's decision; it does not make it."
        submitLabel="Record recommendation"
        fields={[
          { name: "recommendation", label: "Recommendation", kind: "select", options: COMPLETION_DECISIONS },
          { name: "comment", label: "Comment (required unless Complete)", kind: "textarea" },
        ]}
        onSubmit={(v) =>
          recommend.mutateAsync({ id: review.review_id, recommendation: v["recommendation"] as CompletionDecision, comment: v["comment"] || undefined })
        }
      />
      {row.can_decide && (
        <FormDialog
          trigger={<Button size="sm">Decide</Button>}
          title={`Completion decision: ${row.student.full_name}`}
          description={`${row.enrolment.course.course_code}. Complete moves the enrolment to Completed and opens certificate eligibility.`}
          submitLabel="Record decision"
          fields={[
            { name: "decision", label: "Decision", kind: "select", options: COMPLETION_DECISIONS },
            { name: "reason", label: "Reason (required unless Complete)", kind: "textarea" },
          ]}
          onSubmit={(v) => decide.mutateAsync({ id: review.review_id, decision: v["decision"] as CompletionDecision, reason: v["reason"] || undefined })}
        />
      )}
    </div>
  );
}

export function AcademicCompletion() {
  const query = useCompletionRows({ per_page: 100 });
  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHead
        title="Completion Review"
        description="Evidence-based decision per enrolment: attendance, required learning, open recoveries and the trainer's recommendation."
      />
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No enrolment is running yet.">
        {(page) => (
          <DataTable
            caption="Completion review"
            rows={page.data}
            getKey={(r) => r.enrolment.enrolment_id}
            cols={[
              { h: "Student", c: (r) => `${r.student.full_name} (${r.batch?.batch_code.replace("NIT-", "") ?? "no batch"})` },
              { h: "Course", c: (r) => r.enrolment.course.course_code },
              { h: "Delivered", c: (r) => percent(r.evidence?.delivery.percent) },
              { h: "Attendance", c: (r) => (r.evidence ? <AttendanceCell measures={r.evidence.attendance} /> : "—") },
              { h: "Required learning", c: (r) => percent(r.evidence?.required_learning.percent) },
              { h: "Trainer recommends", c: (r) => r.review?.trainer_recommendation ?? "—" },
              {
                h: "State",
                c: (r) => (
                  <StatusBadge>{r.review?.status === "Open" ? "Review open" : r.review?.decision ? `${r.review.decision}` : r.certificate_status}</StatusBadge>
                ),
              },
              { h: "Action", c: (r) => <Actions row={r} /> },
            ]}
          />
        )}
      </QueryView>
      <CompletionNote />
    </div>
  );
}
