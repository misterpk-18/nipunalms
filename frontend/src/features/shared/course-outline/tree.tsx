/** The modules and topics of one course outline (the course's own, or one combo track's): reorder by dragging or with Move up / Move down,
 * rename, add and remove after a confirm. Without `editable` it is a plain read-only list. */
import { useState, type DragEvent, type ReactNode } from "react";
import { ArrowDown, ArrowUp, GripVertical } from "lucide-react";
import { coursesApi } from "@/api/courses";
import type { ModuleContent, TopicClass, TopicRow } from "@/api/delivery";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { EmptyState } from "@/components/lms/empty-state";
import { Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { ActionDialog } from "@/features/shared/delivery-ui";
import { cn } from "@/lib/utils";
import { plural, topicChoices, useCourseMutation } from "./mutation";
import { SaveToLibrary } from "./library";
import { TopicDetails, topicSummary } from "./topic-details";

type Drag = { kind: "module" | "topic"; id: number; parent: number } | null;

function Grip({ label, onStart, onEnd }: { label: string; onStart: (e: DragEvent<HTMLSpanElement>) => void; onEnd: () => void }) {
  return (
    <span
      draggable
      title={label}
      aria-hidden="true"
      data-drag-handle=""
      onDragStart={onStart}
      onDragEnd={onEnd}
      className="hidden shrink-0 cursor-grab touch-none rounded p-1 text-muted-foreground hover:bg-accent active:cursor-grabbing md:inline-flex"
    >
      <GripVertical className="size-4" />
    </span>
  );
}

function TopicRowView({
  topic,
  index,
  count,
  module,
  versionTopics,
  editable,
  dragging,
  over,
  onMove,
  onDragStart,
  onDragEnd,
  onOver,
  onDrop,
}: {
  topic: TopicRow;
  index: number;
  count: number;
  module: ModuleContent;
  versionTopics: ModuleContent[];
  editable: boolean;
  dragging: boolean;
  over: boolean;
  onMove: (position: number) => void;
  onDragStart: (e: DragEvent<HTMLSpanElement>) => void;
  onDragEnd: () => void;
  onOver: (e: DragEvent<HTMLLIElement>) => void;
  onDrop: (e: DragEvent<HTMLLIElement>) => void;
}) {
  const remove = useCourseMutation(() => coursesApi.deleteTopic(topic.topic_id), `Topic ${topic.title} removed`);
  const choices = topicChoices(versionTopics);
  const names = new Map(choices.map((c) => [c.topic_id, c.label]));
  const builds = topic.depends_on.map((id) => names.get(id)).filter(Boolean);
  return (
    <li
      id={`topic-${topic.topic_id}`}
      onDragOver={onOver}
      onDrop={onDrop}
      className={cn(
        "flex flex-wrap items-start justify-between gap-2 py-2 outline-none",
        dragging && "opacity-50",
        over && "bg-primary/10 ring-1 ring-primary",
      )}
    >
      <div className="flex min-w-0 flex-1 items-start gap-1">
        {editable && <Grip label={`Drag to reorder topic ${topic.title}`} onStart={onDragStart} onEnd={onDragEnd} />}
        <div className="min-w-0">
          <p className="break-words">
            {topic.sort_order}. {topic.title}
          </p>
          {topicSummary(topic) && <p className="break-words text-xs text-muted-foreground">{topicSummary(topic)}</p>}
          {builds.length > 0 && <p className="break-words text-xs text-muted-foreground">Needs first: {builds.join(", ")}</p>}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <Tag tone={topic.topic_class === "Required" ? "info" : "neutral"}>{topic.topic_class}</Tag>
        <TopicDetails topic={topic} modules={versionTopics} editable={editable} />
        {editable && (
          <>
            <Button size="sm" variant="ghost" aria-label={`Move topic ${topic.title} up`} disabled={index === 0} onClick={() => onMove(topic.sort_order - 1)}>
              <ArrowUp className="size-4" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              aria-label={`Move topic ${topic.title} down`}
              disabled={index === count - 1}
              onClick={() => onMove(topic.sort_order + 1)}
            >
              <ArrowDown className="size-4" />
            </Button>
            <ConfirmDialog
              title={`Remove topic ${topic.title}?`}
              consequence={`${topic.title} will be removed from ${module.title} from this course${topic.depends_on.length || versionTopics.some((m) => m.topics.some((t) => t.depends_on.includes(topic.topic_id))) ? ", and topics that need it first will stop needing it" : ""}. This cannot be undone. A topic that classes, content, assignments, questions or tests use cannot be removed.`}
              confirmLabel="Remove topic"
              destructive
              onConfirm={() => remove.mutateAsync(undefined)}
            >
              <Button size="sm" variant="ghost" aria-label={`Remove topic ${topic.title}`}>
                Remove
              </Button>
            </ConfirmDialog>
          </>
        )}
      </div>
    </li>
  );
}

function ModuleCard({
  module,
  index,
  count,
  modules,
  editable,
  drag,
  setDrag,
  over,
  setOver,
}: {
  module: ModuleContent;
  index: number;
  count: number;
  modules: ModuleContent[];
  editable: boolean;
  drag: Drag;
  setDrag: (d: Drag) => void;
  over: string | null;
  setOver: (key: string | null) => void;
}) {
  const updateModule = useCourseMutation(
    (v: { body: { title?: string; position?: number } }) => coursesApi.updateModule(module.module_id, v.body),
    "Module updated",
  );
  const reorderModule = useCourseMutation((v: { id: number; position: number }) => coursesApi.updateModule(v.id, { position: v.position }), "Module moved");
  const remove = useCourseMutation(() => coursesApi.deleteModule(module.module_id), `Module ${module.title} removed`);
  const addTopic = useCourseMutation((v: { title: string; topic_class: TopicClass }) => coursesApi.addTopic(module.module_id, v), "Topic added", {
    next: "Open Details on it to add the outcome, minutes, weight and evidence.",
  });
  const reorderTopic = useCourseMutation((v: { id: number; position: number }) => coursesApi.updateTopic(v.id, { position: v.position }), "Topic moved");

  const moduleKey = `module-${module.module_id}`;
  const draggingModule = drag?.kind === "module" && drag.id === module.module_id;
  const acceptModule = editable && drag?.kind === "module" && drag.id !== module.module_id;
  const acceptTopic = (t: TopicRow) => editable && drag?.kind === "topic" && drag.parent === module.module_id && drag.id !== t.topic_id;

  return (
    <li
      className={cn("rounded-lg border p-3", draggingModule && "opacity-50", over === moduleKey && "bg-primary/5 ring-2 ring-primary")}
      onDragOver={(e) => {
        if (!acceptModule) return;
        e.preventDefault();
        setOver(moduleKey);
      }}
      onDrop={(e) => {
        if (!acceptModule) return;
        e.preventDefault();
        setOver(null);
        setDrag(null);
        reorderModule.mutate({ id: drag!.id, position: module.sort_order });
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1">
          {editable && (
            <Grip
              label={`Drag to reorder module ${module.title}`}
              onStart={(e) => {
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData("text/plain", moduleKey);
                const row = e.currentTarget.closest("li");
                if (row) e.dataTransfer.setDragImage(row, 16, 16);
                setDrag({ kind: "module", id: module.module_id, parent: 0 });
              }}
              onEnd={() => {
                setDrag(null);
                setOver(null);
              }}
            />
          )}
          <h3 className="min-w-0 break-words font-semibold">
            {module.sort_order}. {module.title}
            {module.library_version_id && <span className="ml-2 text-xs font-normal text-muted-foreground">from the library</span>}
          </h3>
        </div>
        {editable && (
          <div className="flex flex-wrap gap-1.5">
            <ActionDialog
              trigger={
                <Button size="sm" variant="outline" aria-label={`Rename module ${module.title}`}>
                  Rename
                </Button>
              }
              title="Rename module"
              fields={[{ name: "title", label: "Title", required: true, value: module.title }]}
              onSubmit={(v) => updateModule.mutateAsync({ body: { title: v["title"]! } })}
            />
            <Button
              size="sm"
              variant="ghost"
              aria-label={`Move module ${module.title} up`}
              disabled={index === 0}
              onClick={() => reorderModule.mutate({ id: module.module_id, position: module.sort_order - 1 })}
            >
              <ArrowUp className="size-4" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              aria-label={`Move module ${module.title} down`}
              disabled={index === count - 1}
              onClick={() => reorderModule.mutate({ id: module.module_id, position: module.sort_order + 1 })}
            >
              <ArrowDown className="size-4" />
            </Button>
            <SaveToLibrary module={module} />
            <ConfirmDialog
              title={`Remove module ${module.title}?`}
              consequence={`Remove module ${module.title} and its ${plural(module.topics.length, "topic")} from this course? A module that classes, content or tests already use is kept as archived (hidden from the outline, nothing is lost) instead of deleted.`}
              confirmLabel="Remove module"
              destructive
              onConfirm={() => remove.mutateAsync(undefined)}
            >
              <Button size="sm" variant="outline" aria-label={`Remove module ${module.title}`}>
                Remove
              </Button>
            </ConfirmDialog>
          </div>
        )}
      </div>
      <ul className="mt-2 divide-y text-sm" aria-label={`Topics of ${module.title}`}>
        {module.topics.map((t, i) => (
          <TopicRowView
            key={t.topic_id}
            topic={t}
            index={i}
            count={module.topics.length}
            module={module}
            versionTopics={modules}
            editable={editable}
            dragging={drag?.kind === "topic" && drag.id === t.topic_id}
            over={over === `topic-${t.topic_id}`}
            onMove={(position) => reorderTopic.mutate({ id: t.topic_id, position })}
            onDragStart={(e) => {
              e.stopPropagation();
              e.dataTransfer.effectAllowed = "move";
              e.dataTransfer.setData("text/plain", `topic-${t.topic_id}`);
              const row = e.currentTarget.closest("li");
              if (row) e.dataTransfer.setDragImage(row, 16, 16);
              setDrag({ kind: "topic", id: t.topic_id, parent: module.module_id });
            }}
            onDragEnd={() => {
              setDrag(null);
              setOver(null);
            }}
            onOver={(e) => {
              if (!acceptTopic(t)) return;
              e.preventDefault();
              e.stopPropagation();
              setOver(`topic-${t.topic_id}`);
            }}
            onDrop={(e) => {
              if (!acceptTopic(t)) return;
              e.preventDefault();
              e.stopPropagation();
              const moving = drag!.id;
              setOver(null);
              setDrag(null);
              reorderTopic.mutate({ id: moving, position: t.sort_order });
            }}
          />
        ))}
        {module.topics.length === 0 && (
          <li className="py-2 text-muted-foreground">No topics in this module yet.{editable ? " Add the first topic below." : ""}</li>
        )}
      </ul>
      {editable && (
        <div className="mt-2">
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline" aria-label={`Add a topic to ${module.title}`}>
                Add topic
              </Button>
            }
            title={`Add a topic to ${module.title}`}
            fields={[
              { name: "title", label: "Topic title", required: true },
              {
                name: "topic_class",
                label: "Class",
                type: "select",
                value: "Required",
                options: ["Required", "Recommended", "Optional"].map((c) => ({ value: c, label: c })),
                hint: "Only Required topics count towards a student's required learning.",
              },
            ]}
            onSubmit={(v) => addTopic.mutateAsync({ title: v["title"]!, topic_class: v["topic_class"] as TopicClass })}
          />
        </div>
      )}
    </li>
  );
}

/** Every module of one outline. */
export function ModuleTree({
  modules,
  editable,
  emptyReason,
  addAction,
}: {
  modules: ModuleContent[];
  editable: boolean;
  emptyReason?: string;
  addAction?: ReactNode;
}) {
  const [drag, setDrag] = useState<Drag>(null);
  const [over, setOver] = useState<string | null>(null);
  if (modules.length === 0) return <EmptyState reason={emptyReason ?? "This outline has no modules yet."} action={addAction} />;
  return (
    <ul className="space-y-3" aria-label="Modules">
      {modules.map((m, i) => (
        <ModuleCard
          key={m.module_id}
          module={m}
          index={i}
          count={modules.length}
          modules={modules}
          editable={editable}
          drag={drag}
          setDrag={setDrag}
          over={over}
          setOver={setOver}
        />
      ))}
    </ul>
  );
}
