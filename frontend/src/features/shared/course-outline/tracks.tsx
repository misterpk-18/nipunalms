/** The tracks and booster of a combo course. Each has its own outline, or follows the outline of its own standalone course once someone has
 * checked that the two match (Super Admin and Founder pin it). */
import { coursesApi, type CourseOutline, type OutlineTrack } from "@/api/courses";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { ActionDialog } from "@/features/shared/delivery-ui";
import { useCourseMutation } from "./mutation";
import { ModuleTree } from "./tree";

function TrackPin({ courseId, track }: { courseId: number; track: OutlineTrack }) {
  const c = track.component;
  const pin = useCourseMutation(
    async (note: string) => {
      await coursesApi.reviewEquivalence(c.component_id, note);
      return coursesApi.pinTrack(courseId, { component_id: c.component_id, pinned_course_id: c.component_course!.course_id });
    },
    `${c.track_name} now follows ${c.component_course?.title ?? "its own course"}`,
    { next: "Students on the track see that course's outline." },
  );
  const unpin = useCourseMutation(
    () => coursesApi.pinTrack(courseId, { component_id: c.component_id, pinned_course_id: null }),
    `${c.track_name} has its own outline again`,
  );
  if (track.borrowed_from)
    return (
      <ConfirmDialog
        title={`Stop following ${track.borrowed_from.title}?`}
        consequence={`${c.track_name} goes back to its own outline of this course, which may be empty.`}
        confirmLabel="Stop following"
        onConfirm={() => unpin.mutateAsync(undefined)}
      >
        <Button size="sm" variant="outline" aria-label={`Stop following the outline of ${track.borrowed_from.title} for ${c.track_name}`}>
          Use its own outline
        </Button>
      </ConfirmDialog>
    );
  if (!c.component_course) return null;
  return (
    <ActionDialog
      trigger={
        <Button size="sm" variant="outline" aria-label={`Follow the outline of ${c.component_course.title} for ${c.track_name}`}>
          Follow {c.component_course.course_code}
        </Button>
      }
      title={`Does ${c.track_code} match ${c.component_course.title}?`}
      description="Similar names are not enough. Record how outcomes, scope, depth and assessment match. The track then follows that course's outline."
      fields={[{ name: "note", label: "Review", type: "textarea", required: true, value: c.equivalence_note ?? "" }]}
      submitLabel="Record and follow"
      onSubmit={(v) => pin.mutateAsync(v["note"]!)}
    />
  );
}

export function CourseTracks({ outline, editable }: { outline: CourseOutline; editable: boolean }) {
  const courseId = outline.course.course_id;
  if (outline.tracks.length === 0) return null;
  return (
    <div id="course-tracks" tabIndex={-1} className="scroll-mt-20 space-y-3 outline-none">
      <h3 className="text-base font-semibold">Tracks and booster</h3>
      {outline.tracks.map((t) => (
        <TrackBlock key={t.component.component_id} courseId={courseId} track={t} editable={editable} />
      ))}
    </div>
  );
}

function TrackBlock({ courseId, track, editable }: { courseId: number; track: OutlineTrack; editable: boolean }) {
  const c = track.component;
  const own = !track.borrowed_from;
  const addModule = useCourseMutation((title: string) => coursesApi.addModule(courseId, { title, component_id: c.component_id }), "Module added", {
    next: "Add its topics, then open Details on each to fill them in.",
  });
  const addButton = editable && own && (
    <ActionDialog
      trigger={<Button size="sm">Add module</Button>}
      title={`Add a module to ${c.track_name}`}
      fields={[{ name: "title", label: "Module title", required: true }]}
      onSubmit={(f) => addModule.mutateAsync(f["title"]!)}
    />
  );
  return (
    <section aria-label={`${c.track_name} outline`} className="space-y-2 rounded-lg border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <h4 className="break-words font-medium">
            {c.track_name} <span className="text-sm font-normal text-muted-foreground">({c.role})</span>
          </h4>
          <p className="font-mono text-xs text-muted-foreground">{c.track_code}</p>
          {track.borrowed_from ? (
            <p className="text-sm text-muted-foreground">
              Follows the outline of {track.borrowed_from.title} ({track.borrowed_from.course_code}).
            </p>
          ) : (
            c.equivalence_note && <Tag tone="info">Match to {c.component_course?.title ?? "its course"} checked</Tag>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {addButton}
          {editable && <TrackPin courseId={courseId} track={track} />}
        </div>
      </div>
      <ModuleTree modules={track.modules} editable={editable && own} emptyReason="This track has no modules yet." />
    </section>
  );
}
