/** The curriculum screens: topic details and prerequisites, hours and the completion rules, required
 * assessments, track versions, the reusable library, student moves, equivalence rules and branch variations. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/api/client";
import { deliveryApi, type Component, type CurriculumVersion, type ModuleContent, type TopicRow } from "@/api/delivery";
import { useAuth } from "@/auth/auth";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { Field, NativeSelect } from "@/components/lms/forms";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { DataTable, QueryView, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { topicChoices, TopicMultiPicker, useCurriculumMutation } from "@/features/branch/curriculum-pickers";
import { ActionDialog } from "@/features/shared/delivery-ui";

const hours = (minutes: number) => `${(minutes / 60).toFixed(1)} h`;
const DECISIONS = [
  { value: "", label: "Choose a decision" },
  { value: "Approved", label: "Approve" },
  { value: "Rejected", label: "Reject" },
];

/** The messages a 422 carries per field, or the plain message. */
function serverMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const found = Object.values(error.details ?? {}).flatMap((m) => (Array.isArray(m) ? m.map(String) : [String(m)]));
    return found.length ? found.join(" ") : error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong";
}

function TopicForm({ topic, modules, onDone }: { topic: TopicRow; modules: ModuleContent[]; onDone: () => void }) {
  const [form, setForm] = useState({
    topic_class: topic.topic_class as string,
    outcome: topic.outcome ?? "",
    instructional_minutes: topic.instructional_minutes?.toString() ?? "",
    independent_minutes: topic.independent_minutes?.toString() ?? "",
    weight: topic.weight?.toString() ?? "",
    evidence: topic.evidence ?? "",
    activities: topic.activities ?? "",
  });
  const [depends, setDepends] = useState<number[]>(topic.depends_on);
  const [error, setError] = useState<string | null>(null);
  const save = useCurriculumMutation((body: Record<string, unknown>) => deliveryApi.updateTopic(topic.topic_id, body), `Saved ${topic.title}`, {
    silentValidation: true,
  });
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const number = (value: string) => (value.trim() ? Number(value) : null);
  const choices = topicChoices(modules).filter((c) => c.topic_id !== topic.topic_id);
  return (
    <form
      className="space-y-3"
      onSubmit={async (event) => {
        event.preventDefault();
        setError(null);
        try {
          await save.mutateAsync({
            topic_class: form.topic_class,
            outcome: form.outcome.trim() || null,
            instructional_minutes: number(form.instructional_minutes),
            independent_minutes: number(form.independent_minutes),
            weight: number(form.weight),
            evidence: form.evidence.trim() || null,
            activities: form.activities.trim() || null,
            depends_on: depends,
          });
          onDone();
        } catch (e) {
          setError(serverMessage(e));
        }
      }}
    >
      {error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      <Field label="Class" htmlFor="td-class" hint="Only Required topics count towards a student's required learning.">
        <NativeSelect
          id="td-class"
          value={form.topic_class}
          options={["Required", "Recommended", "Optional"].map((c) => ({ value: c, label: c }))}
          onChange={(e) => set("topic_class")(e.target.value)}
        />
      </Field>
      <Field label="Learning outcome" htmlFor="td-outcome" hint="What a student can do after this topic.">
        <Textarea id="td-outcome" rows={3} value={form.outcome} onChange={(e) => set("outcome")(e.target.value)} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Estimated minutes taught" htmlFor="td-instr">
          <Input id="td-instr" type="number" min={0} value={form.instructional_minutes} onChange={(e) => set("instructional_minutes")(e.target.value)} />
        </Field>
        <Field label="Estimated self-study minutes" htmlFor="td-indep">
          <Input id="td-indep" type="number" min={0} value={form.independent_minutes} onChange={(e) => set("independent_minutes")(e.target.value)} />
        </Field>
      </div>
      <Field label="Progress weight" htmlFor="td-weight" hint="How much of the course this topic is worth when progress is counted.">
        <Input id="td-weight" type="number" min={0} step="any" value={form.weight} onChange={(e) => set("weight")(e.target.value)} />
      </Field>
      <Field label="Evidence of completion" htmlFor="td-evidence" hint="What shows the topic was learned (a task, a quiz, a demo).">
        <Textarea id="td-evidence" rows={2} value={form.evidence} onChange={(e) => set("evidence")(e.target.value)} />
      </Field>
      <Field label="Activities" htmlFor="td-activities">
        <Textarea id="td-activities" rows={2} value={form.activities} onChange={(e) => set("activities")(e.target.value)} />
      </Field>
      <Field label="Topics to learn first (optional)" hint="Only where a student really needs one topic before this one.">
        <TopicMultiPicker label="Topics to learn first" choices={choices} value={depends} onChange={setDepends} />
      </Field>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={save.isPending}>
          Save topic
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Outcome, class, minutes, weight, evidence and prerequisites of one topic. Opens from the row or from the submit checklist. */
export function TopicDetails({
  topic,
  modules,
  editable,
  open,
  onOpenChange,
}: {
  topic: TopicRow;
  modules: ModuleContent[];
  editable: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [own, setOwn] = useState(false);
  const isOpen = open ?? own;
  const setOpen = (next: boolean) => {
    setOwn(next);
    onOpenChange?.(next);
  };
  if (!editable) return null;
  return (
    <Dialog open={isOpen} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="ghost" aria-label={`Details of topic ${topic.title}`}>
          Details
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Topic: {topic.title}</DialogTitle>
          <DialogDescription>
            A Required topic needs an outcome, estimated minutes, a progress weight and evidence before the version can be submitted.
          </DialogDescription>
        </DialogHeader>
        <TopicForm topic={topic} modules={modules} onDone={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  );
}

export function topicSummary(t: TopicRow) {
  const parts = [t.outcome, t.instructional_minutes !== null ? `${t.instructional_minutes} min taught` : null, t.weight ? `weight ${t.weight}` : null];
  return parts.filter(Boolean).join(" · ");
}

/** Hours, completion rules, required assessments and library inserts for one version. The dialogs can be opened from the submit checklist. */
export function VersionPlanning({
  version,
  editable,
  author,
  profileOpen,
  onProfileOpenChange,
  assessmentOpen,
  onAssessmentOpenChange,
}: {
  version: CurriculumVersion;
  editable: boolean;
  author: boolean;
  profileOpen?: boolean;
  onProfileOpenChange?: (open: boolean) => void;
  assessmentOpen?: boolean;
  onAssessmentOpenChange?: (open: boolean) => void;
}) {
  const id = version.curriculum_version_id;
  const verify = useCurriculumMutation(() => deliveryApi.verifyHours(id), "Hours verified");
  const profile = useCurriculumMutation(
    (v: Record<string, string>) =>
      deliveryApi.setCompletionProfile(id, {
        attendance_minimum_pct: Number(v["attendance_minimum_pct"]),
        pass_mark_pct: Number(v["pass_mark_pct"]),
        recovery_rule: v["recovery_rule"]!,
        reassessment_rule: v["reassessment_rule"]!,
      }),
    "Completion rules saved",
  );
  const addRequirement = useCurriculumMutation((body: Record<string, unknown>) => deliveryApi.addRequirement(id, body), "Required assessment added");
  const deleteRequirement = useCurriculumMutation((requirementId: number) => deliveryApi.deleteRequirement(requirementId), "Required assessment removed");
  const library = useQuery({ queryKey: ["delivery", "library"], queryFn: deliveryApi.library, enabled: editable });
  const insert = useCurriculumMutation((libraryVersionId: number) => deliveryApi.insertLibraryModule(id, libraryVersionId), "Library module added");
  const totals = version.totals;
  const p = version.completion_profile;
  const approvedLibrary = (library.data?.data ?? []).filter((m) => m.current_version);
  const topicOptions = topicChoices(version.modules ?? []);
  const topicName = (topicId: number | null) => topicOptions.find((t) => t.topic_id === topicId)?.label;
  const manage = editable && author;

  return (
    <div className="grid gap-3 rounded-lg border p-3 text-sm sm:grid-cols-2">
      <div id="cv-hours" tabIndex={-1} className="scroll-mt-20 space-y-1 outline-none">
        <h4 className="font-semibold">Hours</h4>
        {totals && (
          <>
            <p>
              Taught {hours(totals.instructional_minutes)} · self-study {hours(totals.independent_minutes)} · total {hours(totals.total_minutes)}
            </p>
            {totals.booster && (
              <p className="text-muted-foreground">
                Included booster {totals.booster.track_code}: {hours(totals.booster.total_minutes)}
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
      <div id="cv-rules" tabIndex={-1} className="scroll-mt-20 space-y-1 outline-none">
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
            open={profileOpen}
            onOpenChange={onProfileOpenChange}
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
      <div id="cv-assessments" tabIndex={-1} className="scroll-mt-20 space-y-1 outline-none sm:col-span-2">
        <h4 className="font-semibold">Required assessments</h4>
        {(version.assessment_requirements ?? []).length === 0 ? (
          <p className="text-muted-foreground">None yet. A test or assignment marked required must be linked to one of these.</p>
        ) : (
          <ul className="space-y-1">
            {version.assessment_requirements!.map((r) => (
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
            open={assessmentOpen}
            onOpenChange={onAssessmentOpenChange}
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
            description="The module is copied as it is now. Later changes to the library do not change this draft."
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

/** One track or booster of a combo: pick its version by name. A booster may use its own course's version once someone has checked that it matches the course. */
function PinVersion({ version, component }: { version: CurriculumVersion; component: Component }) {
  const [open, setOpen] = useState(false);
  const own = useQuery({
    queryKey: ["delivery", "versions", "pinnable", version.course.course_id],
    queryFn: async () => (await deliveryApi.versions({ course_id: version.course.course_id })).filter((v) => v.status === "Approved" || v.status === "Active"),
    enabled: open,
  });
  const boosterCourse = component.component_course?.course_id;
  const booster = useQuery({
    queryKey: ["delivery", "versions", "pinnable-booster", boosterCourse],
    queryFn: async () =>
      (await deliveryApi.versions({ course_id: boosterCourse!, whole_course: true })).filter((v) => v.status === "Approved" || v.status === "Active"),
    enabled: open && boosterCourse !== undefined,
  });
  const pin = useCurriculumMutation(
    (versionId: number) => deliveryApi.pinComponent(version.curriculum_version_id, { component_id: component.component_id, component_version_id: versionId }),
    `Pinned a version for ${component.track_name}`,
  );
  const options = [
    ...(own.data ?? [])
      .filter((v) => v.component?.component_id === component.component_id)
      .map((v) => ({ value: v.curriculum_version_id, label: `${v.version_label} (${v.status}) for this track` })),
    ...(booster.data ?? []).map((v) => ({
      value: v.curriculum_version_id,
      label: `${v.version_label} (${v.status}) from ${component.component_course?.title ?? "its own course"}`,
    })),
  ];
  return (
    <ActionDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <Button size="sm" variant="outline" aria-label={`Pin a version for ${component.track_name}`}>
          Pin version
        </Button>
      }
      title={`Pin a version for ${component.track_name}`}
      description={
        options.length === 0 && !own.isPending && !booster.isPending
          ? "There is no Approved or Active version for this track yet. Write and approve one first."
          : "Choose the exact version this programme version uses. A booster can use its own course's version once someone has checked that it matches the course."
      }
      fields={[{ name: "component_version_id", label: "Version", type: "select", required: true, options }]}
      onSubmit={(v) => pin.mutateAsync(Number(v["component_version_id"]))}
    />
  );
}

function useComponents(version: CurriculumVersion) {
  const overview = useQuery({ queryKey: ["delivery", "curriculum-overview"], queryFn: deliveryApi.curriculumOverview, enabled: version.component === null });
  return (overview.data ?? []).filter((r) => r.course.course_id === version.course.course_id && r.component).map((r) => r.component!);
}

/** A combo parent pins the exact version of each track and the booster. */
export function ComboPins({ version, editable }: { version: CurriculumVersion; editable: boolean }) {
  const components = useComponents(version);
  if (components.length === 0) return null;
  const pinned = new Map((version.components ?? []).map((c) => [c.component_id, c.component_version]));
  return (
    <div id="cv-tracks" tabIndex={-1} className="scroll-mt-20 rounded-lg border p-3 text-sm outline-none">
      <h4 className="font-semibold">Tracks and booster in this programme version</h4>
      <ul className="mt-1 space-y-1">
        {components.map((c) => (
          <li key={c.component_id} className="flex flex-wrap items-center justify-between gap-2">
            <span>
              {c.track_name} ({c.role}): {pinned.get(c.component_id)?.version_label ?? <Tag tone="warning">No version pinned yet</Tag>}
            </span>
            {editable && <PinVersion version={version} component={c} />}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Record that a combo component matches its standalone course in outcomes, scope, depth and assessment. */
export function EquivalenceReview({ componentId, trackCode, note }: { componentId: number; trackCode: string; note?: string | null }) {
  const review = useCurriculumMutation((text: string) => deliveryApi.reviewEquivalence(componentId, text), "Review recorded");
  return (
    <ActionDialog
      trigger={
        <Button size="sm" variant="outline">
          {note ? "Update the match check" : "Check it matches the course"}
        </Button>
      }
      title={`Does ${trackCode} match the course?`}
      description="Similar names are not enough. Record how outcomes, scope, depth and assessment match before the booster reuses the course curriculum."
      fields={[{ name: "note", label: "Review", type: "textarea", required: true, value: note ?? "" }]}
      onSubmit={(v) => review.mutateAsync(v["note"]!)}
    />
  );
}

export function SaveToLibrary({ module }: { module: ModuleContent }) {
  const save = useCurriculumMutation(() => deliveryApi.saveToLibrary(module.module_id), "Proposed to the library", {
    next: "Another reviewer approves it before others can reuse it.",
  });
  return (
    <Button
      size="sm"
      variant="ghost"
      aria-label={`Save module ${module.title} to the library`}
      disabled={save.isPending}
      onClick={() => save.mutate(undefined)}
    >
      Save to library
    </Button>
  );
}

/** Student moves, equivalence rules, variations and library versions waiting for the signed-in reviewer. */
export function CurriculumDecisions() {
  const { hasRole, profile } = useAuth();
  const me = profile?.user.user_id;
  const central = hasRole("FOUNDER_CEO", "SUPER_ADMIN");
  const reviewer = hasRole("BRANCH_MANAGER", "SUPER_ADMIN");
  const mappings = useQuery({ queryKey: ["delivery", "mappings"], queryFn: () => deliveryApi.mappings({ status: "Pending" }) });
  const rules = useQuery({ queryKey: ["delivery", "rules"], queryFn: () => deliveryApi.rules({ status: "Pending" }) });
  const variations = useQuery({ queryKey: ["delivery", "variations"], queryFn: () => deliveryApi.variations({ status: "Pending" }) });
  const library = useQuery({ queryKey: ["delivery", "library"], queryFn: deliveryApi.library });
  const decideMapping = useCurriculumMutation(
    (v: { id: number; body: { decision: string; note?: string; student_acceptance?: string } }) => deliveryApi.decideMapping(v.id, v.body),
    "Decision recorded",
  );
  const decideRule = useCurriculumMutation(
    (v: { id: number; body: { decision: string; note?: string } }) => deliveryApi.decideRule(v.id, v.body),
    "Decision recorded",
  );
  const decideVariation = useCurriculumMutation(
    (v: { id: number; body: { decision: string; note?: string } }) => deliveryApi.decideVariation(v.id, v.body),
    "Decision recorded",
  );
  const decideLibrary = useCurriculumMutation((v: { id: number; decision: string }) => deliveryApi.decideLibraryVersion(v.id, v.decision), "Decision recorded");
  const pendingLibrary = (library.data?.data ?? []).flatMap((m) => m.versions.filter((v) => v.status === "Pending").map((v) => ({ m, v })));
  const decisionFields = [
    { name: "decision", label: "Decision", type: "select" as const, options: DECISIONS, required: true },
    { name: "note", label: "Note (needed if you reject)", type: "textarea" as const },
  ];

  return (
    <div className="space-y-4">
      <QueryView query={mappings} isEmpty={(p) => p.data.length === 0} empty="No student is waiting to move to another version.">
        {(page) => (
          <DataTable
            caption="Students waiting to move to another version"
            rows={page.data}
            getKey={(m) => m.mapping_id}
            cols={[
              { h: "Move from / to", c: (m) => `${m.from_version?.version_label ?? "—"} → ${m.to_version.version_label}` },
              { h: "Comparison and plan", c: (m) => `${m.comparison} · Plan: ${m.migration_plan}` },
              { h: "Earlier work credited", c: (m) => String(m.proposed_credits.length) },
              { h: "Prepared by", c: (m) => m.requested_by.full_name },
              {
                h: "",
                c: (m) =>
                  reviewer && m.requested_by.user_id !== me ? (
                    <ActionDialog
                      trigger={<Button size="sm">Decide</Button>}
                      title="Move to another version"
                      fields={[...decisionFields, { name: "student_acceptance", label: "How the student agreed (needed to approve)", type: "textarea" }]}
                      onSubmit={(v) =>
                        decideMapping.mutateAsync({
                          id: m.mapping_id,
                          body: { decision: v["decision"]!, note: v["note"] || undefined, student_acceptance: v["student_acceptance"] || undefined },
                        })
                      }
                    />
                  ) : null,
              },
            ]}
          />
        )}
      </QueryView>
      <QueryView query={rules} isEmpty={(p) => p.data.length === 0} empty="No rule about matching versions is waiting.">
        {(page) => (
          <DataTable
            caption="Rules about matching versions, waiting for the Founder / CEO or Super Admin"
            rows={page.data}
            getKey={(r) => r.rule_id}
            cols={[
              { h: "Rule", c: (r) => r.description },
              { h: "Proposed by", c: (r) => r.requested_by.full_name },
              {
                h: "",
                c: (r) =>
                  central && r.requested_by.user_id !== me ? (
                    <ActionDialog
                      trigger={<Button size="sm">Decide</Button>}
                      title="Rule about matching versions"
                      fields={decisionFields}
                      onSubmit={(v) => decideRule.mutateAsync({ id: r.rule_id, body: { decision: v["decision"]!, note: v["note"] || undefined } })}
                    />
                  ) : null,
              },
            ]}
          />
        )}
      </QueryView>
      <QueryView query={variations} isEmpty={(p) => p.data.length === 0} empty="No branch change is waiting.">
        {(page) => (
          <DataTable
            caption="Branch changes waiting for a decision"
            rows={page.data}
            getKey={(x) => x.variation_id}
            cols={[
              { h: "Kind", c: (x) => <Tag>{x.kind}</Tag> },
              { h: "Change", c: (x) => [x.description, x.remedial_plan && `Remedial plan: ${x.remedial_plan}`].filter(Boolean).join(" · ") },
              { h: "Recorded by", c: (x) => x.requested_by.full_name },
              {
                h: "",
                c: (x) =>
                  (x.kind === "Required topic constraint" ? central : reviewer) && x.requested_by.user_id !== me ? (
                    <ActionDialog
                      trigger={<Button size="sm">Decide</Button>}
                      title={x.kind}
                      fields={decisionFields}
                      onSubmit={(v) => decideVariation.mutateAsync({ id: x.variation_id, body: { decision: v["decision"]!, note: v["note"] || undefined } })}
                    />
                  ) : null,
              },
            ]}
          />
        )}
      </QueryView>
      {reviewer && pendingLibrary.length > 0 && (
        <DataTable
          caption="Library modules waiting for review"
          rows={pendingLibrary}
          getKey={({ v }) => v.library_version_id}
          cols={[
            { h: "Module", c: ({ m, v }) => `${m.title} (version ${v.version_no})` },
            { h: "Topics", c: ({ v }) => v.content.topics.map((t) => t.title).join(", ") },
            { h: "Change", c: ({ v }) => v.change_note ?? "—" },
            {
              h: "",
              c: ({ v }) =>
                v.proposed_by !== me ? (
                  <span className="flex gap-1.5">
                    <Button size="sm" onClick={() => decideLibrary.mutate({ id: v.library_version_id, decision: "Approved" })}>
                      Approve
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => decideLibrary.mutate({ id: v.library_version_id, decision: "Rejected" })}>
                      Reject
                    </Button>
                  </span>
                ) : (
                  "Waiting for another reviewer"
                ),
            },
          ]}
        />
      )}
    </div>
  );
}

/** Record a branch or batch variation of an Approved / Active version. */
export function RecordVariation({ version }: { version: CurriculumVersion }) {
  const { profile } = useAuth();
  const create = useCurriculumMutation((body: Record<string, unknown>) => deliveryApi.createVariation(body), "Branch variation recorded", {
    next: "A reviewer decides it; it shows under Waiting for a decision.",
  });
  const branches = profile?.allowed_branches ?? [];
  const topics = topicChoices(version.modules ?? []);
  return (
    <ActionDialog
      trigger={
        <Button size="sm" variant="outline">
          Record branch variation
        </Button>
      }
      title="Branch variation"
      description="Record local examples, equivalent exercises, teaching language and a different order here. A required topic that cannot be taught needs a plan to make up for it and central approval."
      fields={[
        { name: "branch_id", label: "Branch", type: "select", options: branches.map((b) => ({ value: b.branch_id, label: b.branch_name })) },
        {
          name: "kind",
          label: "Kind",
          type: "select",
          options: ["Local example", "Equivalent exercise", "Teaching language", "Sequencing", "Required topic constraint"].map((k) => ({
            value: k,
            label: k,
          })),
        },
        {
          name: "topic_id",
          label: "Topic (if it is about one)",
          type: "select",
          options: [{ value: "", label: "—" }, ...topics.map((t) => ({ value: t.topic_id, label: t.label }))],
        },
        { name: "description", label: "What changes", type: "textarea", required: true },
        { name: "remedial_plan", label: "Plan to make up for it (for a required topic that cannot be taught)", type: "textarea" },
      ]}
      onSubmit={(v) =>
        create.mutateAsync({
          curriculum_version_id: version.curriculum_version_id,
          branch_id: Number(v["branch_id"]),
          kind: v["kind"],
          topic_id: v["topic_id"] ? Number(v["topic_id"]) : null,
          description: v["description"],
          remedial_plan: v["remedial_plan"] || null,
        })
      }
    />
  );
}

/** The rules behind the curriculum screens, folded away so the page stays about what to do. */
export function CurriculumHowItWorks() {
  return (
    <HowThisWorks>
      <p>
        Branch Managers write and submit a curriculum version. The Founder / CEO or a Super Admin approves and activates it, and never the person who submitted
        it.
      </p>
      <p>
        Activating a version retires the one it replaces. Batches and students already on the old version keep it. New batches, and batches that had no
        curriculum, use the new one.
      </p>
      <p>
        Only Required topics count towards progress; Recommended and Optional topics are shown separately. Hours stay unconfirmed until someone verifies them,
        and no student can complete a course that has no completion rules.
      </p>
      <p>
        Course names and codes come from the course list and cannot be changed here. A version that has been approved cannot be edited; start a new draft
        instead.
      </p>
    </HowThisWorks>
  );
}

/** Prepare moving one student to another version of the course; the Branch Manager of the receiving branch decides. */
export function PrepareMapping({ enrolmentId, courseId }: { enrolmentId: number; courseId: number }) {
  const versions = useQuery({
    queryKey: ["delivery", "versions", "mappable", courseId],
    queryFn: async () =>
      (await deliveryApi.versions({ course_id: courseId, whole_course: true })).filter((v) => v.status === "Approved" || v.status === "Active"),
  });
  const request = useCurriculumMutation(
    (body: Record<string, unknown>) => deliveryApi.requestMapping(enrolmentId, body),
    "Sent for the Branch Manager's decision",
  );
  return (
    <ActionDialog
      trigger={
        <Button size="sm" variant="ghost">
          Move to another version
        </Button>
      }
      title="Move to another version"
      description="Compare outcomes, work already done and what is left, and explain how the student will move. Credit for earlier work needs an approved rule about matching versions."
      fields={[
        {
          name: "to_version_id",
          label: "Move to version",
          type: "select",
          options: (versions.data ?? []).map((v) => ({ value: v.curriculum_version_id, label: `${v.version_label} (${v.status})` })),
        },
        { name: "comparison", label: "Side-by-side comparison", type: "textarea", required: true },
        { name: "migration_plan", label: "How the student will move", type: "textarea", required: true },
        { name: "trainer_evidence", label: "Trainer evidence", type: "textarea" },
      ]}
      onSubmit={(v) =>
        request.mutateAsync({
          to_version_id: Number(v["to_version_id"]),
          comparison: v["comparison"],
          migration_plan: v["migration_plan"],
          trainer_evidence: v["trainer_evidence"] || null,
        })
      }
    />
  );
}
