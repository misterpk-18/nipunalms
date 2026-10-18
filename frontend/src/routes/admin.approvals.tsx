import { createFileRoute } from "@tanstack/react-router";
import { ApprovalsPage } from "@/features/shared/approvals/approvals-page";

/** The Super Admin's Approvals: the same inbox as the Founder's, every item decided here. */
export const Route = createFileRoute("/admin/approvals")({ component: () => <ApprovalsPage page="/admin/approvals" /> });
