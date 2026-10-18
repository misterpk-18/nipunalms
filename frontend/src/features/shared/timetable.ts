/** The batch timetable fields (db 098): the request body from dialog values, and the one-line label. */
import type { Batch } from "@/api/delivery";

/** Empty fields are sent as null: "not confirmed" for the CRM's sales staff. */
export function timetableBody(v: Record<string, string>) {
  return {
    schedule_days: v["schedule_days"] ? v["schedule_days"].split(",") : null,
    start_time: v["start_time"] || null,
    end_time: v["end_time"] || null,
    location: v["location"]?.trim() || null,
  };
}

/** "Mon, Wed, Fri · 18:30–20:30 IST · Guntur Lab 2", or "Not set". */
export function timetableLabel(batch: Pick<Batch, "schedule_days" | "start_time" | "end_time" | "location">): string {
  const parts = [
    batch.schedule_days.length ? batch.schedule_days.join(", ") : null,
    batch.start_time && batch.end_time ? `${batch.start_time}–${batch.end_time} IST` : null,
    batch.location,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Not set";
}
