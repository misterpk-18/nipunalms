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
  minLength = 3,
  destructive,
  onSubmit,
}: {
  trigger: ReactNode;
  title: string;
  description?: string;
  label?: string;
  confirmLabel: string;
  busy?: boolean;
  /** The shortest reason accepted; shown under the box until it is reached. */
  minLength?: number;
  /** Styles the button as a destructive action (reject, revoke, discard). */
  destructive?: boolean;
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
          {reason.trim().length < minLength && <p className="text-xs text-muted-foreground">Write at least {minLength} characters.</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button variant={destructive ? "destructive" : "default"} disabled={busy || reason.trim().length < minLength} onClick={() => void submit()}>
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
