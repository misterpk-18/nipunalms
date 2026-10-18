import { createFileRoute } from "@tanstack/react-router";
import { ApprovalsPage } from "@/features/shared/approvals/approvals-page";

/** The Founder's Approvals: the same inbox as the Super Admin's, every item decided here. */
export const Route = createFileRoute("/founder/approvals")({ component: () => <ApprovalsPage page="/founder/approvals" /> });
