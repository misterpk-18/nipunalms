import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { curriculumApi, type ChecklistStepKey, type ChecklistTopicItem } from "@/api/curriculum";
import { deliveryApi, type CurriculumRow, type CurriculumVersion } from "@/api/delivery";
import { useAuth } from "@/auth/auth";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { EmptyState } from "@/components/lms/empty-state";
import { DataTable, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { SubmitChecklist, scrollToId, STEP_TARGET, topicDomId } from "@/features/branch/curriculum-checklist";
import { NewDraftDialog } from "@/features/branch/curriculum-new-draft";
import { useCurriculumMutation } from "@/features/branch/curriculum-pickers";
import { ModuleTree } from "@/features/branch/curriculum-tree";
import { ActionDialog, fmtDate, mono } from "@/features/shared/delivery-ui";
import { ComboPins, CurriculumDecisions, CurriculumHowItWorks, EquivalenceReview, RecordVariation, VersionPlanning } from "./curriculum-model";

type Slot = { course_id: number; component_id: number | null; label: string };

const slotOf = (row: CurriculumRow): Slot => ({
  course_id: row.course.course_id,
  component_id: row.component?.component_id ?? null,
  label: row.component ? `${row.component.track_name} (${row.component.track_code})` : `${row.course.title} (${row.course.course_code})`,
});

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** Branch Managers draft, submit and review; the Founder / CEO or Super Admin approve, activate and retire. */
export function VersionEditor({ versionId, onDiscarded }: { versionId: number; onDiscarded?: () => void }) {
  const { hasRole } = useAuth();
  const author = hasRole("BRANCH_MANAGER", "SUPER_ADMIN");
  const approver = hasRole("FOUNDER_CEO", "SUPER_ADMIN");
  const [openTopic, setOpenTopic] = useState<number | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [assessmentOpen, setAssessmentOpen] = useState(false);
  const [moduleOpen, setModuleOpen] = useState(false);
  const query = useQuery({ queryKey: ["delivery", "version", versionId], queryFn: () => curriculumApi.version(versionId) });

  const submit = useCurriculumMutation(() => deliveryApi.versionAction(versionId, "submit"), "Sent for review", {
    next: "The Founder / CEO or a Super Admin approves it or sends it back with a reason.",
  });
  const approve = useCurriculumMutation(() => deliveryApi.versionAction(versionId, "approve"), "Approved", { next: "It can be activated now." });
  const activate = useCurriculumMutation(() => deliveryApi.versionAction(versionId, "activate"), "Activated", {
    next: (v: CurriculumVersion) =>
      v.released && (v.released.batches_mapped || v.released.enrolments_released)
        ? `${plural(v.released.batches_mapped, "batch", "batches")} and ${plural(v.released.enrolments_released, "student")} that had no curriculum now use it.`
        : "New batches now use it.",
  });
  const retire = useCurriculumMutation(() => deliveryApi.versionAction(versionId, "retire"), "Retired", {
    next: "Batches and students already on it keep it.",
  });
  const giveBack = useCurriculumMutation((reason: string) => deliveryApi.versionAction(versionId, "return", { reason }), "Returned to draft", {
    next: "The Branch Manager can change it again.",
  });
  const rename = useCurriculumMutation((label: string) => deliveryApi.renameVersion(versionId, label), "Draft renamed");
  const discard = useCurriculumMutation(() => deliveryApi.deleteVersion(versionId), "Draft discarded", { onSuccess: () => onDiscarded?.() });
  const addModule = useCurriculumMutation((title: string) => deliveryApi.addModule(versionId, { title }), "Module added", {
    next: "Add its topics, then open Details on each to fill them in.",
  });

  return (
    <QueryView query={query} skeleton="detail">
      {(v) => {
        const draft = v.status === "Draft";
        const editable = draft && author;
        const modules = v.modules ?? [];
        const checklist = editable ? v.checklist : undefined;
        const missingByTopic = new Map<number, string[]>();
        for (const step of checklist?.steps ?? []) {
          if (step.key !== "topics") continue;
          for (const item of step.items) if ("topic_id" in item) missingByTopic.set(item.topic_id, item.missing);
        }
        const openIncomplete = (item: ChecklistTopicItem) => {
          setOpenTopic(item.topic_id);
          window.setTimeout(() => scrollToId(topicDomId(item.topic_id)), 0);
        };
        const go = (key: ChecklistStepKey) => {
          const topicsStep = checklist?.steps.find((s) => s.key === "topics");
          const first = topicsStep?.items.find((i): i is ChecklistTopicItem => "topic_id" in i);
          if (key === "topics" && first) return openIncomplete(first);
          if (key === "modules" && modules.length === 0) return setModuleOpen(true);
          scrollToId(STEP_TARGET[key]);
          if (key === "rules") setProfileOpen(true);
          if (key === "assessments") setAssessmentOpen(true);
        };
        const addModuleButton = (
          <ActionDialog
            open={moduleOpen}
            onOpenChange={setModuleOpen}
            trigger={<Button size="sm">Add module</Button>}
            title="Add a module"
            fields={[{ name: "title", label: "Module title", required: true }]}
            onSubmit={(f) => addModule.mutateAsync(f["title"]!)}
          />
        );
        return (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <h3 className="break-words text-lg font-semibold">
                  {v.version_label} <StatusBadge domain="curriculum" code={v.status} />
                </h3>
                <p className="text-sm text-muted-foreground">
                  {plural(v.counts.modules, "module")}, {plural(v.counts.topics, "topic")}, {v.counts.required_topics} required · used by{" "}
                  {plural(v.usage.batches, "batch", "batches")} and {plural(v.usage.enrolments + v.usage.tracks, "student")}
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {editable && (
                  <>
                    <ActionDialog
                      trigger={
                        <Button size="sm" variant="outline">
                          Rename
                        </Button>
                      }
                      title="Rename draft"
                      description="The name was chosen for you. Change it if you prefer another."
                      fields={[{ name: "label", label: "Name", required: true, value: v.version_label }]}
                      onSubmit={(f) => rename.mutateAsync(f["label"]!)}
                    />
                    <ConfirmDialog
                      title={`Discard draft ${v.version_label}?`}
                      consequence={`Discard ${v.version_label} and everything in it (${plural(v.counts.modules, "module")}, ${plural(v.counts.topics, "topic")})? This cannot be undone.`}
                      confirmLabel="Discard draft"
                      destructive
                      onConfirm={() => discard.mutateAsync(undefined)}
                    >
                      <Button size="sm" variant="outline">
                        Discard draft
                      </Button>
                    </ConfirmDialog>
                  </>
                )}
                {v.status === "Under Review" && (
                  <>
                    {approver && (
                      <Button size="sm" disabled={approve.isPending} onClick={() => approve.mutate(undefined)}>
                        Approve
                      </Button>
                    )}
                    <ActionDialog
                      trigger={
                        <Button size="sm" variant="outline">
                          Return to draft
                        </Button>
                      }
                      title="Return to draft"
                      fields={[{ name: "reason", label: "What needs to change", type: "textarea", required: true }]}
                      submitLabel="Return"
                      onSubmit={(f) => giveBack.mutateAsync(f["reason"]!)}
                    />
                  </>
                )}
                {approver && v.status === "Approved" && (
                  <ConfirmDialog
                    title={`Activate ${v.version_label}?`}
                    consequence="It replaces the current Active version for new batches. Batches and students already on the old version keep it; batches with no curriculum yet start using this one."
                    confirmLabel="Activate"
                    onConfirm={() => activate.mutateAsync(undefined)}
                  >
                    <Button size="sm">Activate</Button>
                  </ConfirmDialog>
                )}
                {approver && (v.status === "Approved" || v.status === "Active") && (
                  <ConfirmDialog
                    title={`Retire ${v.version_label}?`}
                    consequence={`Batches and students already on ${v.version_label} keep it. New batches will have no curriculum until another version is activated.`}
                    confirmLabel="Retire version"
                    destructive
                    onConfirm={() => retire.mutateAsync(undefined)}
                  >
                    <Button size="sm" variant="outline">
                      Retire
                    </Button>
                  </ConfirmDialog>
                )}
              </div>
            </div>

            {!author && (v.status === "Under Review" || v.status === "Approved") && (
              <StatusNote tone="info">
                {v.status === "Under Review" ? "Waiting for approval" : "Approved, waiting to be activated"} by the Founder / CEO or a Super Admin.
              </StatusNote>
            )}
            {author && v.status === "Under Review" && (
              <StatusNote tone="info">Submitted. Waiting for the Founder / CEO or a Super Admin to approve it or send it back.</StatusNote>
            )}
            {!draft && (
              <StatusNote tone="info">
                {v.status} versions cannot be edited because batches and students point at them. To change the curriculum, start a new draft.
              </StatusNote>
            )}

            {checklist && (
              <SubmitChecklist
                checklist={checklist}
                canSubmit={editable}
                submitting={submit.isPending}
                onGo={go}
                onOpenTopic={openIncomplete}
                onSubmit={() => submit.mutate(undefined)}
              />
            )}
            {draft && !checklist && v.blockers && v.blockers.length > 0 && <StatusNote tone="warning">Before review: {v.blockers.join("; ")}.</StatusNote>}

            <ComboPins version={v} editable={editable} />

            <Section id="cv-modules" title="Modules and topics" actions={editable && modules.length > 0 ? addModuleButton : undefined}>
              <ModuleTree
                modules={modules}
                editable={editable}
                author={author}
                missingByTopic={missingByTopic}
                openTopic={openTopic}
                setOpenTopic={setOpenTopic}
                addAction={editable && modules.length === 0 ? addModuleButton : undefined}
              />
              {editable && modules.length > 1 && (
                <p className="mt-2 text-xs text-muted-foreground">Drag a row by its handle to reorder it, or use Move up and Move down.</p>
              )}
            </Section>

            <VersionPlanning
              version={v}
              editable={editable}
              author={author}
              profileOpen={profileOpen}
              onProfileOpenChange={setProfileOpen}
              assessmentOpen={assessmentOpen}
              onAssessmentOpenChange={setAssessmentOpen}
            />
            {author && (v.status === "Approved" || v.status === "Active") && <RecordVariation version={v} />}

            <details className="text-sm">
              <summary className="cursor-pointer font-medium">History ({v.events?.length ?? 0})</summary>
              <ul className="mt-2 space-y-1">
                {(v.events ?? []).map((e) => (
                  <li key={e.event_id}>
                    {fmtDate(e.created_at)} · <strong>{e.action}</strong> ({e.from_status ?? "—"} → {e.to_status}) by {e.actor?.full_name ?? "the system"}
                    {e.note ? `: ${e.note}` : ""}
                  </li>
                ))}
              </ul>
            </details>
          </div>
        );
      }}
    </QueryView>
  );
}

const defaultVersion = (list: CurriculumVersion[]) =>
  (list.find((v) => v.status === "Draft" || v.status === "Under Review" || v.status === "Approved") ?? list.find((v) => v.status === "Active") ?? list[0])
    ?.curriculum_version_id ?? null;

function SlotPanel({ slot }: { slot: Slot }) {
  const [selected, setSelected] = useState<number | null>(null);
  const top = useRef<HTMLDivElement>(null);
  useEffect(() => {
    top.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);
  const versions = useQuery({
    queryKey: ["delivery", "versions", slot.course_id, slot.component_id],
    queryFn: () =>
      deliveryApi.versions(
        slot.component_id === null ? { course_id: slot.course_id, whole_course: true } : { course_id: slot.course_id, component_id: slot.component_id },
      ),
  });
  const list = versions.data ?? [];
  const chosen = selected !== null && list.some((v) => v.curriculum_version_id === selected) ? selected : defaultVersion(list);
  const newDraft = versions.data && <NewDraftDialog courseId={slot.course_id} componentId={slot.component_id} versions={list} onCreated={setSelected} />;
  return (
    <div ref={top} className="scroll-mt-20">
      <Section title={`Versions of ${slot.label}`} actions={newDraft}>
        <QueryView
          query={versions}
          isEmpty={(l) => l.length === 0}
          empty="There is no curriculum for this yet, so batches of it have nothing to follow. Start the first draft."
          emptyAction={newDraft}
        >
          {(l) => (
            <div className="space-y-4">
              <ul className="flex flex-wrap gap-2" aria-label="Versions">
                {l.map((v) => (
                  <li key={v.curriculum_version_id}>
                    <Button
                      size="sm"
                      variant={chosen === v.curriculum_version_id ? "default" : "outline"}
                      aria-pressed={chosen === v.curriculum_version_id}
                      onClick={() => setSelected(v.curriculum_version_id)}
                    >
                      {v.version_label} · {v.status}
                    </Button>
                  </li>
                ))}
              </ul>
              {chosen !== null ? (
                <VersionEditor key={chosen} versionId={chosen} onDiscarded={() => setSelected(null)} />
              ) : (
                <EmptyState reason="Choose a version to view or edit it." />
              )}
            </div>
          )}
        </QueryView>
      </Section>
    </div>
  );
}

export function AcademicCurriculum() {
  const [slot, setSlot] = useState<Slot | null>(null);
  const query = useQuery({ queryKey: ["delivery", "curriculum-overview"], queryFn: deliveryApi.curriculumOverview });
  return (
    <>
      <PageHead title="Curriculum" description="The modules, topics and completion rules of each course and track. New batches follow the Active version." />
      <div className="space-y-6">
        <QueryView query={query} isEmpty={(rows) => rows.length === 0} empty="No course exists yet, so there is no curriculum to write.">
          {(rows) => (
            <DataTable
              caption="Curriculum of each course and track"
              rows={rows}
              getKey={(r) => `${r.course.course_id}-${r.component?.component_id ?? 0}`}
              cols={[
                {
                  h: "Course or track",
                  c: (r) => (
                    <>
                      <div className="font-medium">{r.component ? `${r.component.track_name} (${r.component.role})` : r.course.title}</div>
                      {mono(r.component ? r.component.track_code : r.course.course_code)}
                    </>
                  ),
                },
                {
                  h: "Active version",
                  c: (r) =>
                    r.active_version ? (
                      <>
                        {r.active_version.version_label}
                        {r.borrowed_from && <div className="text-xs text-muted-foreground">uses the curriculum of {r.borrowed_from.course_code}</div>}
                      </>
                    ) : (
                      "None yet"
                    ),
                },
                {
                  h: "In progress",
                  c: (r) =>
                    r.latest_version && r.latest_version.status !== "Active" ? (
                      <>
                        {r.latest_version.version_label} <StatusBadge domain="curriculum" code={r.latest_version.status} />
                      </>
                    ) : (
                      "Nothing"
                    ),
                },
                {
                  h: "New batches",
                  c: (r) => (
                    <>
                      <StatusBadge
                        domain="readiness"
                        code={r.active_version ? "Ready" : "Blocked"}
                        label={r.active_version ? "Have a curriculum" : "No Active version yet"}
                      />
                      {r.waiting_batches > 0 && (
                        <div className="mt-1 text-xs text-muted-foreground">{plural(r.waiting_batches, "batch", "batches")} waiting for a curriculum</div>
                      )}
                    </>
                  ),
                },
                {
                  h: "",
                  c: (r) => (
                    <span className="flex flex-wrap gap-1.5">
                      <Button size="sm" variant={slot && slotOf(r).label === slot.label ? "default" : "outline"} onClick={() => setSlot(slotOf(r))}>
                        Manage versions
                      </Button>
                      {r.component?.role === "Included booster" && r.component.component_course && (
                        <EquivalenceReview componentId={r.component.component_id} trackCode={r.component.track_code} note={r.component.equivalence_note} />
                      )}
                    </span>
                  ),
                },
              ]}
            />
          )}
        </QueryView>
        {slot && <SlotPanel key={`${slot.course_id}-${slot.component_id}`} slot={slot} />}
        <Section title="Waiting for a decision">
          <CurriculumDecisions />
        </Section>
        <CurriculumHowItWorks />
      </div>
    </>
  );
}
