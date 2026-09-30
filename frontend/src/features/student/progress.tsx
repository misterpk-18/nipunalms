import { useState } from "react";
import { useMyProgress } from "@/api/attendance";
import { PageHead, PillTabs, QueryView } from "@/components/lms/ui";
import { CompletionNote, MeasureCards } from "@/features/shared/attendance-parts";
import { useT } from "@/lib/i18n";

export function Progress() {
  const t = useT();
  const query = useMyProgress();
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <div className="mx-auto max-w-5xl">
      <PageHead title={t("progress")} description="Four measures, never merged into one score" />
      <QueryView query={query} isEmpty={(blocks) => blocks.length === 0} empty="Progress appears once you are studying a course.">
        {(blocks) => {
          const labels = blocks.map((b) => b.enrolment.course.course_code);
          const active = blocks.find((b) => b.enrolment.course.course_code === (selected ?? labels[0])) ?? blocks[0]!;
          return (
            <div className="space-y-4">
              {blocks.length > 1 && <PillTabs label="Course" tabs={labels} value={active.enrolment.course.course_code} onChange={setSelected} />}
              <p className="text-sm text-muted-foreground">
                {active.enrolment.course.course_code} · {active.enrolment.course.title}
                {active.batch && ` · ${active.batch.batch_code}`}
              </p>
              <MeasureCards measures={active} />
              <CompletionNote />
            </div>
          );
        }}
      </QueryView>
    </div>
  );
}
