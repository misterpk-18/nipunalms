import { createFileRoute } from "@tanstack/react-router";
import { BatchList } from "@/features/branch/batches";

/** Every branch's batches, read-only, with a branch filter. */
export const Route = createFileRoute("/founder/batches/")({
  component: () => <BatchList basePath="/founder/batches" manage={false} branchFilter />,
});
