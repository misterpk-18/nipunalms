import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { contentApi, CONTENT_TYPES, LINK_TYPES, formatDateTime, type ContentItem } from "@/api/content";
import { DataTable, Note, PageHead, QueryView, StatusBadge } from "@/components/lms/ui";
import { Field, NativeSelect } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";
import { ContentDetailDialog } from "@/features/shared/content-detail";

export function TrainerContent() {
  const query = useQuery({ queryKey: ["content-items", "mine"], queryFn: () => contentApi.items({ per_page: 100 }) });
  const [uploading, setUploading] = useState(false);
  const [versionFor, setVersionFor] = useState<ContentItem | null>(null);
  const [detailId, setDetailId] = useState<number | null>(null);
  const submit = useApiMutation((id: number) => contentApi.submit(id), { success: "Submitted for academic review", invalidate: [["content-items"]] });

  return (
    <div className="mx-auto max-w-6xl">
      <PageHead
        title="Content"
        description="Upload session content and submit it for academic review."
        actions={<Button onClick={() => setUploading(true)}>Upload content</Button>}
      />
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No content yet. Upload a file or add a link for one of your batches.">
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
                  </>
                ),
              },
              { h: "Topic", c: (i) => i.topic?.title ?? i.module?.title ?? i.course.title },
              { h: "Batch", c: (i) => i.batch?.batch_code ?? "Whole course" },
              {
                h: "Review state",
                c: (i) => (
                  <>
                    <StatusBadge>{i.status}</StatusBadge>
                    <div className="text-xs text-muted-foreground">{formatDateTime(i.updated_at)}</div>
                  </>
                ),
              },
              {
                h: "Action",
                c: (i) => (
                  <div className="flex flex-wrap gap-2">
                    {(i.status === "Draft" || i.status === "Changes Requested") && (
                      <Button size="sm" onClick={() => submit.mutate(i.content_item_id)} disabled={submit.isPending}>
                        Submit for review
                      </Button>
                    )}
                    {i.status !== "Submitted" && i.status !== "Under Review" && i.status !== "Retired" && (
                      <Button size="sm" variant="outline" onClick={() => setVersionFor(i)}>
                        New version
                      </Button>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => setDetailId(i.content_item_id)}>
                      Details
                    </Button>
                  </div>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <div className="mt-4">
        <Note>
          Content is published to students only after Academic Coordinator review. A new version does not replace what students see until it is approved and
          released.
        </Note>
      </div>
      {uploading && <UploadDialog onClose={() => setUploading(false)} />}
      {versionFor && <VersionDialog item={versionFor} onClose={() => setVersionFor(null)} />}
      {detailId !== null && <ContentDetailDialog id={detailId} onClose={() => setDetailId(null)} />}
    </div>
  );
}

function UploadDialog({ onClose }: { onClose: () => void }) {
  const options = useQuery({ queryKey: ["content-items", "options"], queryFn: contentApi.options });
  const [batchId, setBatchId] = useState("");
  const [topicKey, setTopicKey] = useState("");
  const [title, setTitle] = useState("");
  const [type, setType] = useState<string>("PDF");
  const [description, setDescription] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [downloadAllowed, setDownloadAllowed] = useState(true);
  const isLink = LINK_TYPES.includes(type);

  const batch = options.data?.find((o) => String(o.batch.batch_id) === batchId);
  const topics = (batch?.versions ?? []).flatMap((v) =>
    v.modules.flatMap((m) => m.topics.map((t) => ({ value: t.topic_id, label: `${v.track_name ?? v.version_label} · ${m.title} · ${t.title}` }))),
  );

  const create = useApiMutation((form: FormData) => contentApi.create(form), {
    success: "Saved as a draft",
    invalidate: [["content-items"]],
    onSuccess: onClose,
  });
  function save() {
    const form = new FormData();
    form.set("title", title.trim());
    form.set("content_type", type);
    form.set("batch_id", batchId);
    if (topicKey) form.set("topic_id", topicKey);
    if (description.trim()) form.set("description", description.trim());
    form.set("download_allowed", String(downloadAllowed && !isLink));
    if (isLink) form.set("url", url.trim());
    else if (file) form.set("file", file);
    create.mutate(form);
  }
  const ready = title.trim() && batchId && (isLink ? url.trim() : file);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Upload content</DialogTitle>
          <DialogDescription>The file is stored in LMS content storage as a draft. Submit it for review when it is ready.</DialogDescription>
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
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!ready || create.isPending} onClick={save}>
            Save draft
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function VersionDialog({ item, onClose }: { item: ContentItem; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [summary, setSummary] = useState("");
  const isLink = item.storage_kind === "Link";
  const add = useApiMutation((form: FormData) => contentApi.addVersion(item.content_item_id, form), {
    success: "New version saved as a draft",
    invalidate: [["content-items"]],
    onSuccess: onClose,
  });
  function save() {
    const form = new FormData();
    if (summary.trim()) form.set("change_summary", summary.trim());
    if (isLink) form.set("url", url.trim());
    else if (file) form.set("file", file);
    add.mutate(form);
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
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={(isLink ? !url.trim() : !file) || add.isPending} onClick={save}>
            Save version
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
