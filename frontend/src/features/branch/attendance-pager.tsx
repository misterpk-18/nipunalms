import type { PageMeta } from "@/api/client";
import { Button } from "@/components/ui/button";

/** Previous / Next with "Page 2 of 5" and the total; nothing when there is only one page. */
export function Pager({ meta, onPage, noun }: { meta: PageMeta; onPage: (page: number) => void; noun: string }) {
  if (meta.pages <= 1) return null;
  return (
    <nav aria-label="Pages" className="flex flex-wrap items-center justify-between gap-2 text-sm">
      <span className="text-muted-foreground">
        {meta.total} {noun}
      </span>
      <div className="flex items-center gap-2">
        <Button size="sm" variant="outline" disabled={meta.page <= 1} onClick={() => onPage(meta.page - 1)}>
          Previous
        </Button>
        <span>
          Page {meta.page} of {meta.pages}
        </span>
        <Button size="sm" variant="outline" disabled={meta.page >= meta.pages} onClick={() => onPage(meta.page + 1)}>
          Next
        </Button>
      </div>
    </nav>
  );
}
