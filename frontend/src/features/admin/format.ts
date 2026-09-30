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
