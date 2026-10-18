/** Save one module to the reusable library. A library module is usable at once; there is no approval step. */
import { coursesApi } from "@/api/courses";
import type { ModuleContent } from "@/api/delivery";
import { Button } from "@/components/ui/button";
import { useCourseMutation } from "./mutation";

export function SaveToLibrary({ module }: { module: ModuleContent }) {
  const save = useCourseMutation(() => coursesApi.saveToLibrary(module.module_id), "Saved to the library", {
    next: "It can be added to any course from Module library.",
  });
  return (
    <Button
      size="sm"
      variant="ghost"
      aria-label={`Save module ${module.title} to the library`}
      disabled={save.isPending}
      onClick={() => save.mutate(undefined)}
    >
      Save to library
    </Button>
  );
}
