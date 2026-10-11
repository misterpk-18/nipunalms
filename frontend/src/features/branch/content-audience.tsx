/** Words for who will see a content item. */
import type { ContentItem } from "@/api/content";

/** Who will see the item, in words for the preview. */
export function audienceText(item: Pick<ContentItem, "staff_only" | "batch" | "course" | "branch">): string {
  if (item.staff_only) return "Staff only. Students never see it.";
  if (item.batch) return `Students of batch ${item.batch.batch_code}`;
  return `All ${item.course.course_code} students at ${item.branch.branch_name} (the whole course)`;
}

/** The consequence line of a release: who sees it now. */
export function releaseConsequence(item: Pick<ContentItem, "staff_only" | "batch" | "course" | "branch">): string {
  if (item.staff_only) return "It is for staff only, so students will not see it.";
  if (item.batch) return `Students of batch ${item.batch.batch_code} will see it now.`;
  return `Students of the whole course (${item.course.course_code} at ${item.branch.branch_name}) will see it now.`;
}
