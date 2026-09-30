/** IST date and percentage formatting shared by the attendance and certificate screens. */
import type { DateOnly, DateTime } from "@/api/types";

const IST = "Asia/Kolkata";

/** "21 Sep 2026" in IST (business dates are IST everywhere). */
export function fmtDate(value: DateTime | DateOnly | null | undefined): string {
  if (!value) return "—";
  const date = value.length === 10 ? new Date(`${value}T00:00:00+05:30`) : new Date(value);
  return date.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: IST });
}

/** "10:00–12:00 IST" for a class. */
export function fmtRange(start: DateTime, end: DateTime): string {
  const time = (v: string) => new Date(v).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: IST });
  return `${time(start)}–${time(end)} IST`;
}

export function fmtDateTime(value: DateTime | null | undefined): string {
  if (!value) return "—";
  return `${fmtDate(value)}, ${new Date(value).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: IST })} IST`;
}

export const percent = (value: number | null | undefined) => (value === null || value === undefined ? "Not Yet Calculable" : `${Math.round(value)}%`);

/** "Today", "1 day", "5 days" for the age of a queue item. */
export const ageText = (days: number) => (days === 0 ? "Today" : `${days} day${days === 1 ? "" : "s"}`);
