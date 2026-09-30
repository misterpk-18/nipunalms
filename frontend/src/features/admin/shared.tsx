/** Pieces shared by the admin screens: IST formatting, pager, form dialog, show-once secret dialog, filter inputs. */
import { useState, type FormEvent, type ReactNode } from "react";
import { Copy } from "lucide-react";
import { toast } from "sonner";
import type { PageMeta } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

export function Pager({ meta, onPage }: { meta: PageMeta; onPage: (page: number) => void }) {
  if (meta.pages <= 1) return null;
  return (
    <nav aria-label="Pages" className="mt-3 flex items-center justify-between gap-2 text-sm">
      <span className="text-muted-foreground">
        Page {meta.page} of {meta.pages} · {meta.total} records
      </span>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={meta.page <= 1} onClick={() => onPage(meta.page - 1)}>
          Previous
        </Button>
        <Button variant="outline" size="sm" disabled={meta.page >= meta.pages} onClick={() => onPage(meta.page + 1)}>
          Next
        </Button>
      </div>
    </nav>
  );
}

export function FormDialog({
  title,
  description,
  onClose,
  onSubmit,
  busy,
  submitLabel = "Save",
  destructive = false,
  children,
}: {
  title: string;
  description?: ReactNode;
  onClose: () => void;
  onSubmit: () => void;
  busy?: boolean;
  submitLabel?: string;
  destructive?: boolean;
  children: ReactNode;
}) {
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] w-[calc(100vw-1.5rem)] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <form
          className="grid gap-3"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            onSubmit();
          }}
        >
          {children}
          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant={destructive ? "destructive" : "default"} disabled={busy}>
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** A secret the server shows exactly once (temporary password, activation link): copy it now, it is not stored. */
export function SecretDialog({
  title,
  description,
  label,
  value,
  onClose,
}: {
  title: string;
  description: ReactNode;
  label: string;
  value: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[calc(100vw-1.5rem)] max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="space-y-1.5">
          <p className="text-xs text-muted-foreground">{label}</p>
          <div className="flex items-center gap-2">
            <Input readOnly value={value} aria-label={label} className="font-mono text-sm" onFocus={(e) => e.currentTarget.select()} />
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label="Copy"
              onClick={() => {
                void navigator.clipboard?.writeText(value).then(
                  () => setCopied(true),
                  () => toast.error("Copy failed — select the text and copy it"),
                );
              }}
            >
              <Copy className="size-4" />
            </Button>
          </div>
          {copied && <p className="text-xs text-success">Copied.</p>}
        </div>
        <DialogFooter>
          <Button onClick={onClose}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** A small labelled control for filter bars. */
export function FilterField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1 text-xs text-muted-foreground">
      {label}
      {children}
    </label>
  );
}
