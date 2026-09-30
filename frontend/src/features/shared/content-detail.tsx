/** Detail dialog of a content item: placement, versions and the review history (trainer and academic screens). */
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { contentApi, formatDateTime, openContentFile } from "@/api/content";
import { errorMessage } from "@/api/client";
import { KeyValue, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export function ContentDetailDialog({ id, onClose }: { id: number; onClose: () => void }) {
  const query = useQuery({ queryKey: ["content-items", "detail", id], queryFn: () => contentApi.item(id) });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <QueryView query={query}>
          {(item) => (
            <>
              <DialogHeader>
                <DialogTitle>{item.title}</DialogTitle>
                <DialogDescription>
                  {item.item_code} · {item.content_type} · <StatusBadge>{item.status}</StatusBadge>
                </DialogDescription>
              </DialogHeader>
              <KeyValue
                items={[
                  ["Course", item.course.title],
                  ["Curriculum version", item.curriculum_version?.version_label ?? "Any version"],
                  ["Module · Topic", [item.module?.title, item.topic?.title].filter(Boolean).join(" · ") || "—"],
                  ["Audience", item.batch ? `Batch ${item.batch.batch_code}` : `All ${item.course.course_code} students at ${item.branch.branch_name}`],
                  ["Author", item.owner.full_name],
                  ["Downloads", item.download_allowed ? "Allowed" : "View only"],
                ]}
              />
              <h3 className="mt-2 text-sm font-semibold">Versions</h3>
              <ul className="space-y-2 text-sm">
                {(item.versions ?? []).map((v) => (
                  <li key={v.content_version_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-2">
                    <div>
                      <strong>v{v.version_no}</strong> {v.original_filename ?? v.url} <StatusBadge>{v.status}</StatusBadge>
                      <div className="text-xs text-muted-foreground">
                        {v.uploaded_by.full_name} · {formatDateTime(v.uploaded_at)}
                        {v.change_summary && ` · ${v.change_summary}`}
                      </div>
                    </div>
                    {v.storage_kind === "File" ? (
                      v.version_no === item.version_no && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => openContentFile(id, v.original_filename, false).catch((e) => toast.error(errorMessage(e)))}
                        >
                          Preview
                        </Button>
                      )
                    ) : (
                      <a className="text-sm underline" href={v.url ?? "#"} target="_blank" rel="noreferrer noopener">
                        Open link
                      </a>
                    )}
                  </li>
                ))}
              </ul>
              <h3 className="mt-2 text-sm font-semibold">Review history</h3>
              {(item.reviews ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">Not submitted yet.</p>
              ) : (
                <ol className="space-y-1.5 text-sm">
                  {(item.reviews ?? []).map((r) => (
                    <li key={r.review_id} className="rounded-lg border p-2">
                      <strong>{r.action}</strong> · v{r.version_no} · {r.actor.full_name} · {formatDateTime(r.acted_at)}
                      {r.comment && <div className="text-muted-foreground">“{r.comment}”</div>}
                    </li>
                  ))}
                </ol>
              )}
            </>
          )}
        </QueryView>
      </DialogContent>
    </Dialog>
  );
}
