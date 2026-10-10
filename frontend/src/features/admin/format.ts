/** Non-component helpers for the admin screens. */
import { useAuth } from "@/auth/auth";

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

/** Only a Super Admin may change anything on the admin screens; the Founder / CEO reads. */
export function useCanAdminister(): boolean {
  return useAuth().hasRole("SUPER_ADMIN");
}
/** One line for a person who just sent a link: it went by WhatsApp, or why it did not and what to do instead. */
export function whatsappLine(whatsapp: { state: string; note: string | null }, who: string): string {
  if (whatsapp.state === "Queued" || whatsapp.state === "Sent") return `The link is on its way to ${who} by WhatsApp.`;
  return `It was not sent by WhatsApp (${whatsapp.note ?? whatsapp.state}). Copy the link below and give it to ${who}.`;
}
