/** IST display helpers: business dates and times are always shown in Asia/Kolkata. */

const DATE_TIME = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const DATE = new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "numeric" });

/** "30 Sep 2026, 15:30 IST" from an ISO timestamp. */
export function formatIst(iso: string | null | undefined): string {
  return iso ? `${DATE_TIME.format(new Date(iso))} IST` : "—";
}

/** "30 Sep 2026" from an ISO timestamp or a YYYY-MM-DD business date. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return DATE.format(value.length === 10 ? new Date(`${value}T00:00:00+05:30`) : new Date(value));
}

/** "₹ 30,000" from a money string such as "30000.00". */
export function formatMoney(value: string | null | undefined): string {
  return value == null ? "—" : `₹ ${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}
