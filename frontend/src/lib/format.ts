/** Date helpers: every business time is shown in IST, and datetime-local inputs are read and written as IST. */

const IST_OFFSET = "+05:30";
const IST_MS = 5.5 * 3600 * 1000;

const FORMAT = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Kolkata",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** "29 Sep 2026, 23:59 IST" */
export function formatIst(value: string | null | undefined): string {
  if (!value) return "—";
  return `${FORMAT.format(new Date(value)).replace(",", "")} IST`;
}

/** The ISO timestamp as the "YYYY-MM-DDTHH:mm" text a datetime-local input shows, in IST. */
export function toIstInput(value: string | null | undefined): string {
  if (!value) return "";
  return new Date(new Date(value).getTime() + IST_MS).toISOString().slice(0, 16);
}

/** "YYYY-MM-DDTHH:mm" typed in IST → ISO 8601 with the +05:30 offset the API expects. */
export function fromIstInput(value: string): string {
  return `${value}:00${IST_OFFSET}`;
}

/** A datetime-local default: now plus the given hours, in IST. */
export function istInputIn(hours: number): string {
  return toIstInput(new Date(Date.now() + hours * 3600 * 1000).toISOString());
}

/** 3725 → "01:02:05" */
export function clock(totalSeconds: number): string {
  const s = Math.max(totalSeconds, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
}
