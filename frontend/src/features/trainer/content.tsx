import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { contentApi, CONTENT_TYPES, LINK_TYPES, formatDateTime, type ContentItem } from "@/api/content";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { DataTable, PageHead, QueryView, StatusBadge } from "@/components/lms/ui";
import { Field, NativeSelect } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { fmtDate } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { ContentDetailDialog } from "@/features/shared/content-detail";

/** What the status filter offers: plain words, each one a set of the item's statuses. */
const STATUS_FILTERS = {
  "": "All",
  Draft: "Draft",
  "Submitted,Under Review": "Waiting for review",
  "Changes Requested": "Changes requested",
  "Approved,Released": "Approved or released",
  Rejected: "Rejected",
} as const;

/** The trainer's uploads. With `reviewPath` it is the Super Admin's / Founder's content page: any batch, and they approve and release it themselves there. */
export function TrainerContent({ basePath = "/trainer/content", reviewPath }: { basePath?: string; reviewPath?: string }) {
  const { batch } = useSearch({ strict: false }) as { batch?: number };
  const navigate = useNavigate();
  const [status, setStatus] = useState<keyof typeof STATUS_FILTERS>("");
  const query = useQuery({
    queryKey: ["content-items", "mine", batch ?? null, status],
    queryFn: () => contentApi.items({ per_page: 100, ...(batch ? { batch_id: batch } : {}), ...(status ? { status } : {}) }),
  });
  const options = useQuery({ queryKey: ["content-items", "options"], queryFn: contentApi.options });
  const [uploading, setUploading] = useState(false);
  const [versionFor, setVersionFor] = useState<ContentItem | null>(null);
  const [detailId, setDetailId] = useState<number | null>(null);
  const submit = useApiMutation((id: number) => contentApi.submit(id), {
    success: (item) => `${item.title} sent for review`,
    next: reviewPath ? "Approve and release it under Content review." : "Your Branch Manager reviews it. You are told when they decide.",
    invalidate: [["content-items"]],
  });
  const filtered = Boolean(batch) || status !== "";

  return (
    <div className="mx-auto max-w-6xl">
      <PageHead
        title="Content"
        description={
          reviewPath
            ? "Upload notes, files and links for any batch. Send them for review, then approve and release them under Content review."
            : "Upload notes, files and links for your batches and send them to your Branch Manager for review."
        }
        actions={<Button onClick={() => setUploading(true)}>Upload content</Button>}
      />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="w-full sm:w-56">
          <Label htmlFor="content-filter-batch">Batch</Label>
          <NativeSelect
            id="content-filter-batch"
            placeholder={reviewPath ? "All batches" : "All my batches"}
            value={batch ?? ""}
            onChange={(e) => void navigate({ to: basePath as "/trainer/content", search: (e.target.value ? { batch: Number(e.target.value) } : {}) as never })}
            options={(options.data ?? []).map((o) => ({ value: o.batch.batch_id, label: o.batch.batch_code }))}
          />
        </div>
        <div className="w-full sm:w-56">
          <Label htmlFor="content-filter-status">Status</Label>
          <NativeSelect
            id="content-filter-status"
            value={status}
            onChange={(e) => setStatus(e.target.value as keyof typeof STATUS_FILTERS)}
            options={Object.entries(STATUS_FILTERS).map(([value, label]) => ({ value, label }))}
          />
        </div>
      </div>
      <QueryView
        query={query}
        isEmpty={(page) => page.data.length === 0}
        empty={filtered ? "No content matches these filters." : "No content yet. Upload a file or add a link for one of your batches, then send it for review."}
        emptyAction={
          filtered ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setStatus("");
                void navigate({ to: basePath as "/trainer/content", search: {} as never });
              }}
            >
              Clear filters
            </Button>
          ) : (
            <Button size="sm" onClick={() => setUploading(true)}>
              Upload content
            </Button>
          )
        }
      >
        {(page) => (
          <DataTable
            caption="Content"
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
                      {i.released_version_no && i.released_version_no !== i.version_no && ` (students see v${i.released_version_no})`}
                    </div>
                    {i.last_decision?.comment && (
                      <div className="mt-1.5 rounded-md border border-warning/30 bg-warning-soft px-2 py-1.5 text-xs text-foreground">
                        <strong>
                          {i.last_decision.reviewer.full_name} {i.last_decision.action === "Rejected" ? "did not accept this" : "asked for changes"}:
                        </strong>{" "}
                        {i.last_decision.comment}
                      </div>
                    )}
                  </>
                ),
              },
              { h: "Topic", c: (i) => i.topic?.title ?? i.module?.title ?? i.course.title },
              { h: "Batch", c: (i) => i.batch?.batch_code ?? "Whole course" },
              {
                h: "Review state",
                c: (i) => (
                  <>
                    <StatusBadge domain="content" code={i.status} />
                    <div className="text-xs text-muted-foreground">{fmtDate(i.updated_at)}</div>
                  </>
                ),
              },
              {
                h: "Action",
                c: (i) => {
                  const canChange = i.status !== "Submitted" && i.status !== "Under Review" && i.status !== "Retired";
                  return (
                    <div className="flex flex-wrap gap-2">
                      {i.status === "Draft" && (
                        <Button size="sm" onClick={() => submit.mutate(i.content_item_id)} disabled={submit.isPending}>
                          Submit for review
                        </Button>
                      )}
                      {i.status === "Changes Requested" && (
                        <Button size="sm" onClick={() => setVersionFor(i)}>
                          Fix and resubmit
                        </Button>
                      )}
                      {canChange && i.status !== "Changes Requested" && (
                        <Button size="sm" variant="outline" onClick={() => setVersionFor(i)}>
                          New version
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" onClick={() => setDetailId(i.content_item_id)}>
                        Details
                      </Button>
                    </div>
                  );
                },
              },
            ]}
          />
        )}
      </QueryView>
      <div className="mt-4">
        <HowThisWorks>
          <p>
            Students see content only after it is approved and released
            {reviewPath ? (
              <>
                {" "}
                under{" "}
                <Link to={reviewPath as "/branch/content"} className="underline">
                  Content review
                </Link>
                , where you can approve your own uploads
              </>
            ) : (
              " by your Branch Manager"
            )}
            . A new version does not replace what students see until it is approved and released. When changes are requested, the reviewer&apos;s comment shows
            on the item: upload a corrected version and send it again.
          </p>
        </HowThisWorks>
      </div>
      {uploading && <UploadDialog selfReview={Boolean(reviewPath)} onClose={() => setUploading(false)} />}
      {versionFor && <VersionDialog item={versionFor} selfReview={Boolean(reviewPath)} onClose={() => setVersionFor(null)} />}
      {detailId !== null && <ContentDetailDialog id={detailId} onClose={() => setDetailId(null)} />}
    </div>
  );
}

function UploadDialog({ onClose, selfReview }: { onClose: () => void; selfReview: boolean }) {
  const options = useQuery({ queryKey: ["content-items", "options"], queryFn: contentApi.options });
  const [batchId, setBatchId] = useState("");
  const [topicKey, setTopicKey] = useState("");
  const [title, setTitle] = useState("");
  const [type, setType] = useState<string>("PDF");
  const [description, setDescription] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [downloadAllowed, setDownloadAllowed] = useState(true);
  const [staffOnly, setStaffOnly] = useState(false);
  const isLink = LINK_TYPES.includes(type);

  const batch = options.data?.find((o) => String(o.batch.batch_id) === batchId);
  const topics = (batch?.outlines ?? []).flatMap((o) =>
    o.modules.flatMap((m) => m.topics.map((t) => ({ value: t.topic_id, label: `${o.track_name ? `${o.track_name} · ` : ""}${m.title} · ${t.title}` }))),
  );

  const create = useApiMutation(
    async (vars: { form: FormData; submit: boolean }) => {
      const item = await contentApi.create(vars.form);
      return vars.submit ? contentApi.submit(item.content_item_id) : item;
    },
    {
      success: (item) => (item.status === "Submitted" ? `${item.title} sent for review` : "Saved as a draft"),
      next: (item) =>
        item.status === "Submitted"
          ? selfReview
            ? "Approve and release it under Content review."
            : "Your Branch Manager reviews it. You are told when they decide."
          : "Send it for review when it is ready.",
      invalidate: [["content-items"]],
      onSuccess: onClose,
    },
  );
  function save(submit: boolean) {
    const form = new FormData();
    form.set("title", title.trim());
    form.set("content_type", type);
    form.set("batch_id", batchId);
    if (topicKey) form.set("topic_id", topicKey);
    else if (batch) form.set("course_id", String(batch.course.course_id)); // no topic: the item belongs to the whole course
    if (description.trim()) form.set("description", description.trim());
    form.set("download_allowed", String(downloadAllowed && !isLink));
    form.set("staff_only", String(staffOnly));
    if (isLink) form.set("url", url.trim());
    else if (file) form.set("file", file);
    create.mutate({ form, submit });
  }
  const ready = title.trim() && batchId && (isLink ? url.trim() : file);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Upload content</DialogTitle>
          <DialogDescription>
            {selfReview ? "Save it as a draft, or send it for review." : "Save it as a draft, or send it straight to your Branch Manager for review."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Field label="Batch" htmlFor="content-batch">
            <NativeSelect
              id="content-batch"
              value={batchId}
              onChange={(e) => {
                setBatchId(e.target.value);
                setTopicKey("");
              }}
              placeholder="Choose a batch"
              options={(options.data ?? []).map((o) => ({ value: o.batch.batch_id, label: `${o.batch.batch_code} · ${o.course.title}` }))}
            />
          </Field>
          <Field label="Topic" htmlFor="content-topic" hint="Optional: leave empty to attach to the whole course.">
            <NativeSelect
              id="content-topic"
              value={topicKey}
              onChange={(e) => setTopicKey(e.target.value)}
              placeholder="No specific topic"
              options={topics}
              disabled={!batchId}
            />
          </Field>
          <Field label="Title" htmlFor="content-title">
            <Input id="content-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
          </Field>
          <Field label="Type" htmlFor="content-type">
            <NativeSelect
              id="content-type"
              value={type}
              onChange={(e) => setType(e.target.value)}
              options={CONTENT_TYPES.map((c) => ({ value: c, label: c }))}
            />
          </Field>
          {isLink ? (
            <Field label="Link address" htmlFor="content-url">
              <Input id="content-url" type="url" placeholder="https://" value={url} onChange={(e) => setUrl(e.target.value)} />
            </Field>
          ) : (
            <Field label="File" htmlFor="content-file" hint="Up to 50 MB (250 MB for datasets and archives).">
              <Input id="content-file" type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </Field>
          )}
          <Field label="Description" htmlFor="content-description">
            <Textarea id="content-description" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          {!isLink && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={downloadAllowed} onChange={(e) => setDownloadAllowed(e.target.checked)} /> Students may download this file
            </label>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={staffOnly} onChange={(e) => setStaffOnly(e.target.checked)} /> Staff only (answer key, marking guide or trainer
            notes): never shown to students
          </label>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="outline" disabled={!ready || create.isPending} onClick={() => save(false)}>
            Save draft
          </Button>
          <Button disabled={!ready || create.isPending} onClick={() => save(true)}>
            Save &amp; submit for review
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function VersionDialog({ item, onClose, selfReview }: { item: ContentItem; onClose: () => void; selfReview: boolean }) {
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [summary, setSummary] = useState("");
  const isLink = item.storage_kind === "Link";
  const add = useApiMutation(
    async (vars: { form: FormData; submit: boolean }) => {
      const saved = await contentApi.addVersion(item.content_item_id, vars.form);
      return vars.submit ? contentApi.submit(saved.content_item_id) : saved;
    },
    {
      success: (saved) => (saved.status === "Submitted" ? `${saved.title} sent for review` : "New version saved as a draft"),
      next: (saved) =>
        saved.status === "Submitted"
          ? selfReview
            ? "Approve and release it under Content review."
            : "Your Branch Manager reviews it. You are told when they decide."
          : "Send it for review when it is ready.",
      invalidate: [["content-items"]],
      onSuccess: onClose,
    },
  );
  function save(submit: boolean) {
    const form = new FormData();
    if (summary.trim()) form.set("change_summary", summary.trim());
    if (isLink) form.set("url", url.trim());
    else if (file) form.set("file", file);
    add.mutate({ form, submit });
  }
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New version of {item.title}</DialogTitle>
          <DialogDescription>Earlier versions are kept. Students keep seeing the released version until this one is approved and released.</DialogDescription>
        </DialogHeader>
        {isLink ? (
          <Field label="Link address" htmlFor="version-url">
            <Input id="version-url" type="url" value={url} onChange={(e) => setUrl(e.target.value)} />
          </Field>
        ) : (
          <Field label="File" htmlFor="version-file">
            <Input id="version-file" type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </Field>
        )}
        <Field label="What changed?" htmlFor="version-summary">
          <Input id="version-summary" value={summary} onChange={(e) => setSummary(e.target.value)} />
        </Field>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="outline" disabled={(isLink ? !url.trim() : !file) || add.isPending} onClick={() => save(false)}>
            Save draft
          </Button>
          <Button disabled={(isLink ? !url.trim() : !file) || add.isPending} onClick={() => save(true)}>
            Save &amp; submit for review
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
