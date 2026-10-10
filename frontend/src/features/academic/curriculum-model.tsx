/** The curriculum screens: topic details and dependencies, hours and the completion profile, required
 * assessments, combo pins, the reusable library, academic mappings, equivalence rules and branch variations. */
import { useQuery } from "@tanstack/react-query";
import {
  deliveryApi,
  type CurriculumVersion,
  type ModuleContent,
  type TopicRow,
} from "@/api/delivery";
import { useAuth } from "@/auth/auth";
import { DataTable, Note, QueryView, Section, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { ActionDialog } from "@/features/shared/delivery-ui";
import { useDelivery } from "@/features/shared/sessions";

const hours = (minutes: number) => `${(minutes / 60).toFixed(1)} h`;
const DECISIONS = [
  { value: "Approved", label: "Approve" },
  { value: "Rejected", label: "Reject" },
];

/** Outcome, class, effort, weight, evidence and dependencies of one topic. */
export function TopicDetails({ topic, siblings, editable }: { topic: TopicRow; siblings: TopicRow[]; editable: boolean }) {
  const update = useDelivery((body: Record<string, unknown>) => deliveryApi.updateTopic(topic.topic_id, body), "Topic updated");
  const others = siblings.filter((t) => t.topic_id !== topic.topic_id);
  if (!editable) return null;
  return (
    <ActionDialog
      trigger={
        <Button size="sm" variant="ghost">
          Details
        </Button>
      }
      title={`Topic: ${topic.title}`}
      description="Required topics need an outcome, an estimate, a progress weight and evidence before the version can be submitted."
      fields={[
        {
          name: "topic_class",
          label: "Class",
          type: "select",
          value: topic.topic_class,
          options: ["Required", "Recommended", "Optional"].map((c) => ({ value: c, label: c })),
        },
        { name: "outcome", label: "Learning outcome", type: "textarea", value: topic.outcome ?? "" },
        { name: "instructional_minutes", label: "Instructional minutes (taught, supervised)", type: "number", min: 0, value: String(topic.instructional_minutes ?? "") },
        { name: "independent_minutes", label: "Independent minutes (self-study)", type: "number", min: 0, value: String(topic.independent_minutes ?? "") },
        { name: "weight", label: "Progress weight", type: "number", min: 0, value: topic.weight ?? "" },
        { name: "evidence", label: "Evidence of completion", type: "textarea", value: topic.evidence ?? "" },
        { name: "activities", label: "Activities", type: "textarea", value: topic.activities ?? "" },
        ...others.map((t) => ({
          name: `dep-${t.topic_id}`,
          label: `Builds on: ${t.title}`,
          type: "checkbox" as const,
          value: topic.depends_on.includes(t.topic_id) ? "true" : "",
        })),
      ]}
      onSubmit={(v) => {
        const number = (key: string) => (v[key] ? Number(v[key]) : null);
        return update.mutateAsync({
          topic_class: v["topic_class"],
          outcome: v["outcome"] || null,
          instructional_minutes: number("instructional_minutes"),
          independent_minutes: number("independent_minutes"),
          weight: number("weight"),
          evidence: v["evidence"] || null,
          activities: v["activities"] || null,
          depends_on: others.filter((t) => v[`dep-${t.topic_id}`] === "true").map((t) => t.topic_id),
        });
      }}
    />
  );
}

export function topicSummary(t: TopicRow) {
  const parts = [t.outcome, t.instructional_minutes !== null ? `${t.instructional_minutes} min taught` : null, t.weight ? `weight ${t.weight}` : null];
  return parts.filter(Boolean).join(" · ");
}

/** Hours, completion profile, required assessments, pins and library inserts for one version. */
export function VersionPlanning({ version, editable, author }: { version: CurriculumVersion; editable: boolean; author: boolean }) {
  const id = version.curriculum_version_id;
  const verify = useDelivery(() => deliveryApi.verifyHours(id), "Hours verified");
  const profile = useDelivery(
    (v: Record<string, string>) =>
      deliveryApi.setCompletionProfile(id, {
        attendance_minimum_pct: Number(v["attendance_minimum_pct"]),
        pass_mark_pct: Number(v["pass_mark_pct"]),
        recovery_rule: v["recovery_rule"]!,
        reassessment_rule: v["reassessment_rule"]!,
      }),
    "Completion profile saved",
  );
  const addRequirement = useDelivery((body: Record<string, unknown>) => deliveryApi.addRequirement(id, body), "Required assessment added");
  const deleteRequirement = useDelivery((requirementId: number) => deliveryApi.deleteRequirement(requirementId), "Required assessment removed");
  const library = useQuery({ queryKey: ["delivery", "library"], queryFn: deliveryApi.library, enabled: editable });
  const insert = useDelivery((libraryVersionId: number) => deliveryApi.insertLibraryModule(id, libraryVersionId), "Library module added");
  const totals = version.totals;
  const p = version.completion_profile;
  const approvedLibrary = (library.data?.data ?? []).filter((m) => m.current_version);

  return (
    <div className="grid gap-3 rounded-lg border p-3 text-sm sm:grid-cols-2">
      <div className="space-y-1">
        <h4 className="font-semibold">Hours</h4>
        {totals && (
          <>
            <p>
              Instructional {hours(totals.instructional_minutes)} · independent {hours(totals.independent_minutes)} · total{" "}
              {hours(totals.total_minutes)}
            </p>
            {totals.booster && (
              <p className="text-muted-foreground">
                Included booster {totals.booster.track_code}: {hours(totals.booster.total_minutes)}
              </p>
            )}
            <Tag tone={totals.hours_verified ? "success" : "warning"}>{totals.hours_verified ? "Hours verified" : "Hours not verified"}</Tag>
            {totals.unestimated_topics > 0 && <p className="text-muted-foreground">{totals.unestimated_topics} topic(s) without an estimate</p>}
          </>
        )}
        {editable && author && (
          <Button size="sm" variant="outline" onClick={() => verify.mutate(undefined)}>
            Verify hours
          </Button>
        )}
      </div>
      <div className="space-y-1">
        <h4 className="font-semibold">Completion profile</h4>
        {p ? (
          <p>
            Attendance ≥ {p.attendance_minimum_pct}% · pass mark {p.pass_mark_pct}% · recovery: {p.recovery_rule} · reassessment: {p.reassessment_rule}
          </p>
        ) : (
          <Tag tone="warning">Not set — nothing completes without it</Tag>
        )}
        {editable && author && (
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Set completion profile
              </Button>
            }
            title="Completion profile"
            fields={[
              { name: "attendance_minimum_pct", label: "Attendance minimum (%)", type: "number", required: true, min: 0, value: String(p?.attendance_minimum_pct ?? "") },
              { name: "pass_mark_pct", label: "Pass mark (%)", type: "number", required: true, min: 0, value: String(p?.pass_mark_pct ?? "") },
              { name: "recovery_rule", label: "Recovery rule", type: "textarea", required: true, value: p?.recovery_rule ?? "" },
              { name: "reassessment_rule", label: "Reassessment rule", type: "textarea", required: true, value: p?.reassessment_rule ?? "" },
            ]}
            onSubmit={(v) => profile.mutateAsync(v)}
          />
        )}
      </div>
      <div className="space-y-1 sm:col-span-2">
        <h4 className="font-semibold">Required assessments</h4>
        {(version.assessment_requirements ?? []).length === 0 ? (
          <p className="text-muted-foreground">None. Assignments and tests marked required must link to one of these.</p>
        ) : (
          <ul className="space-y-1">
            {version.assessment_requirements!.map((r) => (
              <li key={r.requirement_id} className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  <Tag>{r.kind}</Tag> {r.title} — {r.outcome} · weight {r.weight} · pass: {r.pass_rule}
                </span>
                {editable && author && (
                  <Button size="sm" variant="ghost" onClick={() => deleteRequirement.mutate(r.requirement_id)}>
                    Remove
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
        {editable && author && (
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
              { name: "outcome", label: "Outcome it evidences", type: "textarea", required: true },
              { name: "weight", label: "Weight", type: "number", min: 0, required: true },
              { name: "pass_rule", label: "Pass rule", required: true },
            ]}
            onSubmit={(v) => addRequirement.mutateAsync({ ...v, weight: Number(v["weight"]) })}
          />
        )}
      </div>
      {editable && author && approvedLibrary.length > 0 && (
        <div className="sm:col-span-2">
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Add a module from the library
              </Button>
            }
            title="Reuse a library module"
            description="The module is copied at its approved version; later library changes do not alter this curriculum."
            fields={[
              {
                name: "library_version_id",
                label: "Library module",
                type: "select",
                options: approvedLibrary.map((m) => ({
                  value: m.current_version!.library_version_id,
                  label: `${m.module_code} ${m.title} (v${m.current_version!.version_no})`,
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

/** A combo parent pins the exact version of each track and the booster. */
export function ComboPins({ version, editable }: { version: CurriculumVersion; editable: boolean }) {
  const course = useQuery({
    queryKey: ["delivery", "overview"],
    queryFn: deliveryApi.curriculumOverview,
    enabled: version.component === null,
  });
  const versions = useQuery({
    queryKey: ["delivery", "versions", "pinnable", version.course.course_id],
    queryFn: async () => {
      const own = await deliveryApi.versions({ course_id: version.course.course_id });
      return own.filter((v) => v.status === "Approved" || v.status === "Active");
    },
  });
  const pin = useDelivery((v: { component_id: number; component_version_id: number }) => deliveryApi.pinComponent(version.curriculum_version_id, v), "Track pinned");
  const components = (course.data ?? []).filter((r) => r.course.course_id === version.course.course_id && r.component).map((r) => r.component!);
  if (components.length === 0) return null;
  const pinned = new Map((version.components ?? []).map((c) => [c.component_id, c.component_version]));
  return (
    <div className="rounded-lg border p-3 text-sm">
      <h4 className="font-semibold">Tracks and booster in this programme version</h4>
      <ul className="mt-1 space-y-1">
        {components.map((c) => (
          <li key={c.component_id} className="flex flex-wrap items-center justify-between gap-2">
            <span>
              {c.track_code} — {c.track_name}: {pinned.get(c.component_id)?.version_label ?? <Tag tone="warning">Not pinned</Tag>}
            </span>
            {editable && (
              <ActionDialog
                trigger={
                  <Button size="sm" variant="outline">
                    Pin version
                  </Button>
                }
                title={`Pin ${c.track_code}`}
                description="A version written for this track; a booster can reuse its own course's version once its equivalence is reviewed."
                fields={[
                  {
                    name: "component_version_id",
                    label: "Version (id)",
                    type: "select",
                    options: (versions.data ?? [])
                      .filter((v) => v.component?.component_id === c.component_id)
                      .map((v) => ({ value: v.curriculum_version_id, label: `${v.version_label} (${v.status})` })),
                  },
                  { name: "other", label: "Or a version id of the booster's own course", type: "number", min: 1 },
                ]}
                onSubmit={(v) => pin.mutateAsync({ component_id: c.component_id, component_version_id: Number(v["other"] || v["component_version_id"]) })}
              />
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Record that a combo component matches its standalone course in outcomes, scope, depth and assessment. */
export function EquivalenceReview({ componentId, trackCode, note }: { componentId: number; trackCode: string; note?: string | null }) {
  const review = useDelivery((text: string) => deliveryApi.reviewEquivalence(componentId, text), "Equivalence review recorded");
  return (
    <ActionDialog
      trigger={
        <Button size="sm" variant="outline">
          {note ? "Update equivalence review" : "Review equivalence"}
        </Button>
      }
      title={`Equivalence review: ${trackCode}`}
      description="Similar names are not enough. Record how outcomes, scope, depth and assessment match before the booster reuses the course curriculum."
      fields={[{ name: "note", label: "Review", type: "textarea", required: true, value: note ?? "" }]}
      onSubmit={(v) => review.mutateAsync(v["note"]!)}
    />
  );
}

export function SaveToLibrary({ module }: { module: ModuleContent }) {
  const save = useDelivery(() => deliveryApi.saveToLibrary(module.module_id), "Proposed to the library; another reviewer approves it");
  return (
    <Button size="sm" variant="ghost" onClick={() => save.mutate(undefined)}>
      Save to library
    </Button>
  );
}

/** Academic mappings, equivalence rules, variations and library versions waiting for the signed-in reviewer. */
export function CurriculumDecisions() {
  const { hasRole, profile } = useAuth();
  const me = profile?.user.user_id;
  const central = hasRole("FOUNDER_CEO", "SUPER_ADMIN");
  const reviewer = hasRole("BRANCH_MANAGER", "SUPER_ADMIN");
  const mappings = useQuery({ queryKey: ["delivery", "mappings"], queryFn: () => deliveryApi.mappings({ status: "Pending" }) });
  const rules = useQuery({ queryKey: ["delivery", "rules"], queryFn: () => deliveryApi.rules({ status: "Pending" }) });
  const variations = useQuery({ queryKey: ["delivery", "variations"], queryFn: () => deliveryApi.variations({ status: "Pending" }) });
  const library = useQuery({ queryKey: ["delivery", "library"], queryFn: deliveryApi.library });
  const decideMapping = useDelivery(
    (v: { id: number; body: { decision: string; note?: string; student_acceptance?: string } }) => deliveryApi.decideMapping(v.id, v.body),
    "Mapping decided",
  );
  const decideRule = useDelivery((v: { id: number; body: { decision: string; note?: string } }) => deliveryApi.decideRule(v.id, v.body), "Rule decided");
  const decideVariation = useDelivery(
    (v: { id: number; body: { decision: string; note?: string } }) => deliveryApi.decideVariation(v.id, v.body),
    "Variation decided",
  );
  const decideLibrary = useDelivery((v: { id: number; decision: string }) => deliveryApi.decideLibraryVersion(v.id, v.decision), "Library version decided");
  const pendingLibrary = (library.data?.data ?? []).flatMap((m) => m.versions.filter((v) => v.status === "Pending").map((v) => ({ m, v })));
  const decisionFields = [
    { name: "decision", label: "Decision", type: "select" as const, options: DECISIONS },
    { name: "note", label: "Note (required to reject)", type: "textarea" as const },
  ];

  return (
    <div className="space-y-4">
      <QueryView query={mappings} isEmpty={(p) => p.data.length === 0} empty="No academic mapping is waiting.">
        {(page) => (
          <DataTable
            caption="Academic mappings waiting for a decision"
            rows={page.data}
            getKey={(m) => m.mapping_id}
            cols={[
              { h: "Move", c: (m) => `${m.from_version?.version_label ?? "—"} → ${m.to_version.version_label}` },
              { h: "Comparison and plan", c: (m) => `${m.comparison} · Plan: ${m.migration_plan}` },
              { h: "Credits", c: (m) => String(m.proposed_credits.length) },
              { h: "Prepared by", c: (m) => m.requested_by.full_name },
              {
                h: "",
                c: (m) =>
                  reviewer && m.requested_by.user_id !== me ? (
                    <ActionDialog
                      trigger={<Button size="sm">Decide</Button>}
                      title="Academic mapping"
                      fields={[...decisionFields, { name: "student_acceptance", label: "How the student accepted (required to approve)", type: "textarea" }]}
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
      <QueryView query={rules} isEmpty={(p) => p.data.length === 0} empty="No equivalence rule is waiting.">
        {(page) => (
          <DataTable
            caption="Equivalence rules waiting for the Founder / CEO or Super Admin"
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
                      title="Equivalence rule"
                      fields={decisionFields}
                      onSubmit={(v) => decideRule.mutateAsync({ id: r.rule_id, body: { decision: v["decision"]!, note: v["note"] || undefined } })}
                    />
                  ) : null,
              },
            ]}
          />
        )}
      </QueryView>
      <QueryView query={variations} isEmpty={(p) => p.data.length === 0} empty="No branch variation is waiting.">
        {(page) => (
          <DataTable
            caption="Branch variations waiting for a decision"
            rows={page.data}
            getKey={(x) => x.variation_id}
            cols={[
              { h: "Kind", c: (x) => <Tag>{x.kind}</Tag> },
              { h: "Variation", c: (x) => [x.description, x.remedial_plan && `Remedial plan: ${x.remedial_plan}`].filter(Boolean).join(" · ") },
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
          caption="Library versions waiting for review"
          rows={pendingLibrary}
          getKey={({ v }) => v.library_version_id}
          cols={[
            { h: "Module", c: ({ m, v }) => `${m.module_code} ${m.title} v${v.version_no}` },
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
                  "Another reviewer decides"
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
  const create = useDelivery((body: Record<string, unknown>) => deliveryApi.createVariation(body), "Variation recorded");
  const branches = profile?.allowed_branches ?? [];
  const topics = (version.modules ?? []).flatMap((m) => m.topics);
  return (
    <ActionDialog
      trigger={
        <Button size="sm" variant="outline">
          Record branch variation
        </Button>
      }
      title="Branch variation"
      description="Local examples, equivalent exercises, teaching language and sequencing are recorded here. A required topic that cannot be delivered needs a remedial plan and central approval."
      fields={[
        { name: "branch_id", label: "Branch", type: "select", options: branches.map((b) => ({ value: b.branch_id, label: b.branch_name })) },
        {
          name: "kind",
          label: "Kind",
          type: "select",
          options: ["Local example", "Equivalent exercise", "Teaching language", "Sequencing", "Required topic constraint"].map((k) => ({ value: k, label: k })),
        },
        { name: "topic_id", label: "Topic (if it is about one)", type: "select", options: [{ value: "", label: "—" }, ...topics.map((t) => ({ value: t.topic_id, label: t.title }))] },
        { name: "description", label: "Variation", type: "textarea", required: true },
        { name: "remedial_plan", label: "Remedial plan (for a required topic constraint)", type: "textarea" },
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

export function CurriculumModelNote() {
  return (
    <Note>
      Required topics count towards progress; Recommended and Optional learning stays visible separately. Hours stay Pending until verified, and nothing completes
      without a completion profile.
    </Note>
  );
}


/** Prepare an individual academic mapping to another version of the course; the Branch Manager of the receiving branch decides. */
export function PrepareMapping({ enrolmentId, courseId }: { enrolmentId: number; courseId: number }) {
  const versions = useQuery({
    queryKey: ["delivery", "versions", "mappable", courseId],
    queryFn: async () => (await deliveryApi.versions({ course_id: courseId, whole_course: true })).filter((v) => v.status === "Approved" || v.status === "Active"),
  });
  const request = useDelivery((body: Record<string, unknown>) => deliveryApi.requestMapping(enrolmentId, body), "Mapping sent for the Branch Manager's decision");
  return (
    <ActionDialog
      trigger={
        <Button size="sm" variant="ghost">
          Academic mapping
        </Button>
      }
      title="Prepare an academic mapping"
      description="Compare outcomes, previous work and remaining obligations, and give the migration plan. Credit for earlier work needs an approved equivalence rule."
      fields={[
        {
          name: "to_version_id",
          label: "Move to version",
          type: "select",
          options: (versions.data ?? []).map((v) => ({ value: v.curriculum_version_id, label: `${v.version_label} (${v.status})` })),
        },
        { name: "comparison", label: "Side-by-side comparison", type: "textarea", required: true },
        { name: "migration_plan", label: "Migration plan", type: "textarea", required: true },
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
