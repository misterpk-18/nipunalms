/** Non-component helpers for the admin screens. */

const IST_FORMAT = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: true,
});

/** "30 Sep 2026, 09:49 am IST" */
export function istDateTime(value: string | null | undefined): string {
  return value ? `${IST_FORMAT.format(new Date(value))} IST` : "—";
}

/** One line for a person who just sent a link: it went by WhatsApp, or why it did not and what to do instead. */
type Outcome = { state: string; note: string | null };
const going = (o: Outcome | undefined) => o?.state === "Queued" || o?.state === "Sent";
const why = (o: Outcome | undefined) => o?.note ?? o?.state ?? "not sent";

/** Where a new link went: by WhatsApp, by email (to the masked address), both, or neither (then copy it). */
export function deliveryLine(whatsapp: Outcome | undefined, email: (Outcome & { to: string | null }) | undefined, who: string): string {
  const byEmail = `by email to ${email?.to ?? "the address on file"}`;
  if (going(whatsapp) && going(email)) return `The link is on its way to ${who} by WhatsApp and ${byEmail}.`;
  if (going(whatsapp)) return `The link is on its way to ${who} by WhatsApp. No email went (${why(email)}).`;
  if (going(email)) return `The link is on its way to ${who} ${byEmail}. It was not sent by WhatsApp (${why(whatsapp)}).`;
  return `It was not sent by WhatsApp (${why(whatsapp)}) or email (${why(email)}). Copy the link below and give it to ${who}.`;
}
