/** Hours, completion rules, required assessments and library inserts for one course. */
import { useQuery } from "@tanstack/react-query";
import { coursesApi, type CourseOutline } from "@/api/courses";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { ActionDialog } from "@/features/shared/delivery-ui";
import { hoursText, topicChoices, useCourseMutation } from "./mutation";

/**  */
export function CoursePlanning({ outline, editable }: { outline: CourseOutline; editable: boolean }) {
  const id = outline.course.course_id;
  const verify = useCourseMutation(() => coursesApi.verifyHours(id), "Hours verified");
  const profile = useCourseMutation(
    (v: Record<string, string>) =>
      coursesApi.setCompletionProfile(id, {
        attendance_minimum_pct: Number(v["attendance_minimum_pct"]),
        pass_mark_pct: Number(v["pass_mark_pct"]),
        recovery_rule: v["recovery_rule"]!,
        reassessment_rule: v["reassessment_rule"]!,
      }),
    "Completion rules saved",
  );
  const addRequirement = useCourseMutation((body: Record<string, unknown>) => coursesApi.addRequirement(id, body), "Required assessment added");
  const deleteRequirement = useCourseMutation((requirementId: number) => coursesApi.deleteRequirement(requirementId), "Required assessment removed");
  const library = useQuery({ queryKey: ["delivery", "library"], queryFn: coursesApi.library, enabled: editable });
  const insert = useCourseMutation((libraryVersionId: number) => coursesApi.insertLibraryModule(id, libraryVersionId), "Library module added");
  const totals = outline.totals;
  const p = outline.completion_profile;
  const approvedLibrary = (library.data?.data ?? []).filter((m) => m.current_version);
  const topicOptions = topicChoices(outline.modules);
  const topicName = (topicId: number | null) => topicOptions.find((t) => t.topic_id === topicId)?.label;
  const manage = editable;

  return (
    <div className="grid gap-3 rounded-lg border p-3 text-sm sm:grid-cols-2">
      <div id="course-hours" tabIndex={-1} className="scroll-mt-20 space-y-1 outline-none">
        <h4 className="font-semibold">Hours</h4>
        {totals && (
          <>
            <p>
              Taught {hoursText(totals.instructional_minutes)} · self-study {hoursText(totals.independent_minutes)} · total {hoursText(totals.total_minutes)}
            </p>
            {totals.booster && (
              <p className="text-muted-foreground">
                Included booster {totals.booster.track_code}: {hoursText(totals.booster.total_minutes)}
              </p>
            )}
            <Tag tone={totals.hours_verified ? "success" : "warning"}>{totals.hours_verified ? "Hours verified" : "Hours not verified yet"}</Tag>
            {totals.unestimated_topics > 0 && <p className="text-muted-foreground">{totals.unestimated_topics} topic(s) have no minutes yet.</p>}
          </>
        )}
        {manage && (
          <Button size="sm" variant="outline" disabled={verify.isPending} onClick={() => verify.mutate(undefined)}>
            Verify hours
          </Button>
        )}
      </div>
      <div id="course-rules" tabIndex={-1} className="scroll-mt-20 space-y-1 outline-none">
        <h4 className="font-semibold">Completion rules</h4>
        {p ? (
          <p>
            Attendance at least {p.attendance_minimum_pct}% · pass mark {p.pass_mark_pct}% · missed classes: {p.recovery_rule} · retakes: {p.reassessment_rule}
          </p>
        ) : (
          <Tag tone="warning">Not set. No student can complete the course without them.</Tag>
        )}
        {manage && (
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Set completion rules
              </Button>
            }
            title="Completion rules"
            description="What a student must reach to complete this course."
            fields={[
              {
                name: "attendance_minimum_pct",
                label: "Attendance minimum (%)",
                type: "number",
                required: true,
                min: 0,
                value: String(p?.attendance_minimum_pct ?? ""),
              },
              { name: "pass_mark_pct", label: "Pass mark (%)", type: "number", required: true, min: 0, value: String(p?.pass_mark_pct ?? "") },
              { name: "recovery_rule", label: "If a student misses classes", type: "textarea", required: true, value: p?.recovery_rule ?? "" },
              { name: "reassessment_rule", label: "If a student fails a test", type: "textarea", required: true, value: p?.reassessment_rule ?? "" },
            ]}
            onSubmit={(v) => profile.mutateAsync(v)}
          />
        )}
      </div>
      <div id="course-assessments" tabIndex={-1} className="scroll-mt-20 space-y-1 outline-none sm:col-span-2">
        <h4 className="font-semibold">Required assessments</h4>
        {(outline.assessment_requirements ?? []).length === 0 ? (
          <p className="text-muted-foreground">None yet. A test or assignment marked required must be linked to one of these.</p>
        ) : (
          <ul className="space-y-1">
            {outline.assessment_requirements!.map((r) => (
              <li key={r.requirement_id} className="flex flex-wrap items-center justify-between gap-2">
                <span className="min-w-0 break-words">
                  <Tag>{r.kind}</Tag> {r.title} — {r.outcome} · weight {r.weight} · pass: {r.pass_rule}
                  {topicName(r.topic_id) && <span className="text-muted-foreground"> · for {topicName(r.topic_id)}</span>}
                </span>
                {manage && (
                  <ConfirmDialog
                    title={`Remove required assessment ${r.title}?`}
                    consequence={`${r.title} will no longer be needed to complete this course, and any test or assignment linked to it loses the link. This cannot be undone.`}
                    confirmLabel="Remove assessment"
                    destructive
                    onConfirm={() => deleteRequirement.mutateAsync(r.requirement_id)}
                  >
                    <Button size="sm" variant="ghost" aria-label={`Remove required assessment ${r.title}`}>
                      Remove
                    </Button>
                  </ConfirmDialog>
                )}
              </li>
            ))}
          </ul>
        )}
        {manage && (
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Add required assessment
              </Button>
            }
            title="Add a required assessment"
            fields={[
              { name: "kind", label: "Kind", type: "select", options: ["Assignment", "Test"].map((k) => ({ value: k, label: k })) },
              { name: "title", label: "Title", required: true },
              { name: "outcome", label: "What it shows a student can do", type: "textarea", required: true },
              { name: "weight", label: "Weight", type: "number", min: 0, required: true },
              { name: "pass_rule", label: "What counts as a pass", required: true, placeholder: "For example: 60% or more" },
              {
                name: "topic_id",
                label: "Linked topic (optional)",
                type: "select",
                options: [{ value: "", label: "Not linked to one topic" }, ...topicOptions.map((t) => ({ value: t.topic_id, label: t.label }))],
              },
            ]}
            onSubmit={(v) => {
              const { topic_id, ...rest } = v;
              return addRequirement.mutateAsync({ ...rest, weight: Number(v["weight"]), ...(topic_id ? { topic_id: Number(topic_id) } : {}) });
            }}
          />
        )}
      </div>
      {manage && approvedLibrary.length > 0 && (
        <div className="sm:col-span-2">
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Add a module from the library
              </Button>
            }
            title="Reuse a library module"
            description="The module is copied as it is now. Later changes to the library do not change this course."
            fields={[
              {
                name: "library_version_id",
                label: "Library module",
                type: "select",
                options: approvedLibrary.map((m) => ({
                  value: m.current_version!.library_version_id,
                  label: `${m.title} (version ${m.current_version!.version_no}, ${m.current_version!.content.topics.length} topics)`,
                })),
              },
            ]}
            onSubmit={(v) => insert.mutateAsync(Number(v["library_version_id"]))}
          />
        </div>
      )}
    </div>
  );
}
