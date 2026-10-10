import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi, type CurriculumVersion } from "@/api/delivery";
import { Button } from "@/components/ui/button";
import { DataTable, PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { VersionEditor } from "@/features/academic/curriculum";
import { CurriculumDecisions } from "@/features/academic/curriculum-model";
import { fmtDate } from "@/features/shared/delivery-ui";

/** Curriculum versions waiting for the Founder / CEO (or Super Admin): approve after academic review, then activate (Module 14 §5). */
export function FounderCurriculum() {
  const query = useQuery({
    queryKey: ["delivery", "versions", "approvals"],
    queryFn: async () => {
      const [review, approved] = await Promise.all([
        deliveryApi.versions({ status: "Under Review" }),
        deliveryApi.versions({ status: "Approved" }),
      ]);
      return [...review, ...approved];
    },
  });
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHead
        title="Curriculum approvals"
        description="Versions the Branch Managers have submitted. Approve after reviewing them (never your own submission), then activate."
      />
      <Section>
        <QueryView query={query} isEmpty={(rows) => rows.length === 0} empty="No curriculum version is waiting for approval or activation.">
          {(rows) => (
            <DataTable
              caption="Curriculum versions waiting for a decision"
              rows={rows}
              getKey={(v: CurriculumVersion) => v.curriculum_version_id}
              cols={[
                { h: "Course", c: (v) => (v.component ? `${v.component.track_code} — ${v.component.track_name}` : `${v.course.course_code} — ${v.course.title}`) },
                { h: "Version", c: (v) => v.version_label },
                { h: "Status", c: (v) => <StatusBadge domain="curriculum" code={v.status} /> },
                { h: "Content", c: (v) => `${v.counts.modules} module(s), ${v.counts.topics} topic(s)` },
                { h: "Created", c: (v) => fmtDate(v.created_at) },
                {
                  h: "",
                  c: (v) => (
                    <Button size="sm" variant="outline" onClick={() => setOpen(v.curriculum_version_id)}>
                      Review
                    </Button>
                  ),
                },
              ]}
            />
          )}
        </QueryView>
      </Section>
      {open !== null && (
        <Section>
          <VersionEditor key={open} versionId={open} />
        </Section>
      )}
      <Section title="Equivalence rules and required-topic constraints">
        <CurriculumDecisions />
      </Section>
    </div>
  );
}
