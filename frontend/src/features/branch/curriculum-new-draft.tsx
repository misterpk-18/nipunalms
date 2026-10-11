/** New draft: the server names it and copies the Active version unless you choose to start empty. */
import { useState } from "react";
import { curriculumApi } from "@/api/curriculum";
import type { CurriculumVersion } from "@/api/delivery";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useCurriculumMutation } from "./curriculum-pickers";

/** What the server will call the next draft: the Active (else newest) name with its last number raised, or "Version 1". */
export function suggestDraftName(versions: CurriculumVersion[]): string {
  if (versions.length === 0) return "Version 1";
  const taken = new Set(versions.map((v) => v.version_label));
  const base = versions.find((v) => v.status === "Active") ?? versions.reduce((a, b) => (b.curriculum_version_id > a.curriculum_version_id ? b : a));
  const match = /^(.*?)(\d+)$/.exec(base.version_label.trim());
  if (!match) {
    let n = 2;
    while (taken.has(`${base.version_label} (${n})`)) n += 1;
    return `${base.version_label} (${n})`;
  }
  const prefix = match[1]!;
  let n = Number(match[2]);
  while (taken.has(`${prefix}${n + 1}`)) n += 1;
  return `${prefix}${n + 1}`;
}

export function NewDraftDialog({
  courseId,
  componentId,
  versions,
  onCreated,
}: {
  courseId: number;
  componentId: number | null;
  versions: CurriculumVersion[];
  onCreated: (versionId: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const [empty, setEmpty] = useState(false);
  const active = versions.find((v) => v.status === "Active");
  const inProgress = versions.find((v) => v.status === "Draft" || v.status === "Under Review");
  const create = useCurriculumMutation(
    () => curriculumApi.createDraft({ course_id: courseId, component_id: componentId, ...(empty || !active ? { blank: true } : {}) }),
    (made) => `Draft ${made.version_label} created`,
    { next: "Work through the checklist, then submit it for review." },
  );
  if (inProgress)
    return (
      <p className="text-sm text-muted-foreground">
        {inProgress.version_label} is {inProgress.status === "Draft" ? "still a draft" : "under review"}. Finish or return it before starting another.
      </p>
    );
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next) setEmpty(false);
        setOpen(next);
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">New draft</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New draft</DialogTitle>
          <DialogDescription>
            {active && !empty
              ? `Start from the current Active version (${active.version_label}). Its modules, topics and rules are copied, so you only change what is new.`
              : active
                ? "The draft will be empty. You will add every module and topic yourself."
                : "There is no Active version yet, so the draft starts empty."}
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={async (event) => {
            event.preventDefault();
            try {
              const made = await create.mutateAsync(undefined);
              setOpen(false);
              onCreated(made.curriculum_version_id);
            } catch {
              /* the mutation already showed the reason */
            }
          }}
        >
          {active && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={empty} onChange={(e) => setEmpty(e.target.checked)} />
              Start empty instead
            </label>
          )}
          <p className="text-sm text-muted-foreground">
            The draft is named for you: <strong className="text-foreground">{suggestDraftName(versions)}</strong>. You can rename it later.
          </p>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              Create draft
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
