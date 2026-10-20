/** Content review: what trainers sent for review and what is ready to release. Questions for tests are approved on their own page (`/branch/questions`). */
import { useState } from "react";
import { Link, Navigate, useNavigate, useSearch } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { contentApi, contentReviewApi, formatDateTime, type ReviewListItem, type ReviewSummary } from "@/api/content";
import { useAuth } from "@/auth/auth";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { DataTable, LoadingSkeleton, PageHead, PillTabs, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { useApiMutation } from "@/lib/mutation";
import { audienceText, releaseConsequence } from "./content-audience";
import { ContentReviewDialog } from "./content-review";

type TabKey = "awaiting" | "ready" | "changes" | "released";

const TABS = [
  { key: "awaiting", label: "To review", statuses: "Submitted,Under Review" },
  { key: "ready", label: "Ready to release", statuses: "Approved" },
  { key: "changes", label: "Changes requested", statuses: "Changes Requested,Rejected" },
  { key: "released", label: "Released", statuses: "Released" },
] as const satisfies readonly { key: TabKey; label: string; statuses: string }[];

type TabLabel = (typeof TABS)[number]["label"];
const LABELS = TABS.map((t) => t.label) as readonly TabLabel[];
const PER_PAGE = 20;

const EMPTY: Record<TabKey, string> = {
  awaiting: "Nothing is waiting for your review. When a trainer sends content for review it appears here.",
  ready: "Nothing is approved and waiting. Content you approve without releasing stays here until you release it.",
  changes: "Nothing has been sent back. Content you ask a trainer to change or reject appears here.",
  released: "No content has been released to students yet.",
};

const isTab = (value: unknown): value is TabKey => TABS.some((t) => t.key === value);

function ReleaseButton({ item, basePath }: { item: ReviewListItem; basePath: string }) {
  const release = useApiMutation(() => contentApi.release(item.content_item_id), {
    success: `${item.title} is released`,
    next: `${audienceText(item)} can see it now.`,
    view: { to: basePath, label: "View content" },
    invalidate: [["content-items"], ["nav"], ["branch"]],
  });
  return (
    <ConfirmDialog
      title={`Release “${item.title}”?`}
      consequence={releaseConsequence(item)}
      confirmLabel="Release"
      onConfirm={() => release.mutateAsync(undefined)}
    >
      <Button size="sm" variant="secondary">
        Release
      </Button>
    </ConfirmDialog>
  );
}

function ReviewList({
  tab,
  onOpen,
  moveTo,
  counts,
  basePath,
  moreLink,
}: {
  basePath: string;
  moreLink: { to: string; label: string };
  tab: TabKey;
  onOpen: (id: number) => void;
  moveTo: (tab: TabKey) => void;
  counts?: ReviewSummary;
}) {
  const { profile } = useAuth();
  const [page, setPage] = useState(1);
  const statuses = TABS.find((t) => t.key === tab)?.statuses;
  const query = useQuery({
    queryKey: ["content-items", "review", tab, page],
    queryFn: () => contentReviewApi.list({ status: statuses, page, per_page: PER_PAGE }),
  });
  const other = TABS.find((t) => t.key !== tab && (counts?.[t.key] ?? 0) > 0);
  return (
    <>
      <QueryView
        query={query}
        isEmpty={(p) => p.data.length === 0}
        empty={EMPTY[tab]}
        emptyAction={
          other ? (
            <Button size="sm" variant="outline" onClick={() => moveTo(other.key)}>
              Open {other.label} ({counts?.[other.key]})
            </Button>
          ) : (
            <Button asChild size="sm" variant="outline">
              <Link to={moreLink.to as "/branch/results"}>{moreLink.label}</Link>
            </Button>
          )
        }
      >
        {(result) => (
          <>
            <DataTable
              caption={`Content: ${TABS.find((t) => t.key === tab)?.label}`}
              rows={result.data}
              getKey={(i) => i.content_item_id}
              cols={[
                {
                  h: "Content",
                  c: (i) => (
                    <>
                      <div className="font-medium">{i.title}</div>
                      <div className="text-xs text-muted-foreground">
                        {i.content_type} · v{i.version_no} · <span className="font-mono">{i.item_code}</span>
                      </div>
                    </>
                  ),
                },
                {
                  h: "Sent by",
                  c: (i) => (
                    <>
                      <div>{i.owner.full_name}</div>
                      {i.submitted_at && <div className="text-xs text-muted-foreground">{formatDateTime(i.submitted_at)}</div>}
                    </>
                  ),
                },
                { h: "Who will see it", c: (i) => audienceText(i) },
                {
                  h: "Status",
                  c: (i) => (
                    <div className="space-y-1">
                      <StatusBadge domain="content" code={i.status} />
                      {i.status === "Under Review" && i.claimed_by && (
                        <div className={i.claimed_by.user_id === profile?.user.user_id ? "text-xs font-medium text-primary" : "text-xs text-muted-foreground"}>
                          {i.claimed_by.user_id === profile?.user.user_id ? "You are reviewing" : `Being reviewed by ${i.claimed_by.full_name}`}
                        </div>
                      )}
                      {i.last_decision?.comment && (
                        <div className="text-xs text-muted-foreground">
                          {i.last_decision.reviewer.full_name}: “{i.last_decision.comment}”
                        </div>
                      )}
                    </div>
                  ),
                },
                {
                  h: "Action",
                  c: (i) => (
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant={tab === "awaiting" ? "default" : "outline"} onClick={() => onOpen(i.content_item_id)}>
                        {tab === "awaiting" || tab === "ready" ? "Review" : "View"}
                      </Button>
                      {tab === "ready" && <ReleaseButton item={i} basePath={basePath} />}
                    </div>
                  ),
                },
              ]}
            />
            {result.meta.pages > 1 && (
              <nav aria-label="Pages" className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
                <span>
                  Page {result.meta.page} of {result.meta.pages} · {result.meta.total} items
                </span>
                <span className="flex gap-2">
                  <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                    Previous
                  </Button>
                  <Button size="sm" variant="outline" disabled={page >= result.meta.pages} onClick={() => setPage(page + 1)}>
                    Next
                  </Button>
                </span>
              </nav>
            )}
          </>
        )}
      </QueryView>
    </>
  );
}

/** The Branch Manager's content review; the Super Admin and Founder open the same page from their own workspace (`basePath`) and may approve their own uploads. */
export function BranchContent({
  basePath = "/branch/content",
  questionsPath = "/branch/questions",
  moreLink = { to: "/branch/results", label: "Open Marks & results" },
}: {
  basePath?: string;
  questionsPath?: string;
  moreLink?: { to: string; label: string };
}) {
  // The route declares no search schema, so read `?tab=` and `?item=` loosely.
  const search = useSearch({ strict: false }) as { tab?: unknown; item?: unknown };
  const navigate = useNavigate();
  const summary = useQuery({ queryKey: ["content-items", "review-summary"], queryFn: contentReviewApi.summary });
  // The old "Questions to approve" tab became its own page
  if (search.tab === "questions") return <Navigate to={questionsPath as "/branch/questions"} replace />;
  const itemId = Number(search.item) > 0 ? Number(search.item) : null;

  const requested = isTab(search.tab) ? search.tab : null;
  // With no tab in the address, open on the first tab that has work.
  const firstWithWork = summary.data ? (TABS.find((t) => (summary.data[t.key] ?? 0) > 0)?.key ?? "awaiting") : "awaiting";
  const tab: TabKey = requested ?? firstWithWork;
  const waitingForCounts = requested === null && summary.isPending;

  const setSearch = (next: { tab?: TabKey; item?: number | undefined }) =>
    void navigate({ to: basePath as "/branch/content", search: ((prev: Record<string, unknown>) => ({ ...prev, ...next })) as never, replace: true });
  const counts = summary.data
    ? ({
        "To review": summary.data.awaiting,
        "Ready to release": summary.data.ready,
        "Changes requested": summary.data.changes,
        Released: summary.data.released,
      } satisfies Record<TabLabel, number>)
    : undefined;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead
        title="Content review"
        description="Review what trainers send and release it to students. Questions for tests are approved under Question approvals."
      />
      <PillTabs
        label="Content review"
        tabs={LABELS}
        value={TABS.find((t) => t.key === tab)?.label ?? "To review"}
        onChange={(label) => setSearch({ tab: TABS.find((t) => t.label === label)?.key ?? "awaiting", item: undefined })}
        counts={counts}
      />
      {waitingForCounts ? (
        <LoadingSkeleton />
      ) : (
        <ReviewList
          key={tab}
          tab={tab}
          counts={summary.data}
          basePath={basePath}
          moreLink={moreLink}
          onOpen={(id) => setSearch({ item: id })}
          moveTo={(t) => setSearch({ tab: t, item: undefined })}
        />
      )}
      <HowThisWorks>
        <p>Approving a routine resource does not change the syllabus, hours, assessments or completion rules.</p>
        <p>
          Opening a review takes it, so two people do not review the same upload. A Branch Manager cannot review content they uploaded; a Super Admin or the
          Founder can.
        </p>
        <p>"Approve and release later" keeps it in Ready to release until you release it. Students see content only after it is released.</p>
      </HowThisWorks>
      {itemId !== null && <ContentReviewDialog key={itemId} id={itemId} basePath={basePath} onClose={() => setSearch({ item: undefined })} />}
    </div>
  );
}
