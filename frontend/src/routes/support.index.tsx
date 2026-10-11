import { createFileRoute } from "@tanstack/react-router";
import { SUPPORT_CATEGORIES, type SupportCategory } from "@/api/support";
import { Support } from "@/features/student/support";

export type SupportSearch = { new?: 1; category?: SupportCategory; subject?: string; details?: string };

/** `?new=1` opens the request form, optionally filled in (Ask Nipuna sends a question it could not answer this way). */
export const Route = createFileRoute("/support/")({
  validateSearch: (search: Record<string, unknown>): SupportSearch => {
    const out: SupportSearch = {};
    if (search["new"] === 1 || search["new"] === "1" || search["new"] === true) out.new = 1;
    const category = SUPPORT_CATEGORIES.find((c) => c === search["category"]);
    if (category) out.category = category;
    if (typeof search["subject"] === "string") out.subject = search["subject"].slice(0, 200);
    if (typeof search["details"] === "string") out.details = search["details"].slice(0, 4000);
    return out;
  },
  component: Support,
});
