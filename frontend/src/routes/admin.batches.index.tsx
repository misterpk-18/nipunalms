import { createFileRoute } from "@tanstack/react-router";
import { BatchList } from "@/features/shared/batches";

/** Every branch's batches, read-only, with a branch filter. */
export const Route = createFileRoute("/admin/batches/")({
  component: () => <BatchList basePath="/admin/batches" manage={false} branchFilter />,
});
