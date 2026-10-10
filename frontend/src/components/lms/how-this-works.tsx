import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

/** The policy and rules behind a screen, folded away so the screen itself stays about what to do. */
export function HowThisWorks({ title = "How this works", children }: { title?: string; children: ReactNode }) {
  return (
    <Collapsible className="rounded-lg border bg-muted/40 px-3 py-2 text-sm">
      <CollapsibleTrigger className="group flex w-full items-center justify-between gap-2 font-medium">
        {title}
        <ChevronDown className="size-4 transition-transform group-data-[state=open]:rotate-180" aria-hidden />
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2 space-y-2 text-muted-foreground">{children}</CollapsibleContent>
    </Collapsible>
  );
}
