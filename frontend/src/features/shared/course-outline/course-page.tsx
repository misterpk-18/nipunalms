/** One course: the CRM's fields (read-only), what is running, and the outline. Super Admin and Founder edit modules, topics, hours, completion
 * rules, required assessments, combo track pins and the module library; the Branch Manager reads and starts a batch for the course. */
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { coursesApi } from "@/api/courses";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { KeyValue, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { ActionDialog } from "@/features/shared/delivery-ui";
import { coursesTo, type CoursesBase } from "./area";
import { plural, useCourseMutation } from "./mutation";
import { OutlineView } from "./outline-view";
import { CoursePlanning } from "./planning";
import { CourseTracks } from "./tracks";
import { ModuleTree } from "./tree";

export function CoursePage({ id, base }: { id: string; base: CoursesBase }) {
  const courseId = Number(id);
  const query = useQuery({
    queryKey: ["courses", "outline", courseId],
    queryFn: () => coursesApi.outline(courseId),
    enabled: Number.isInteger(courseId) && courseId > 0,
  });
  const addModule = useCourseMutation((title: string) => coursesApi.addModule(courseId, { title }), "Module added", {
    next: "Add its topics, then open Details on each to fill them in.",
  });
  return (
    <div className="mx-auto max-w-6xl">
      <QueryView query={query} skeleton="detail">
        {(o) => {
          const editable = o.can_edit && base !== "/branch";
          const course = o.course;
          const usage = o.usage;
          const addButton = editable && (
            <ActionDialog
              trigger={<Button size="sm">Add module</Button>}
              title="Add a module"
              fields={[{ name: "title", label: "Module title", required: true }]}
              onSubmit={(f) => addModule.mutateAsync(f["title"]!)}
            />
          );
          return (
            <>
              <Breadcrumbs items={[{ label: "Courses", to: coursesTo(base, "") }, { label: course.title }]} />
              <PageHead
                title={course.title}
                description={
                  <>
                    <span className="font-mono">{course.course_code}</span>
                    {course.category && ` · ${course.category}`} · {plural(o.counts.modules, "module")}, {plural(o.counts.topics, "topic")},{" "}
                    {o.counts.required_topics} required
                  </>
                }
                actions={
                  base === "/branch" && course.status === "Active" ? (
                    <Button asChild>
                      <Link to="/branch/batches" search={{ new: 1, course: course.course_id }}>
                        New batch for this course
                      </Link>
                    </Button>
                  ) : undefined
                }
              />
              <div className="space-y-4">
                <Section title="From the CRM">
                  <KeyValue
                    items={[
                      [
                        "Code",
                        <span key="c" className="font-mono">
                          {course.course_code}
                        </span>,
                      ],
                      ["Title", course.title],
                      ["Category", course.category ?? "—"],
                      ["Status", <StatusBadge key="s" domain="course" code={course.status} />],
                      [
                        "Tracks",
                        course.is_combo && (course.components?.length ?? 0) > 0
                          ? course.components!.map((t) => `${t.track_name} (${t.role})`).join(", ")
                          : "Single course",
                      ],
                    ]}
                  />
                  <p className="mt-2 text-xs text-muted-foreground">These come from the CRM and cannot be changed here.</p>
                  {usage && (
                    <p className="mt-3 text-sm text-muted-foreground">
                      {base === "/branch" ? "At your branch: " : "Company-wide: "}
                      {plural(usage.running_batches, "batch", "batches")} running, {plural(usage.active_enrolments, "active student")}
                      {usage.students_waiting > 0 && `, ${usage.students_waiting} waiting for a batch`}.
                    </p>
                  )}
                  {base !== "/branch" && usage && usage.by_branch.length > 0 && (
                    <ul className="mt-1 space-y-0.5 text-sm text-muted-foreground">
                      {usage.by_branch.map((b) => (
                        <li key={b.branch.branch_id}>
                          {b.branch.branch_name}: {plural(b.running_batches, "batch", "batches")}, {plural(b.active_enrolments, "active student")}
                        </li>
                      ))}
                    </ul>
                  )}
                </Section>

                {editable && (
                  <StatusNote tone="info">
                    A change here applies at once to every batch of this course. The Branch Managers of branches with a running batch are told, and the change
                    is written to the audit log.
                  </StatusNote>
                )}

                <Section id="course-modules" title="Modules and topics" actions={editable && o.modules.length > 0 ? addButton : undefined}>
                  {editable ? (
                    <>
                      <ModuleTree
                        modules={o.modules}
                        editable
                        emptyReason={
                          o.tracks.length > 0
                            ? "This course has no modules of its own. Its tracks have outlines below."
                            : "This course has no outline yet. Add the first module, then its topics."
                        }
                        addAction={addButton}
                      />
                      {o.modules.length > 1 && (
                        <p className="mt-2 text-xs text-muted-foreground">Drag a row by its handle to reorder it, or use Move up and Move down.</p>
                      )}
                    </>
                  ) : (
                    <OutlineView outline={{ ...o, tracks: [] }} />
                  )}
                </Section>

                {editable ? (
                  <CourseTracks outline={o} editable />
                ) : (
                  o.tracks.length > 0 && (
                    <Section title="Tracks and booster">
                      <OutlineView outline={{ ...o, modules: [], tracks: o.tracks }} />
                    </Section>
                  )
                )}

                {o.totals && <CoursePlanning outline={o} editable={editable} />}
              </div>
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
