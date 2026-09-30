import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { contentApi, formatDateTime, type ContentItem } from "@/api/content";
import { DataTable, Note, PageHead, PillTabs, QueryView, StatusBadge } from "@/components/lms/ui";
import { Field } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";
import { ContentDetailDialog } from "@/features/shared/content-detail";

const TABS = {
  "Awaiting review": "Submitted,Under Review",
  "Ready to release": "Approved",
  Released: "Released",
  "Changes requested": "Changes Requested",
  All: "",
} as const;
type Tab = keyof typeof TABS;

export function AcademicContentReview() {
  const [tab, setTab] = useState<Tab>("Awaiting review");
  const query = useQuery({ queryKey: ["content-items", "review", tab], queryFn: () => contentApi.items({ status: TABS[tab], per_page: 100 }) });
  const [acting, setActing] = useState<{ item: ContentItem; mode: "review" | "retire" } | null>(null);
  const [detailId, setDetailId] = useState<number | null>(null);
  const release = useApiMutation((id: number) => contentApi.release(id), { success: "Released to students", invalidate: [["content-items"]] });
  const start = useApiMutation((id: number) => contentApi.review(id, { decision: "start" }), { success: "Review started", invalidate: [["content-items"]] });

  return (
    <div className="mx-auto max-w-6xl">
      <PageHead title="Content Review" description="Review trainer-submitted content before release to students." />
      <PillTabs label="Content state" tabs={Object.keys(TABS) as Tab[]} value={tab} onChange={setTab} />
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="Nothing in this state.">
        {(page) => (
          <DataTable
            caption="Content review queue"
            rows={page.data}
            getKey={(i) => i.content_item_id}
            cols={[
              {
                h: "Item",
                c: (i) => (
                  <>
                    <div className="font-medium">{i.title}</div>
                    <div className="text-xs text-muted-foreground">
                      {i.item_code} · {i.content_type} · v{i.version_no}
                    </div>
                  </>
                ),
              },
              { h: "Submitted by", c: (i) => i.owner.full_name },
              { h: "Topic", c: (i) => i.topic?.title ?? i.course.title },
              { h: "Audience", c: (i) => i.batch?.batch_code ?? `${i.branch.branch_code} · whole course` },
              {
                h: "State",
                c: (i) => (
                  <>
                    <StatusBadge>{i.status}</StatusBadge>
                    {i.submitted_at && <div className="text-xs text-muted-foreground">{formatDateTime(i.submitted_at)}</div>}
                  </>
                ),
              },
              {
                h: "Action",
                c: (i) => (
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="ghost" onClick={() => setDetailId(i.content_item_id)}>
                      Open
                    </Button>
                    {i.status === "Submitted" && (
                      <Button size="sm" variant="outline" onClick={() => start.mutate(i.content_item_id)}>
                        Start review
                      </Button>
                    )}
                    {(i.status === "Submitted" || i.status === "Under Review") && (
                      <Button size="sm" onClick={() => setActing({ item: i, mode: "review" })}>
                        Review
                      </Button>
                    )}
                    {i.status === "Approved" && (
                      <Button size="sm" onClick={() => release.mutate(i.content_item_id)}>
                        Release
                      </Button>
                    )}
                    {i.status === "Released" && (
                      <Button size="sm" variant="outline" onClick={() => setActing({ item: i, mode: "retire" })}>
                        Retire
                      </Button>
                    )}
                  </div>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <div className="mt-4">
        <Note>
          Approving a routine resource does not change the syllabus, hours, assessments or completion rules. You cannot review content you uploaded yourself.
        </Note>
      </div>
      {acting && <DecisionDialog {...acting} onClose={() => setActing(null)} />}
      {detailId !== null && <ContentDetailDialog id={detailId} onClose={() => setDetailId(null)} />}
    </div>
  );
}

function DecisionDialog({ item, mode, onClose }: { item: ContentItem; mode: "review" | "retire"; onClose: () => void }) {
  const [comment, setComment] = useState("");
  const options = { invalidate: [["content-items"]], onSuccess: onClose };
  const review = useApiMutation(
    (body: { decision: "approve" | "request_changes" | "reject"; release?: boolean }) =>
      contentApi.review(item.content_item_id, { ...body, comment: comment.trim() || undefined }),
    { success: "Decision recorded", ...options },
  );
  const retire = useApiMutation(() => contentApi.retire(item.content_item_id, comment.trim()), { success: "Withdrawn from students", ...options });
  const busy = review.isPending || retire.isPending;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{mode === "review" ? `Review: ${item.title}` : `Retire: ${item.title}`}</DialogTitle>
          <DialogDescription>
            {mode === "review"
              ? `Version ${item.version_no} by ${item.owner.full_name}. Approve and release makes it visible to ${item.batch ? `batch ${item.batch.batch_code}` : "the whole course"}.`
              : "Students lose access immediately. Files and versions are kept."}
          </DialogDescription>
        </DialogHeader>
        <Field label={mode === "review" ? "Comment (required to request changes or reject)" : "Reason"} htmlFor="decision-comment">
          <Textarea id="decision-comment" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} />
        </Field>
        <DialogFooter className="gap-2">
          {mode === "review" ? (
            <>
              <Button variant="destructive" disabled={busy || !comment.trim()} onClick={() => review.mutate({ decision: "reject" })}>
                Reject
              </Button>
              <Button variant="outline" disabled={busy || !comment.trim()} onClick={() => review.mutate({ decision: "request_changes" })}>
                Request changes
              </Button>
              <Button variant="outline" disabled={busy} onClick={() => review.mutate({ decision: "approve" })}>
                Approve
              </Button>
              <Button disabled={busy} onClick={() => review.mutate({ decision: "approve", release: true })}>
                Approve &amp; release
              </Button>
            </>
          ) : (
            <Button variant="destructive" disabled={busy || !comment.trim()} onClick={() => retire.mutate()}>
              Retire
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
