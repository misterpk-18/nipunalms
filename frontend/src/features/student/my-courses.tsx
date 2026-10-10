import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { deliveryApi, type MyEnrolment } from "@/api/delivery";
import { EmptyState } from "@/components/lms/empty-state";
import { PageHead, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Meter } from "@/features/shared/attendance-parts";
import { mono } from "@/features/shared/delivery-ui";
import { useLocalised, useT, type TranslationKey } from "@/lib/i18n";

const KIND_KEY: Record<string, TranslationKey> = {
  Combo: "kind_combo",
  Standalone: "kind_standalone",
  "Separately purchased": "kind_separate",
  Complimentary: "kind_complimentary",
};

const NOTE_KEY: Partial<Record<string, TranslationKey>> = {
  "Provisioning Pending": "enrol_note_provisioning",
  "Allocation Pending": "enrol_note_allocation",
  "Allocated — awaiting first regular class": "enrol_note_allocated",
  Paused: "enrol_note_paused",
  Completed: "enrol_note_completed",
  Withdrawn: "enrol_note_withdrawn",
};

/** What the kind of enrolment is, in the reader's language. */
export function useKindLabel() {
  const t = useT();
  return (kind: string) => (KIND_KEY[kind] ? t(KIND_KEY[kind]) : kind);
}

/** What the enrolment's status means for the learner. Nothing is said for a course that is simply in progress. */
export function StatusExplanation({ enrolment }: { enrolment: Pick<MyEnrolment, "status"> }) {
  const t = useT();
  const key = NOTE_KEY[enrolment.status];
  return key ? <p className="text-sm text-muted-foreground">{t(key)}</p> : null;
}

/** The one button a course card leads with: carry on with the next topic. */
export function ContinueButton({ enrolment, size = "default" }: { enrolment: MyEnrolment; size?: "default" | "sm" | "lg" }) {
  const t = useT();
  const pick = useLocalised();
  const next = enrolment.continue_topic;
  if (!next) return null;
  const started = (enrolment.topics?.done ?? 0) > 0;
  const title = pick(next.title, next.title_te);
  return (
    <Button asChild size={size} className="tap h-auto min-h-9 whitespace-normal text-left">
      <Link to="/topics/$topicId" params={{ topicId: String(next.topic_id) }}>
        {started ? t("continueTopic", { title }) : t("startCourse", { title })}
      </Link>
    </Button>
  );
}

export function MyCourses() {
  const t = useT();
  const kindLabel = useKindLabel();
  const query = useQuery({ queryKey: ["delivery", "my-enrolments"], queryFn: deliveryApi.myEnrolments });
  return (
    <div className="mx-auto max-w-6xl">
      <PageHead title={t("myLearning")} description={t("myLearningHelp")} />
      <QueryView query={query} isEmpty={(rows) => rows.length === 0} empty={t("noEnrolments")}>
        {(rows) => (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {rows.map((e) => (
              <section key={e.enrolment_id} className="flex flex-col rounded-xl border bg-card p-4 shadow-sm" aria-label={e.course.title}>
                <div className="flex flex-wrap gap-2">
                  <Tag tone="info">{kindLabel(e.kind)}</Tag>
                  <StatusBadge domain="enrolment" code={e.status} />
                </div>
                <p className="mt-3">{mono(e.course.course_code)}</p>
                <h2 className="font-semibold">{e.course.title}</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {t("batchLabel")}: {e.batch ? e.batch.display_name || e.batch.batch_code : t("notAllocated")}
                </p>
                <div className="mt-3 space-y-3">
                  {e.topics && e.topics.total > 0 ? (
                    <Meter value={e.topics.percent} label={t("topicsDone", { done: e.topics.done, total: e.topics.total })} />
                  ) : (
                    <p className="text-sm text-muted-foreground">{e.batch ? t("noCurriculumYet") : t("noTopicsYet")}</p>
                  )}
                  <StatusExplanation enrolment={e} />
                  {e.continue_topic ? (
                    <ContinueButton enrolment={e} />
                  ) : e.topics && e.topics.total > 0 ? (
                    <p className="text-sm font-medium text-success">{t("courseDone")}</p>
                  ) : null}
                </div>
                <Link
                  to="/courses/$enrolmentId"
                  params={{ enrolmentId: String(e.enrolment_id) }}
                  className="tap mt-auto inline-flex items-center pt-3 text-sm font-medium text-primary underline"
                >
                  {t("openCourse")}
                </Link>
              </section>
            ))}
          </div>
        )}
      </QueryView>
      {query.data?.length === 0 && <EmptyState reason={t("noEnrolments")} />}
    </div>
  );
}
