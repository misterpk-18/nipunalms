/** The side panel every Founder item opens in: a header, a scrolling body and a bar pinned to the bottom with the decision buttons. */
import type { ReactNode } from "react";
import { Tag } from "@/components/lms/ui";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

export function PanelFrame({
  open,
  onClose,
  title,
  description,
  fromBranchManager,
  bar,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  /** A Branch Manager's own request: nobody at the branch can review it, so it comes to the Founder. */
  fromBranchManager?: boolean;
  /** The decision buttons. */
  bar: ReactNode;
  children: ReactNode;
}) {
  return (
    <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
      <SheetContent className="flex w-full flex-col gap-0 p-0 sm:max-w-xl">
        <SheetHeader className="space-y-1 border-b px-6 py-4 pr-12">
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription asChild>
            <div>
              {description}
              {fromBranchManager && (
                <div className="mt-2">
                  <Tag tone="info">A Branch Manager's own request. Nobody at the branch can review it, so it comes to you.</Tag>
                </div>
              )}
            </div>
          </SheetDescription>
        </SheetHeader>
        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-4">{children}</div>
        <div data-testid="decision-bar" className="flex flex-wrap items-center justify-end gap-2 border-t bg-background px-6 py-3">
          {bar}
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** A small heading and its content inside a panel. */
export function PanelPart({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}
