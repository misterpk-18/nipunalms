/** Plain-words helpers for Marks & results. */
import type { ReviewQueueRow } from "@/api/assessments";

/** "5 to review, 2 moderated, 0 published" and, when attempts are still being marked, how many. */
export function countsText(counts: ReviewQueueRow["counts"]): string {
  const base = `${counts.provisional} to review, ${counts.moderated} moderated, ${counts.published} published`;
  return counts.awaiting_grading > 0 ? `${base}, ${counts.awaiting_grading} still being marked` : base;
}

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** The filter the results and publish endpoints take for one item in one batch. */
export function scopeOf(row: Pick<ReviewQueueRow, "kind" | "item_id" | "batch">) {
  return row.kind === "Assignment" ? { assignment_id: row.item_id, batch_id: row.batch.batch_id } : { test_id: row.item_id, batch_id: row.batch.batch_id };
}

/** A mark as people write it: 8.00 becomes 8. */
export const marksText = (value: string | null) => (value === null ? "" : String(Number(value)));
