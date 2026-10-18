/** The course outline of a batch, read-only: the modules and topics the classes follow. Only a Super Admin or the Founder / CEO edits it. */
import { useQuery } from "@tanstack/react-query";
import { coursesApi } from "@/api/courses";
import { QueryView, Section } from "@/components/lms/ui";
import { OutlineView } from "@/features/shared/course-outline/outline-view";

export function CourseOutlineBlock({ courseId }: { courseId: number }) {
  const query = useQuery({ queryKey: ["courses", "outline", courseId], queryFn: () => coursesApi.outline(courseId) });
  return (
    <Section title="Course outline">
      <QueryView query={query} skeleton="cards">
        {(outline) => (
          <details>
            <summary className="cursor-pointer text-sm font-medium">
              {outline.counts.modules} modules, {outline.counts.topics} topics ({outline.counts.required_topics} required)
            </summary>
            <div className="mt-3">
              <OutlineView outline={outline} />
            </div>
          </details>
        )}
      </QueryView>
    </Section>
  );
}
