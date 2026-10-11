import { createFileRoute, redirect } from "@tanstack/react-router";

/** Fees & Receipts is a tab of My Account now. */
export const Route = createFileRoute("/finance")({
  beforeLoad: () => {
    throw redirect({ to: "/my-account", search: { tab: "fees" }, replace: true });
  },
});
