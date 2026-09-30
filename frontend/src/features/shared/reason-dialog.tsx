import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/** A button that opens a small dialog asking for a written reason (escalate, reopen, resolve) before it acts. */
export function ReasonDialog({
  trigger,
  title,
  description,
  label = "Reason",
  confirmLabel,
  busy,
  onSubmit,
}: {
  trigger: ReactNode;
  title: string;
  description?: string;
  label?: string;
  confirmLabel: string;
  busy?: boolean;
  onSubmit: (reason: string) => Promise<unknown> | unknown;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const id = `reason-${title.replace(/\W+/g, "-").toLowerCase()}`;

  const submit = async () => {
    try {
      await onSubmit(reason.trim());
      setOpen(false);
      setReason("");
    } catch {
      /* the mutation already toasted the error; keep the dialog open */
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor={id}>{label}</Label>
          <Textarea id={id} rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button disabled={busy || reason.trim().length < 3} onClick={() => void submit()}>
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
