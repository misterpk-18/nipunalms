/** Curriculum: what changes, who is affected, and Approve & activate (or Return). A version already approved and not yet active has Activate. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { founderApi, type CurriculumDetail, type CurriculumImpact } from "@/api/founder";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { Field } from "@/components/lms/forms";
import { LoadingSkeleton, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { fmtDate, fmtDateTime } from "@/features/shared/format";
import { ReasonDialog } from "@/features/shared/reason-dialog";
import { useApiMutation } from "@/lib/mutation";
import { PanelFrame, PanelPart } from "./panel-frame";

const INVALIDATE = [["founder"], ["nav"], ["delivery"], ["curriculum"], ["dashboard"]];
const istDate = (offsetDays = 0) => new Date(Date.now() + offsetDays * 86_400_000).toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
const hours = (minutes: number) => `${Math.round((minutes / 60) * 10) / 10} hours`;

type When = "now" | "day" | "later";

/** The choice that goes with approving: activate straight away, on a day, or leave it approved. */
function ApproveDialog({ impact, busy, onApprove }: { impact: CurriculumImpact; busy: boolean; onApprove: (activateOn?: string) => Promise<unknown> }) {
  const [open, setOpen] = useState(false);
  const [when, setWhen] = useState<When>("now");
  const [day, setDay] = useState("");
  const options: [When, string][] = [
    ["now", "Activate it now"],
    ["day", "Activate it on a day I choose"],
    ["later", "Only approve it. I will activate it later"],
  ];
  const confirmLabel = { now: "Approve & activate", day: "Approve and schedule", later: "Approve only" }[when];
  const submit = async () => {
    try {
      await onApprove(when === "now" ? istDate() : when === "day" ? day : undefined);
      setOpen(false);
    } catch {
      /* the mutation already showed the message */
    }
  };
  return (
    <>
      <Button disabled={busy} className="min-w-28" onClick={() => setOpen(true)}>
        Approve
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve {impact.version_label}?</DialogTitle>
            <DialogDescription>Choose when it becomes the curriculum in use.</DialogDescription>
          </DialogHeader>
          <fieldset className="space-y-2">
            <legend className="sr-only">When to activate</legend>
            {options.map(([value, label]) => (
              <label key={value} className="flex items-center gap-2 text-sm">
                <input type="radio" name="activation" value={value} checked={when === value} onChange={() => setWhen(value)} />
                {label}
              </label>
            ))}
          </fieldset>
          {when === "day" && (
            <Field label="Activate on" htmlFor="activate-on" hint="It is activated that morning. Until then the current curriculum stays in use.">
              <Input id="activate-on" type="date" min={istDate(1)} value={day} onChange={(e) => setDay(e.target.value)} />
            </Field>
          )}
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {when === "later" ? (
              <li>It is approved but not in use. You can activate it from your inbox when you are ready.</li>
            ) : (
              impact.who_is_affected.map((line) => (
                <li key={line}>{line.replace(/would get it as soon as it is active/, when === "now" ? "get it now" : "get it that day")}</li>
              ))
            )}
          </ul>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button disabled={busy || (when === "day" && !day)} onClick={() => void submit()}>
              {confirmLabel}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function CurriculumPanel({ detail, onClose }: { detail: CurriculumDetail; onClose: () => void }) {
  const id = detail.curriculum_version_id;
  const impact = useQuery({ queryKey: ["founder", "impact", id], queryFn: () => founderApi.impact(id) });
  const waiting = detail.status === "Under Review";
  const name = detail.component ? `${detail.course.title} (${detail.component.track_name})` : detail.course.title;

  const approve = useApiMutation((activateOn?: string) => founderApi.approveCurriculum(id, activateOn), {
    success: (v) => (v.status === "Active" ? `${v.version_label} is now active` : `${v.version_label} approved`),
    next: (v) =>
      v.status === "Active"
        ? `${v.released?.batches_mapped ?? 0} batch(es) with no curriculum got it, and their students follow it.`
        : v.activate_on
          ? `It will be activated on ${fmtDate(v.activate_on)}.`
          : "It is approved but not active. Activate it from your inbox when you are ready.",
    view: { to: "/founder/curriculum", label: "Open approvals" },
    invalidate: INVALIDATE,
    onSuccess: onClose,
  });
  const activate = useApiMutation(() => founderApi.activateCurriculum(id), {
    success: `${detail.version_label} is now active`,
    next: "Batches with no curriculum got it, and their students follow it.",
    invalidate: INVALIDATE,
    onSuccess: onClose,
  });
  const giveBack = useApiMutation((reason: string) => founderApi.returnCurriculum(id, reason), {
    success: `${detail.version_label} returned`,
    next: "The person who submitted it is told, with your reason.",
    invalidate: INVALIDATE,
    onSuccess: onClose,
  });
  const busy = approve.isPending || activate.isPending || giveBack.isPending;

  return (
    <PanelFrame
      open
      onClose={onClose}
      title={`${waiting ? "Approve" : "Activate"} ${detail.version_label}`}
      description={
        <>
          {name} <StatusBadge domain="curriculum" code={detail.status} />
        </>
      }
      bar={
        waiting ? (
          <>
            <ReasonDialog
              trigger={
                <Button variant="outline" disabled={busy} className="min-w-28">
                  Return
                </Button>
              }
              title={`Return ${detail.version_label}?`}
              description="It goes back to a draft. The person who submitted it is told, with your reason, and can change it and send it again."
              label="What needs to change? (they will read this)"
              confirmLabel="Return it"
              busy={giveBack.isPending}
              minLength={5}
              onSubmit={(reason) => giveBack.mutateAsync(reason)}
            />
            {impact.data ? (
              <ApproveDialog impact={impact.data} busy={busy} onApprove={(day) => approve.mutateAsync(day)} />
            ) : (
              <Button disabled className="min-w-28">
                Approve
              </Button>
            )}
          </>
        ) : (
          <ConfirmDialog
            title={`Activate ${detail.version_label}?`}
            consequence={
              impact.data
                ? impact.data.who_is_affected.join(" ")
                : "It becomes the curriculum in use. Batches with no curriculum get it, and their students follow it."
            }
            confirmLabel="Activate"
            onConfirm={() => activate.mutateAsync(undefined)}
          >
            <Button disabled={busy} className="min-w-28">
              Activate now
            </Button>
          </ConfirmDialog>
        )
      }
    >
      {impact.isPending && <LoadingSkeleton kind="detail" />}
      {impact.isError && <StatusNote tone="danger">Could not work out what changes. Close the panel and open it again.</StatusNote>}
      {impact.data && (
        <>
          <p className="text-sm text-muted-foreground">
            {detail.submitted_by ? `Submitted by ${detail.submitted_by.full_name}` : "Submitted"}
            {detail.submitted_at ? ` on ${fmtDateTime(detail.submitted_at)}` : ""}
            {!waiting && detail.approved_at ? `. Approved ${fmtDate(detail.approved_at)}, not yet active` : ""}.
          </p>
          <PanelPart title="What changes">
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {impact.data.what_changes.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            {impact.data.added_topics.length > 0 && (
              <p className="text-sm">
                <span className="font-medium">New topics:</span> {impact.data.added_topics.join(", ")}
              </p>
            )}
            {impact.data.removed_topics.length > 0 && (
              <p className="text-sm">
                <span className="font-medium">Topics taken out:</span> {impact.data.removed_topics.join(", ")}
              </p>
            )}
          </PanelPart>
          <PanelPart title="Who is affected">
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {impact.data.who_is_affected.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </PanelPart>
          <details className="rounded-lg border px-3 py-2 text-sm">
            <summary className="cursor-pointer font-medium">
              Everything in it ({impact.data.outline.length} module{impact.data.outline.length === 1 ? "" : "s"}, about {hours(impact.data.total_minutes)})
            </summary>
            <ol className="mt-2 space-y-2">
              {impact.data.outline.map((m) => (
                <li key={m.module}>
                  <span className="font-medium">{m.module}</span>
                  <ul className="list-disc pl-5 text-muted-foreground">
                    {m.topics.map((t) => (
                      <li key={t}>{t}</li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          </details>
        </>
      )}
    </PanelFrame>
  );
}
