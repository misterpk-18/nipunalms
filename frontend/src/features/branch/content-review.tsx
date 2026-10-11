/** The review of one content item: a preview, who has it open, and the decision. Opening it takes the review. */
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { toast } from "sonner";
import { errorMessage } from "@/api/client";
import { contentApi, contentReviewApi, formatDateTime, openContentFile, type ClaimResult, type ContentItem } from "@/api/content";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { KeyValue, QueryView, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";

import { audienceText, releaseConsequence } from "./content-audience";

const REFRESH = [["content-items"], ["nav"], ["branch"]];

/** A small dialog that asks for a written reason before it acts. Opened from a menu, so it is controlled by its parent. */
export function ReasonPrompt({
  open,
  onOpenChange,
  title,
  description,
  label,
  confirmLabel,
  destructive,
  busy,
  minLength = 3,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  label: string;
  confirmLabel: string;
  destructive?: boolean;
  busy?: boolean;
  minLength?: number;
  onSubmit: (reason: string) => Promise<unknown>;
}) {
  const [reason, setReason] = useState("");
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setReason("");
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="reason-prompt">{label}</Label>
          <Textarea id="reason-prompt" rows={4} value={reason} onChange={(e) => setReason(e.target.value)} />
          {reason.trim().length < minLength && <p className="text-xs text-muted-foreground">Write at least {minLength} characters.</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant={destructive ? "destructive" : "default"}
            disabled={busy || reason.trim().length < minLength}
            onClick={() =>
              void onSubmit(reason.trim()).then(
                () => setReason(""),
                () => undefined, // the mutation already showed the error; keep the box open
              )
            }
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Preview({ item }: { item: ContentItem }) {
  const version = (item.versions ?? []).find((v) => v.version_no === item.version_no);
  const uploader = version?.uploaded_by ?? item.owner;
  const topic = [item.module?.title, item.topic?.title].filter(Boolean).join(" · ");
  return (
    <div className="space-y-3">
      <KeyValue
        items={[
          ["Type", item.content_type],
          ["Version", `v${item.version_no}`],
          ["Uploaded by", `${uploader.full_name}, ${formatDateTime(version?.uploaded_at ?? item.submitted_at)}`],
          ["Topic", topic || item.course.title],
          ["Who will see it", audienceText(item)],
          ["What changed", version?.change_summary || "No summary written."],
          ...(item.description ? ([["About it", item.description]] as [string, string][]) : []),
          ["Downloads", item.download_allowed ? "Students may download it" : "View only"],
        ]}
      />
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/40 px-3 py-2 text-sm">
        {item.storage_kind === "File" ? (
          <>
            <span className="min-w-0 break-words">{item.original_filename ?? "File"}</span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => openContentFile(item.content_item_id, item.original_filename, false).catch((e) => toast.error(errorMessage(e)))}
            >
              Open the file
            </Button>
          </>
        ) : (
          <>
            <span className="min-w-0 break-all">{item.url}</span>
            <Button asChild size="sm" variant="outline">
              <a href={item.url ?? "#"} target="_blank" rel="noreferrer noopener">
                Open the link
              </a>
            </Button>
          </>
        )}
      </div>
      {(item.reviews ?? []).length > 0 && (
        <details className="rounded-lg border px-3 py-2 text-sm">
          <summary className="cursor-pointer font-medium">Earlier decisions ({item.reviews?.length})</summary>
          <ol className="mt-2 space-y-1.5">
            {(item.reviews ?? []).map((r) => (
              <li key={r.review_id}>
                <strong>{r.action}</strong> · v{r.version_no} · {r.actor.full_name} · {formatDateTime(r.acted_at)}
                {r.comment && <div className="text-muted-foreground">“{r.comment}”</div>}
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}

type Prompt = "changes" | "reject" | "retire" | null;

function Decisions({ item, claim, onDone }: { item: ContentItem; claim: ClaimResult | null; onDone: () => void }) {
  const [prompt, setPrompt] = useState<Prompt>(null);
  const awaiting = item.status === "Submitted" || item.status === "Under Review";
  const base = { invalidate: REFRESH, onSuccess: onDone };
  const when = audienceText(item);
  const approveNow = useApiMutation(() => contentApi.review(item.content_item_id, { decision: "approve", release: true }), {
    success: `${item.title} is approved and released`,
    next: `${when} can see it now.`,
    view: { to: "/branch/content", label: "View content" },
    ...base,
  });
  const approveLater = useApiMutation(() => contentApi.review(item.content_item_id, { decision: "approve" }), {
    success: `${item.title} is approved`,
    next: "Students cannot see it yet. Release it from Ready to release when you are ready.",
    view: { to: "/branch/content", label: "View content" },
    ...base,
  });
  const changes = useApiMutation((comment: string) => contentApi.review(item.content_item_id, { decision: "request_changes", comment }), {
    success: "Changes requested",
    next: `${item.owner.full_name} is told and sees your comment.`,
    view: { to: "/branch/content", label: "View content" },
    ...base,
  });
  const reject = useApiMutation((comment: string) => contentApi.review(item.content_item_id, { decision: "reject", comment }), {
    success: "Content rejected",
    next: `${item.owner.full_name} is told and sees your reason.`,
    view: { to: "/branch/content", label: "View content" },
    ...base,
  });
  const release = useApiMutation(() => contentApi.release(item.content_item_id), {
    success: `${item.title} is released`,
    next: `${when} can see it now.`,
    view: { to: "/branch/content", label: "View content" },
    ...base,
  });
  const retire = useApiMutation((reason: string) => contentApi.retire(item.content_item_id, reason), {
    success: `${item.title} is retired`,
    next: "Students can no longer see it. Files and versions are kept.",
    ...base,
  });
  const busy = approveNow.isPending || approveLater.isPending || changes.isPending || reject.isPending || release.isPending || retire.isPending;

  const more = (label: string, which: Exclude<Prompt, null>) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" disabled={busy}>
          More <ChevronDown className="size-4" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem className="text-destructive" onSelect={() => setPrompt(which)}>
          {label}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  return (
    <>
      <DialogFooter className="gap-2 sm:justify-start">
        {awaiting && claim?.can_decide && (
          <>
            <ConfirmDialog
              title={`Approve and release “${item.title}”?`}
              consequence={releaseConsequence(item)}
              confirmLabel="Approve & release"
              onConfirm={() => approveNow.mutateAsync(undefined)}
            >
              <Button disabled={busy}>Approve &amp; release</Button>
            </ConfirmDialog>
            <Button variant="secondary" disabled={busy} onClick={() => approveLater.mutate(undefined)}>
              Approve and release later
            </Button>
            <Button variant="outline" disabled={busy} onClick={() => setPrompt("changes")}>
              Request changes
            </Button>
            {more("Reject", "reject")}
          </>
        )}
        {item.status === "Approved" && (
          <ConfirmDialog
            title={`Release “${item.title}”?`}
            consequence={releaseConsequence(item)}
            confirmLabel="Release"
            onConfirm={() => release.mutateAsync(undefined)}
          >
            <Button disabled={busy}>Release</Button>
          </ConfirmDialog>
        )}
        {item.status === "Released" && more("Retire", "retire")}
      </DialogFooter>
      <ReasonPrompt
        open={prompt === "changes"}
        onOpenChange={(o) => !o && setPrompt(null)}
        title="Request changes"
        description={`${item.owner.full_name} will see your comment and can send a new version.`}
        label="What should be changed?"
        confirmLabel="Send request"
        busy={busy}
        onSubmit={(reason) => changes.mutateAsync(reason)}
      />
      <ReasonPrompt
        open={prompt === "reject"}
        onOpenChange={(o) => !o && setPrompt(null)}
        title="Reject this content?"
        description="It is not accepted. The trainer sees your reason."
        label="Why is it rejected?"
        confirmLabel="Reject"
        destructive
        busy={busy}
        onSubmit={(reason) => reject.mutateAsync(reason)}
      />
      <ReasonPrompt
        open={prompt === "retire"}
        onOpenChange={(o) => !o && setPrompt(null)}
        title="Retire this content?"
        description="Students lose access straight away. Files and versions are kept."
        label="Why is it being retired?"
        confirmLabel="Retire"
        destructive
        busy={busy}
        onSubmit={(reason) => retire.mutateAsync(reason)}
      />
    </>
  );
}

/** The claim line: who has the review open. */
function ClaimLine({ claim, error, waiting }: { claim: ClaimResult | null; error: string | null; waiting: boolean }) {
  if (error)
    return (
      <StatusNote tone="danger" title="Could not open this for review.">
        {error}
      </StatusNote>
    );
  if (waiting && !claim) return <p className="text-sm text-muted-foreground">Opening the review…</p>;
  if (!claim) return null;
  if (!claim.can_decide && claim.reason)
    return (
      <StatusNote tone="warning" title="You cannot decide on this one.">
        {claim.reason}
      </StatusNote>
    );
  if (claim.claimed_by_me) return <p className="text-sm font-medium text-primary">You are reviewing this.</p>;
  return null;
}

export function ContentReviewDialog({ id, onClose }: { id: number; onClose: () => void }) {
  const queryClient = useQueryClient();
  const detail = useQuery({ queryKey: ["content-items", "detail", id], queryFn: () => contentApi.item(id) });
  const [claim, setClaim] = useState<ClaimResult | null>(null);
  const [claimError, setClaimError] = useState<string | null>(null);
  const claimedFor = useRef<number | null>(null);
  const awaiting = detail.data?.status === "Submitted" || detail.data?.status === "Under Review";

  // Opening the review takes it, once. The answer says who has it and whether this person may decide.
  useEffect(() => {
    if (!awaiting || claimedFor.current === id) return;
    claimedFor.current = id;
    contentReviewApi.claim(id).then(
      (result) => {
        setClaim(result);
        void queryClient.invalidateQueries({ queryKey: ["content-items"] });
      },
      (error: unknown) => setClaimError(errorMessage(error)),
    );
  }, [awaiting, id, queryClient]);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <QueryView query={detail} skeleton="detail">
          {(item) => (
            <>
              <DialogHeader>
                <DialogTitle>{item.title}</DialogTitle>
                <DialogDescription asChild>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs">{item.item_code}</span>
                    <StatusBadge domain="content" code={item.status} />
                  </div>
                </DialogDescription>
              </DialogHeader>
              <ClaimLine claim={claim} error={claimError} waiting={awaiting} />
              <Preview item={item} />
              <Decisions item={item} claim={claim} onDone={onClose} />
            </>
          )}
        </QueryView>
      </DialogContent>
    </Dialog>
  );
}
