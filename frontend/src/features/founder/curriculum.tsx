import { useFounderInbox } from "@/api/founder";
import { PageHead, Section } from "@/components/lms/ui";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { CurriculumDecisions } from "@/features/academic/curriculum-model";
import { fmtDate } from "@/features/shared/format";
import { ApprovalsInbox } from "@/features/shared/approvals/inbox";

/** Curriculum versions the Branch Managers have submitted: approve them (and activate in the same step), or send them back. */
export function FounderCurriculum() {
  const inbox = useFounderInbox("curriculum");
  const scheduled = inbox.data?.scheduled ?? [];
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHead
        title="Curriculum approvals"
        description="Review what a new curriculum changes and who it affects, then approve it, activate it or send it back."
      />
      <ApprovalsInbox
        page="/founder/curriculum"
        group="curriculum"
        title="Waiting for you"
        empty="No curriculum is waiting for you. When a Branch Manager submits a new version, it appears here."
      />
      {scheduled.length > 0 && (
        <Section title="Approved, activating on a chosen day">
          <ul className="divide-y text-sm">
            {scheduled.map((v) => (
              <li key={v.curriculum_version_id} className="flex flex-wrap justify-between gap-2 py-2">
                <span>
                  {v.version_label} for {v.course.title}
                </span>
                <span className="text-muted-foreground">Activates on {fmtDate(v.activate_on)}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}
      <HowThisWorks>
        <p>
          A Branch Manager writes a version and submits it. You cannot approve one you submitted yourself. Approving can activate it in the same step, on a day
          you choose, or leave it approved for later. Batches already running stay on their current version.
        </p>
      </HowThisWorks>
      <Section title="Equivalence rules and required-topic constraints">
        <CurriculumDecisions />
      </Section>
    </div>
  );
}
