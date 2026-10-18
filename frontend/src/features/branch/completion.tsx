/** Completion & certificates: one pipeline from "decide whether the course is complete" to "the certificate is issued". */
import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { certificatesApi } from "@/api/certificates";
import { completionPipelineApi, PIPELINE_STAGES, STAGE_LABELS, type PipelineRow, type PipelineStage } from "@/api/completion-pipeline";
import { useAuth } from "@/auth/auth";
import { EmptyState } from "@/components/lms/empty-state";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { LoadingSkeleton, PageHead, PillTabs, StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { fmtDate } from "@/features/shared/format";
import { ApprovalsInbox } from "@/features/shared/approvals/inbox";
import { useFounderInbox } from "@/api/founder";
import { ApproveButtons, DecideButton, IssueButton, MoreActions } from "./completion-actions";
import { rupees } from "./completion-format";
import { EvidenceList } from "./completion-evidence";

const PER_PAGE = 20;
const isStage = (v: unknown): v is PipelineStage => typeof v === "string" && (PIPELINE_STAGES as readonly string[]).includes(v);

/** Words for a row that nobody in this list can act on. */
const NO_ACTION: Record<PipelineStage, string> = {
  ready: "Only the Branch Manager of this branch decides this.",
  completed: "Waiting for the Branch Manager of this branch to approve it.",
  fee: "",
  issue: "Waiting for the Branch Manager of this branch to issue it.",
  issued: "",
};

function feeLine(row: PipelineRow): string {
  const fee = row.fee;
  if (!fee) return "The fee status is not known yet.";
  if (fee.state === "Outstanding") return `Fee not cleared: ${rupees(fee.balance)} still to pay`;
  if (fee.state === "Not Received") return "Fee not cleared: the fee status has not arrived from the CRM yet";
  return `Fee not cleared (${fee.state})`;
}

function RowBody({ row }: { row: PipelineRow }) {
  const cert = row.certificate;
  const trainerOk = row.evidence?.checks.find((c) => c.key === "trainer")?.ok;
  return (
    <>
      {row.stage === "ready" && row.review?.trainer_comment && (
        <p className="mt-2 text-sm text-muted-foreground">
          Trainer's note{row.review.recommended_by ? ` (${row.review.recommended_by})` : ""}: {row.review.trainer_comment}
        </p>
      )}
      {row.evidence && (
        <div className="mt-3">
          <EvidenceList checks={row.evidence.checks} />
        </div>
      )}
      {row.stage === "ready" && trainerOk === false && (
        <p className="mt-2 text-sm text-warning">
          The trainer has not recommended Complete yet. Complete will not be accepted until they do; you can still choose Not yet complete or Needs recovery.
        </p>
      )}
      {row.stage === "fee" && (
        <p className="mt-2 text-sm" role="status">
          {feeLine(row)}
        </p>
      )}
      {row.stage === "issued" && cert && (
        <p className="mt-2 text-sm text-muted-foreground">
          {cert.number ? (
            <>
              Certificate{" "}
              <Link to="/verify/$number" params={{ number: cert.number }} className="font-mono text-primary underline-offset-2 hover:underline">
                {cert.number}
              </Link>
            </>
          ) : (
            "Certificate"
          )}
          {` · version ${cert.version}`}
          {cert.issue_date ? ` · issued ${fmtDate(cert.issue_date)}` : ""}
          {cert.number && (
            <>
              {" · "}
              <Link to="/verify/$number" params={{ number: cert.number }} className="text-primary underline-offset-2 hover:underline">
                Open the verification page
              </Link>
            </>
          )}
        </p>
      )}
    </>
  );
}

function RowActions({ row }: { row: PipelineRow }) {
  const cert = row.certificate;
  const buttons: ReactNode[] = [];
  if (row.stage === "ready" && (row.actions.includes("decide") || row.actions.includes("start_review"))) buttons.push(<DecideButton key="decide" row={row} />);
  if (row.stage === "completed" && cert) buttons.push(<ApproveButtons key="approve" row={row} />);
  if (row.stage === "issue" && row.actions.includes("issue")) buttons.push(<IssueButton key="issue" row={row} />);
  const hasAction = buttons.length > 0;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      {buttons}
      {cert?.pending_request && <Tag tone="warning">A change request is waiting for a decision</Tag>}
      {!hasAction && !cert?.pending_request && NO_ACTION[row.stage] && row.actions.length === 0 && (
        <span className="text-sm text-muted-foreground">{NO_ACTION[row.stage]}</span>
      )}
      <span className="ml-auto">
        <MoreActions row={row} />
      </span>
    </div>
  );
}

function PipelineCard({ row }: { row: PipelineRow }) {
  const cert = row.certificate;
  const batch = row.batch ? (row.batch.display_name ?? row.batch.batch_code) : null;
  return (
    <li className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium">
            {row.student.full_name} <span className="font-mono text-xs text-muted-foreground">{row.student.student_code}</span>
          </p>
          <p className="text-sm text-muted-foreground">
            {row.enrolment.course.title}
            {batch ? ` · ${batch}` : " · no batch"}
            {row.since ? ` · since ${fmtDate(row.since)}` : ""}
          </p>
        </div>
        {cert && <StatusBadge domain="certificate" code={cert.status} />}
        {!cert && row.stage === "ready" && (
          <StatusBadge domain="completion" code={row.review ? "Review open" : "Open"} label={row.review ? undefined : "Evidence complete"} />
        )}
      </div>
      <RowBody row={row} />
      <RowActions row={row} />
    </li>
  );
}

function Pager({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (p: number) => void }) {
  return (
    <nav aria-label="Pages" className="flex flex-wrap items-center justify-between gap-2 text-sm">
      <span className="text-muted-foreground">
        Page {page} of {Math.max(pages, 1)} · {total} student{total === 1 ? "" : "s"}
      </span>
      <span className="flex gap-2">
        <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </Button>
        <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </Button>
      </span>
    </nav>
  );
}

/** Certificate changes and fee releases waiting for a decision, folded away so nothing that used to be reachable is lost. */
function RequestsSection() {
  const waiting = useFounderInbox("certificates").data?.counts.certificate ?? 0;
  return (
    <Collapsible className="rounded-xl border bg-card px-4 py-3">
      <CollapsibleTrigger className="group flex w-full items-center justify-between gap-2 text-left text-sm font-medium">
        <span>
          Certificate requests
          {waiting > 0 && <span className="ml-2 rounded-full bg-primary/10 px-1.5 text-xs text-primary">{waiting}</span>}
          <span className="block text-xs font-normal text-muted-foreground">
            Certificate corrections, revocations and reinstatements, and who decides them.
          </span>
        </span>
        <ChevronDown className="size-4 shrink-0 transition-transform group-data-[state=open]:rotate-180" aria-hidden />
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-3">
        <ApprovalsInbox
          page="/branch/completion"
          group="certificates"
          kinds={["certificate"]}
          title="Certificate requests"
          empty="No certificate request is waiting for a decision."
        />
      </CollapsibleContent>
    </Collapsible>
  );
}

export function BranchCompletion() {
  const { branchId } = useAuth();
  const search = useSearch({ strict: false }) as { stage?: unknown };
  const navigate = useNavigate();
  const urlStage = isStage(search.stage) ? search.stage : undefined;
  const stage = urlStage ?? "ready";
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 300);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => setPage(1), [stage, debounced, branchId]);

  const query = useQuery({
    queryKey: ["completion", "pipeline", { stage, q: debounced, branchId, page }],
    queryFn: () => completionPipelineApi.list({ stage, q: debounced || undefined, branch_id: branchId ?? undefined, page, per_page: PER_PAGE }),
    placeholderData: keepPreviousData,
  });
  const meta = query.data?.meta;
  const counts = meta?.counts;

  const setStage = (next: PipelineStage, replace = false) =>
    void navigate({ to: ".", search: ((prev: Record<string, unknown>) => ({ ...prev, stage: next })) as never, replace });

  // With no stage in the address, open the first stage that has people in it when "Ready to decide" is empty.
  useEffect(() => {
    if (urlStage || !counts || counts.ready > 0 || debounced) return;
    const first = PIPELINE_STAGES.find((s) => counts[s] > 0);
    if (first && first !== "ready") setStage(first, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlStage, counts, debounced]);

  const empty = (): ReactNode => {
    if (debounced)
      return (
        <EmptyState
          reason="No student matches that search in this stage."
          action={
            <Button size="sm" variant="outline" onClick={() => setQ("")}>
              Clear the search
            </Button>
          }
        />
      );
    const go = (to: PipelineStage) => (
      <Button size="sm" variant="outline" onClick={() => setStage(to)}>
        Open {STAGE_LABELS[to]}
      </Button>
    );
    switch (stage) {
      case "ready":
        return (
          <EmptyState
            reason="Nobody is ready for a completion decision. A student appears here when the trainer asks for a review or the course evidence is complete."
            action={
              <Button asChild size="sm" variant="outline">
                <Link to="/branch/progress">Open Attendance & progress</Link>
              </Button>
            }
          />
        );
      case "completed":
        return <EmptyState reason="No certificate is waiting for your approval." action={go("ready")} />;
      case "fee":
        return <EmptyState reason="Nobody is waiting for a fee." action={go("issue")} />;
      case "issue":
        return <EmptyState reason="No certificate is ready to issue." action={go("completed")} />;
      default:
        return <EmptyState reason="No certificate has been issued yet." action={go("issue")} />;
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead title="Completion & certificates" description="Decide whether a student has completed the course, then approve and issue the certificate." />
      <div>
        <PillTabs label="Stage" tabs={PIPELINE_STAGES} value={stage} onChange={(s) => setStage(s)} labels={STAGE_LABELS} counts={counts} />
        <Input
          className="max-w-sm"
          aria-label="Search students"
          placeholder="Search by student name or Student ID"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      {query.isPending || query.isPlaceholderData ? (
        <LoadingSkeleton kind="cards" />
      ) : query.isError ? (
        <StatusNote tone="danger" title="Could not load this.">
          Something went wrong.{" "}
          <button className="underline" onClick={() => void query.refetch()}>
            Try again
          </button>
        </StatusNote>
      ) : query.data.data.length === 0 ? (
        empty()
      ) : (
        <>
          <ul className="space-y-3" aria-label={STAGE_LABELS[stage]}>
            {query.data.data.map((row) => (
              <PipelineCard key={row.key} row={row} />
            ))}
          </ul>
          {query.data.meta.pages > 1 && <Pager page={query.data.meta.page} pages={query.data.meta.pages} total={query.data.meta.total} onPage={setPage} />}
        </>
      )}
      <RequestsSection />
      <HowThisWorks>
        <p>
          <strong>Ready to decide:</strong> the course evidence is in (or the trainer asked for a review). You decide: Complete, Not yet complete, or Needs
          recovery.
        </p>
        <p>
          <strong>Completed:</strong> the course is complete and the certificate waits for your approval. <strong>Waiting for fee:</strong> the student's fee is
          not cleared, so the certificate cannot go on. <strong>Ready to issue:</strong> approved and fee cleared. <strong>Issued:</strong> the student has the
          certificate.
        </p>
        <p>
          The Branch Manager decides, but the trainer's Complete recommendation is needed first. Each check is shown against the course's own threshold, never
          as one score.
        </p>
        <p>Corrections, revocations and fee releases are rare. They are under "More" on a row, and someone else decides them.</p>
      </HowThisWorks>
    </div>
  );
}
