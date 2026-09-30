import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp } from "lucide-react";
import { deliveryApi, type CurriculumRow, type CurriculumVersion, type ModuleContent } from "@/api/delivery";
import { Button } from "@/components/ui/button";
import { DataTable, Note, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { ActionDialog, fmtDate, mono } from "@/features/shared/delivery-ui";
import { useDelivery } from "@/features/shared/sessions";

type Slot = { course_id: number; component_id: number | null; label: string };

const slotOf = (row: CurriculumRow): Slot => ({
  course_id: row.course.course_id,
  component_id: row.component?.component_id ?? null,
  label: row.component ? `${row.component.track_code} — ${row.component.track_name}` : `${row.course.course_code} — ${row.course.title}`,
});

function ModuleEditor({ module, editable }: { module: ModuleContent; editable: boolean }) {
  const updateModule = useDelivery(
    (v: { id: number; body: { title?: string; position?: number } }) => deliveryApi.updateModule(v.id, v.body),
    "Module updated",
  );
  const deleteModule = useDelivery((id: number) => deliveryApi.deleteModule(id), "Module removed");
  const addTopic = useDelivery(
    (v: { id: number; title: string; is_required: boolean }) => deliveryApi.addTopic(v.id, { title: v.title, is_required: v.is_required }),
    "Topic added",
  );
  const updateTopic = useDelivery(
    (v: { id: number; body: { title?: string; is_required?: boolean; position?: number } }) => deliveryApi.updateTopic(v.id, v.body),
    "Topic updated",
  );
  const deleteTopic = useDelivery((id: number) => deliveryApi.deleteTopic(id), "Topic removed");
  return (
    <li className="rounded-lg border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">
          {module.sort_order}. {module.title}
        </h3>
        {editable && (
          <div className="flex flex-wrap gap-1.5">
            <ActionDialog
              trigger={
                <Button size="sm" variant="outline">
                  Rename
                </Button>
              }
              title="Rename module"
              fields={[{ name: "title", label: "Title", required: true, value: module.title }]}
              onSubmit={(v) => updateModule.mutateAsync({ id: module.module_id, body: { title: v["title"]! } })}
            />
            <Button
              size="sm"
              variant="ghost"
              aria-label="Move module up"
              onClick={() => updateModule.mutate({ id: module.module_id, body: { position: module.sort_order - 1 } })}
              disabled={module.sort_order === 1}
            >
              <ArrowUp className="size-4" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              aria-label="Move module down"
              onClick={() => updateModule.mutate({ id: module.module_id, body: { position: module.sort_order + 1 } })}
            >
              <ArrowDown className="size-4" />
            </Button>
            <Button size="sm" variant="outline" onClick={() => deleteModule.mutate(module.module_id)}>
              Remove
            </Button>
          </div>
        )}
      </div>
      <ul className="mt-2 divide-y text-sm">
        {module.topics.map((t) => (
          <li key={t.topic_id} className="flex flex-wrap items-center justify-between gap-2 py-1.5">
            <span>
              {t.sort_order}. {t.title}
            </span>
            <span className="flex flex-wrap items-center gap-1.5">
              <StatusBadge tone={t.is_required ? "info" : "neutral"}>{t.is_required ? "Required" : "Optional"}</StatusBadge>
              {editable && (
                <>
                  <Button size="sm" variant="ghost" onClick={() => updateTopic.mutate({ id: t.topic_id, body: { is_required: !t.is_required } })}>
                    {t.is_required ? "Make optional" : "Make required"}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label="Move topic up"
                    disabled={t.sort_order === 1}
                    onClick={() => updateTopic.mutate({ id: t.topic_id, body: { position: t.sort_order - 1 } })}
                  >
                    <ArrowUp className="size-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label="Move topic down"
                    onClick={() => updateTopic.mutate({ id: t.topic_id, body: { position: t.sort_order + 1 } })}
                  >
                    <ArrowDown className="size-4" />
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => deleteTopic.mutate(t.topic_id)}>
                    Remove
                  </Button>
                </>
              )}
            </span>
          </li>
        ))}
        {module.topics.length === 0 && <li className="py-1.5 text-muted-foreground">No topics yet.</li>}
      </ul>
      {editable && (
        <div className="mt-2">
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Add topic
              </Button>
            }
            title={`Add a topic to ${module.title}`}
            fields={[
              { name: "title", label: "Topic title", required: true },
              { name: "required", label: "Required", type: "checkbox", hint: "Counts towards required learning", value: "true" },
            ]}
            onSubmit={(v) => addTopic.mutateAsync({ id: module.module_id, title: v["title"]!, is_required: v["required"] === "true" })}
          />
        </div>
      )}
    </li>
  );
}

function VersionEditor({ versionId }: { versionId: number }) {
  const query = useQuery({ queryKey: ["delivery", "version", versionId], queryFn: () => deliveryApi.curriculumVersion(versionId) });
  const act = useDelivery(
    (v: { action: "submit" | "return" | "approve" | "activate" | "retire"; reason?: string }) =>
      deliveryApi.versionAction(versionId, v.action, { reason: v.reason }),
    "Curriculum updated",
  );
  const addModule = useDelivery((title: string) => deliveryApi.addModule(versionId, { title }), "Module added");
  const rename = useDelivery((label: string) => deliveryApi.renameVersion(versionId, label), "Version renamed");
  return (
    <QueryView query={query}>
      {(v) => {
        const draft = v.status === "Draft";
        return (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-lg font-semibold">
                  {v.version_label} <StatusBadge>{v.status}</StatusBadge>
                </h3>
                <p className="text-sm text-muted-foreground">
                  {v.counts.modules} module(s), {v.counts.topics} topic(s), {v.counts.required_topics} required · used by {v.usage.batches} batch(es) and{" "}
                  {v.usage.enrolments + v.usage.tracks} enrolment(s)
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {draft && (
                  <>
                    <ActionDialog
                      trigger={
                        <Button size="sm" variant="outline">
                          Rename
                        </Button>
                      }
                      title="Rename version"
                      fields={[{ name: "label", label: "Version label", required: true, value: v.version_label }]}
                      onSubmit={(f) => rename.mutateAsync(f["label"]!)}
                    />
                    <Button size="sm" onClick={() => act.mutate({ action: "submit" })}>
                      Submit for review
                    </Button>
                  </>
                )}
                {v.status === "Under Review" && (
                  <>
                    <Button size="sm" onClick={() => act.mutate({ action: "approve" })}>
                      Approve
                    </Button>
                    <ActionDialog
                      trigger={
                        <Button size="sm" variant="outline">
                          Return to draft
                        </Button>
                      }
                      title="Return to draft"
                      fields={[{ name: "reason", label: "What needs to change", type: "textarea", required: true }]}
                      submitLabel="Return"
                      onSubmit={(f) => act.mutateAsync({ action: "return", reason: f["reason"] })}
                    />
                  </>
                )}
                {v.status === "Approved" && (
                  <Button size="sm" onClick={() => act.mutate({ action: "activate" })}>
                    Activate
                  </Button>
                )}
                {(v.status === "Approved" || v.status === "Active") && (
                  <ActionDialog
                    trigger={
                      <Button size="sm" variant="outline">
                        Retire
                      </Button>
                    }
                    title={`Retire ${v.version_label}`}
                    description="New enrolments will wait in Curriculum Mapping Pending until another version is Active."
                    fields={[{ name: "reason", label: "Reason", type: "textarea" }]}
                    submitLabel="Retire"
                    onSubmit={(f) => act.mutateAsync({ action: "retire", reason: f["reason"] || undefined })}
                  />
                )}
              </div>
            </div>
            {draft && v.blockers && v.blockers.length > 0 && <StatusNote state="Pending Verification">Before review: {v.blockers.join("; ")}.</StatusNote>}
            {!draft && (
              <Note>
                {v.status} versions are snapshots that batches and enrolments point at. To change the curriculum, start a new draft (copy this version).
              </Note>
            )}
            <ul className="space-y-3">
              {(v.modules ?? []).map((m) => (
                <ModuleEditor key={m.module_id} module={m} editable={draft} />
              ))}
            </ul>
            {draft && (
              <ActionDialog
                trigger={<Button variant="outline">Add module</Button>}
                title="Add a module"
                fields={[{ name: "title", label: "Module title", required: true }]}
                onSubmit={(f) => addModule.mutateAsync(f["title"]!)}
              />
            )}
            <details className="text-sm">
              <summary className="cursor-pointer font-medium">Review trail ({v.events?.length ?? 0})</summary>
              <ul className="mt-2 space-y-1">
                {(v.events ?? []).map((e) => (
                  <li key={e.event_id}>
                    {fmtDate(e.created_at)} · <strong>{e.action}</strong> ({e.from_status ?? "—"} → {e.to_status}) by {e.actor?.full_name ?? "system"}
                    {e.note ? ` — ${e.note}` : ""}
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

function SlotPanel({ slot }: { slot: Slot }) {
  const [selected, setSelected] = useState<number | null>(null);
  const versions = useQuery({
    queryKey: ["delivery", "versions", slot.course_id, slot.component_id],
    queryFn: () =>
      deliveryApi.versions(
        slot.component_id === null ? { course_id: slot.course_id, whole_course: true } : { course_id: slot.course_id, component_id: slot.component_id },
      ),
  });
  const create = useDelivery(
    (body: { version_label: string; copy_from_version_id?: number }) =>
      deliveryApi.createVersion({ course_id: slot.course_id, component_id: slot.component_id, ...body }),
    "Draft created",
  );
  const discard = useDelivery((id: number) => deliveryApi.deleteVersion(id), "Draft discarded");
  return (
    <Section
      title={`Versions — ${slot.label}`}
      actions={
        <QueryView query={versions}>
          {(list: CurriculumVersion[]) => (
            <ActionDialog
              trigger={<Button size="sm">New draft version</Button>}
              title="New draft version"
              description="Start empty or copy an existing version's modules and topics."
              fields={[
                { name: "version_label", label: "Version label", required: true, placeholder: "CV 6.0" },
                {
                  name: "copy",
                  label: "Copy from",
                  type: "select",
                  options: [
                    { value: "", label: "Start empty" },
                    ...list.map((v) => ({ value: v.curriculum_version_id, label: `${v.version_label} (${v.status})` })),
                  ],
                  value: "",
                },
              ]}
              onSubmit={async (f) => {
                const made = await create.mutateAsync({ version_label: f["version_label"]!, copy_from_version_id: f["copy"] ? Number(f["copy"]) : undefined });
                setSelected(made.curriculum_version_id);
              }}
            />
          )}
        </QueryView>
      }
    >
      <QueryView query={versions} isEmpty={(list) => list.length === 0} empty="No curriculum version exists yet. Start a draft.">
        {(list) => (
          <>
            <ul className="mb-4 flex flex-wrap gap-2">
              {list.map((v) => (
                <li key={v.curriculum_version_id}>
                  <Button size="sm" variant={selected === v.curriculum_version_id ? "default" : "outline"} onClick={() => setSelected(v.curriculum_version_id)}>
                    {v.version_label} · {v.status}
                  </Button>
                </li>
              ))}
            </ul>
            {selected ? (
              <>
                <VersionEditor versionId={selected} />
                {list.find((v) => v.curriculum_version_id === selected)?.status === "Draft" && (
                  <div className="mt-3">
                    <Button size="sm" variant="outline" onClick={() => discard.mutate(selected, { onSuccess: () => setSelected(null) })}>
                      Discard this draft
                    </Button>
                  </div>
                )}
              </>
            ) : (
              <StatusNote state="Empty">Choose a version to view or edit it.</StatusNote>
            )}
          </>
        )}
      </QueryView>
    </Section>
  );
}

export function AcademicCurriculum() {
  const [slot, setSlot] = useState<Slot | null>(null);
  const query = useQuery({ queryKey: ["delivery", "curriculum-overview"], queryFn: deliveryApi.curriculumOverview });
  return (
    <>
      <PageHead title="Course Curriculum & Versions" description="Curriculum versions per course and combo track, their review path and delivery readiness." />
      <QueryView query={query}>
        {(rows) => (
          <DataTable
            caption="Curriculum versions"
            rows={rows}
            getKey={(r) => `${r.course.course_id}-${r.component?.component_id ?? 0}`}
            cols={[
              {
                h: "Course",
                c: (r) => (
                  <>
                    {mono(r.component ? r.component.track_code : r.course.course_code)}
                    <div>{r.component ? `↳ ${r.component.track_name} (${r.component.role})` : r.course.title}</div>
                  </>
                ),
              },
              {
                h: "Active version",
                c: (r) =>
                  r.active_version ? (
                    <>
                      {r.active_version.version_label}
                      {r.borrowed_from && <div className="text-xs text-muted-foreground">from {r.borrowed_from.course_code}</div>}
                    </>
                  ) : (
                    "—"
                  ),
              },
              {
                h: "In progress",
                c: (r) => (r.latest_version && r.latest_version.status !== "Active" ? `${r.latest_version.version_label} — ${r.latest_version.status}` : "—"),
              },
              {
                h: "Delivery readiness",
                c: (r) => (
                  <>
                    <StatusBadge>{r.readiness}</StatusBadge>
                    {r.pending_enrolments > 0 && <div className="mt-1 text-xs text-muted-foreground">{r.pending_enrolments} enrolment(s) waiting</div>}
                  </>
                ),
              },
              {
                h: "",
                c: (r) => (
                  <Button size="sm" variant="outline" onClick={() => setSlot(slotOf(r))}>
                    Manage versions
                  </Button>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      {slot && (
        <div className="mt-6">
          <SlotPanel key={`${slot.course_id}-${slot.component_id}`} slot={slot} />
        </div>
      )}
      <div className="mt-4">
        <Note>
          Course Master names and codes are read-only here. A version is reviewed by someone other than its submitter; activating it retires the previous Active
          version and maps every enrolment and batch that was waiting for a curriculum.
        </Note>
      </div>
    </>
  );
}
