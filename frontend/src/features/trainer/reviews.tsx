import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, type Submission } from "@/api/assessments";
import { PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { formatIst, fromIstInput, istInputIn } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";

function ReviewCard({ submission }: { submission: Submission }) {
  const assignment = submission.assignment;
  const [feedback, setFeedback] = useState("");
  const [marks, setMarks] = useState("");
  const [resubmitBy, setResubmitBy] = useState(istInputIn(72));
  const [started, setStarted] = useState(Boolean(submission.review_started_at));
  const refresh = [["submissions"], ["assignments"]];
  const start = useApiMutation(() => assessmentsApi.startReview(submission.submission_id), { invalidate: [] });
  const save = useApiMutation(() => assessmentsApi.review(submission.submission_id, { outcome: "Reviewed", feedback, marks: Number(marks) }), {
    success: "Review saved. The result stays provisional until published.",
    invalidate: refresh,
  });
  const resubmit = useApiMutation(
    () => assessmentsApi.review(submission.submission_id, { outcome: "Resubmission Requested", feedback, resubmission_due_at: fromIstInput(resubmitBy) }),
    { success: "Resubmission requested", invalidate: refresh },
  );
  const state = started ? "Under Review" : "Submitted";
  const id = submission.submission_id;

  return (
    <Section title={`${assignment.title} — ${submission.student.full_name}`} actions={<StatusBadge>{state}</StatusBadge>} className="space-y-2">
      <p className="text-sm text-muted-foreground">
        Submission v{submission.version_no} · {formatIst(submission.submitted_at)} · {submission.submission_code}
        {submission.is_late && " · Late"}
      </p>
      {submission.body_text && <p className="whitespace-pre-wrap rounded bg-muted p-2 text-sm">{submission.body_text}</p>}
      {submission.link_url && (
        <a href={submission.link_url} target="_blank" rel="noreferrer" className="block text-sm text-primary underline">
          {submission.link_url}
        </a>
      )}
      {submission.file && (
        <Button variant="outline" size="sm" onClick={() => void assessmentsApi.downloadSubmission(id, submission.file!.filename)}>
          Download {submission.file.filename}
        </Button>
      )}
      {submission.ai_disclosure && <p className="text-sm">AI disclosure: {submission.ai_disclosure}</p>}
      <div className="grid gap-2 sm:grid-cols-[1fr_8rem]">
        <div className="space-y-1.5">
          <Label htmlFor={`fb-${id}`}>Feedback</Label>
          <Textarea
            id={`fb-${id}`}
            rows={2}
            value={feedback}
            onFocus={() => {
              if (!started) {
                setStarted(true);
                start.mutate(undefined);
              }
            }}
            onChange={(e) => setFeedback(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`mk-${id}`}>Marks / {assignment.max_marks ?? ""}</Label>
          <Input id={`mk-${id}`} inputMode="decimal" value={marks} onChange={(e) => setMarks(e.target.value)} />
        </div>
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <Button disabled={!feedback || marks === "" || save.isPending} onClick={() => save.mutate(undefined)}>
          Save review
        </Button>
        <div className="space-y-1.5">
          <Label htmlFor={`rs-${id}`}>Resubmit by (IST)</Label>
          <Input id={`rs-${id}`} type="datetime-local" value={resubmitBy} onChange={(e) => setResubmitBy(e.target.value)} />
        </div>
        <Button variant="outline" disabled={!feedback || resubmit.isPending} onClick={() => resubmit.mutate(undefined)}>
          Request resubmission
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">Result remains provisional until the Academic Coordinator publishes it.</p>
    </Section>
  );
}

export function TrainerReviews() {
  const query = useQuery({
    queryKey: ["submissions", "queue"],
    queryFn: () => assessmentsApi.submissions({ status: "Awaiting Review", reviewer_me: true }),
  });
  return (
    <div className="mx-auto max-w-5xl">
      <PageHead title="Submissions awaiting my review" description="The newest version of each student's work, for assignments you review." />
      <QueryView query={query} isEmpty={(p) => p.data.length === 0} empty="Nothing is waiting for your review.">
        {(page) => (
          <div className="space-y-4">
            {page.data.map((s) => (
              <ReviewCard key={s.submission_id} submission={s} />
            ))}
          </div>
        )}
      </QueryView>
    </div>
  );
}
