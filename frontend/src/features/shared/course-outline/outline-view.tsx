/** A course outline to read: the course's modules and topics, then each combo track's. Trainers and students never edit it. */
import type { CourseOutline } from "@/api/courses";
import { ModuleTree } from "./tree";

export function OutlineView({ outline }: { outline: CourseOutline }) {
  return (
    <div className="space-y-4">
      {(outline.modules.length > 0 || outline.tracks.length === 0) && (
        <ModuleTree modules={outline.modules} editable={false} emptyReason="This course has no modules yet." />
      )}
      {outline.tracks.map((t) => (
        <section key={t.component.component_id} aria-label={`${t.component.track_name} outline`}>
          <h3 className="mb-2 text-sm font-semibold">
            {t.component.track_name}
            {t.borrowed_from && <span className="font-normal text-muted-foreground"> · outline of {t.borrowed_from.title}</span>}
          </h3>
          <ModuleTree modules={t.modules} editable={false} emptyReason="This track has no modules yet." />
        </section>
      ))}
    </div>
  );
}
