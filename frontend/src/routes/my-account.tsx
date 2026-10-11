import { createFileRoute } from "@tanstack/react-router";
import { MyAccount } from "@/features/student/account";

/** The student's account: Profile and Fees & Receipts. `?tab=fees` opens the fees. */
export const Route = createFileRoute("/my-account")({
  validateSearch: (search: Record<string, unknown>): { tab?: "fees" } => (search["tab"] === "fees" ? { tab: "fees" } : {}),
  component: MyAccount,
});
