/** The Courses list: the CRM's courses with the outline counts and what is running. The Branch Manager sees their own branch; the Super Admin and
 * Founder see every branch, with the counts per branch. */
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { coursesApi, type CourseListRow } from "@/api/courses";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, PageHead, QueryView, StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Input } from "@/components/ui/input";
import { coursesTo, type CoursesBase } from "./area";
import { plural } from "./mutation";

export function CourseList({ base }: { base: CoursesBase }) {
  const central = base !== "/branch";
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const query = useQuery({ queryKey: ["courses", "list"], queryFn: coursesApi.list });
  const categories = [...new Set((query.data ?? []).map((c) => c.category).filter((c): c is string => !!c))].sort();
  const text = q.trim().toLowerCase();
  const match = (c: CourseListRow) => (!category || c.category === category) && (!text || `${c.title} ${c.course_code}`.toLowerCase().includes(text));
  return (
    <>
      <PageHead
        title="Courses"
        description={
          central
            ? "The courses the CRM offers and the outline each one follows. Open a course to change its modules, topics, hours and completion rules."
            : "The courses on offer and the outline each one follows. Open one to see its modules and topics, or to start a batch for it."
        }
      />
      <div className="space-y-4">
        <StatusNote tone="info">
          Course code, title, category, status and tracks come from the CRM and cannot be changed here.
          {central ? " The outline (modules, topics, hours and rules) is edited in the LMS." : " Only a Super Admin or the Founder / CEO edits an outline."}
        </StatusNote>
        <div className="flex flex-wrap gap-2">
          <Input
            type="search"
            className="max-w-xs"
            placeholder="Search by title or code"
            aria-label="Search courses"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {categories.length > 1 && (
            <NativeSelect
              aria-label="Category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              options={[{ value: "", label: "Every category" }, ...categories.map((c) => ({ value: c, label: c }))]}
            />
          )}
        </div>
        <QueryView query={query} isEmpty={(rows) => rows.length === 0} empty="The CRM has not sent any course yet.">
          {(rows) => (
            <DataTable
              caption="Courses"
              rows={rows.filter(match)}
              getKey={(c) => c.course_id}
              empty="No course matches that search."
              cols={[
                {
                  h: "Course",
                  c: (c) => (
                    <>
                      <Link
                        {...{ to: coursesTo(base, "/$id"), params: { id: String(c.course_id) } as never }}
                        className="font-medium text-primary underline-offset-2 hover:underline"
                      >
                        {c.title}
                      </Link>
                      <div className="font-mono text-xs text-muted-foreground">{c.course_code}</div>
                    </>
                  ),
                },
                { h: "Category", c: (c) => c.category ?? "—" },
                {
                  h: "Tracks",
                  c: (c) =>
                    c.is_combo && (c.components?.length ?? 0) > 0 ? (
                      <ul className="space-y-0.5 text-xs">
                        {c.components!.map((t) => (
                          <li key={t.component_id}>
                            {t.track_name} <span className="text-muted-foreground">({t.role})</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      "Single course"
                    ),
                },
                { h: "Status", c: (c) => <StatusBadge domain="course" code={c.status} /> },
                {
                  h: "Outline",
                  c: (c) => (
                    <>
                      {c.counts.modules === 0 ? (
                        <Tag tone="warning">No outline yet</Tag>
                      ) : (
                        `${plural(c.counts.modules, "module")}, ${plural(c.counts.topics, "topic")}`
                      )}
                      {central && c.counts.modules > 0 && (
                        <div className="mt-1">
                          <Tag tone={c.hours_verified ? "success" : "neutral"}>{c.hours_verified ? "Hours verified" : "Hours not verified"}</Tag>
                        </div>
                      )}
                    </>
                  ),
                },
                {
                  h: central ? "Running now" : "At my branch",
                  c: (c) => (
                    <>
                      <div>{plural(c.usage.running_batches, "batch", "batches")} running</div>
                      <div className="text-xs text-muted-foreground">
                        {plural(c.usage.active_enrolments, "active student")}
                        {c.usage.students_waiting > 0 && ` · ${c.usage.students_waiting} waiting for a batch`}
                      </div>
                      {central && c.usage.by_branch.length > 0 && (
                        <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                          {c.usage.by_branch.map((b) => (
                            <li key={b.branch.branch_id}>
                              {b.branch.branch_name}: {plural(b.running_batches, "batch", "batches")}, {plural(b.active_enrolments, "student")}
                            </li>
                          ))}
                        </ul>
                      )}
                    </>
                  ),
                },
              ]}
            />
          )}
        </QueryView>
      </div>
    </>
  );
}
