/** Schedule one class, or a weekly series. Opened from a batch, it is already filled in from the batch: its next teaching day and time, room, trainer and next topic. */
import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi, type Batch, type ClassSession } from "@/api/delivery";
import { useAuth } from "@/auth/auth";
import { ActionDialog, fromIstInput, toIstInput } from "@/features/shared/delivery-ui";
import { useDelivery } from "@/features/shared/sessions";

const PURPOSES = ["Regular", "Replacement", "Remedial", "Extra"].map((p) => ({ value: p, label: p }));
const DAY_MS = 24 * 60 * 60 * 1000;
const WEEKDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** "YYYY-MM-DDTHH:mm" (IST) of the batch's next teaching day at its class time; tomorrow 10:00 when it has no timetable. */
export function nextClassSlot(batch: Pick<Batch, "schedule_days" | "start_time" | "end_time"> | undefined, from = new Date()): { start: string; end: string } {
  const start = batch?.start_time ?? "10:00";
  const end = batch?.end_time ?? "12:00";
  for (let n = 0; n < 15; n += 1) {
    const day = toIstInput(new Date(from.getTime() + n * DAY_MS).toISOString()).slice(0, 10);
    const weekday = WEEKDAY[new Date(`${day}T12:00:00Z`).getUTCDay()]!;
    const teaches = !batch || batch.schedule_days.length === 0 || batch.schedule_days.includes(weekday);
    const later = new Date(`${day}T${start}:00+05:30`).getTime() > Date.now() + 60_000;
    if (teaches && later) return { start: `${day}T${start}`, end: `${day}T${end}` };
  }
  const day = toIstInput(new Date(from.getTime() + DAY_MS).toISOString()).slice(0, 10);
  return { start: `${day}T${start}`, end: `${day}T${end}` };
}

export function NewClassDialog({
  batches,
  batchId: initialBatchId,
  replaces,
  open,
  onOpenChange,
  trigger,
  approve: approver,
}: {
  batches: Batch[];
  /** Set by the route: true only for the Branch Manager (may accept advisory warnings with a reason). */
  approve: boolean;
  /** The batch to start from (the batch page passes its own). */
  batchId?: number;
  /** A cancelled class this one replaces. */
  replaces?: ClassSession;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  trigger?: ReactNode;
}) {
  const { profile } = useAuth();
  // The dialog is re-created when the batch changes (to fill it in again), so whether it is open is kept out here
  const [ownOpen, setOwnOpen] = useState(false);
  const isOpen = open ?? ownOpen;
  const [batchId, setBatchId] = useState(initialBatchId ?? replaces?.batch.batch_id ?? batches[0]?.batch_id ?? 0);
  const batch = batches.find((b) => b.batch_id === batchId);
  const batchSessions = useQuery({
    queryKey: ["delivery", "sessions", "batch", batchId],
    queryFn: () => deliveryApi.sessions({ batch_id: batchId }),
    enabled: batchId > 0,
  });
  const detail = useQuery({ queryKey: ["delivery", "batch", batchId], queryFn: () => deliveryApi.batch(batchId), enabled: batchId > 0 });
  const owners = useQuery({
    queryKey: ["delivery", "staff", "BRANCH_MANAGER", batch?.branch.branch_id],
    queryFn: () => deliveryApi.staff("BRANCH_MANAGER", batch!.branch.branch_id),
    enabled: !!batch,
  });
  const versions = useQuery({
    queryKey: ["delivery", "versions", "active", batch?.course.course_id],
    queryFn: () => deliveryApi.versions({ course_id: batch?.course.course_id, status: "Active", with_content: true }),
    enabled: !!batch,
  });
  const create = useDelivery((body: Record<string, unknown>) => deliveryApi.createSessions(body), "Class scheduled");

  const sessions = batchSessions.data?.data ?? [];
  const owed = sessions.filter((x) => x.state === "Cancelled" || x.delivery_outcome === "Partially Held");
  const used = new Set(sessions.filter((x) => x.state !== "Cancelled" && x.topic).map((x) => x.topic!.topic_id));
  const topics = (versions.data ?? []).flatMap((v) =>
    (v.modules ?? []).flatMap((m) => m.topics.map((t) => ({ value: t.topic_id, label: `${m.title} › ${t.title}` }))),
  );
  const nextTopic = (versions.data ?? []).flatMap((v) => (v.modules ?? []).flatMap((m) => m.topics)).find((t) => !used.has(t.topic_id));
  const me = profile?.user.user_id ?? 0;
  const ownerOptions = [
    { value: me, label: "Me" },
    ...(owners.data ?? []).filter((o) => o.user_id !== me).map((o) => ({ value: o.user_id, label: o.full_name })),
  ];
  const slot = nextClassSlot(batch);
  const purpose = replaces ? "Replacement" : "Regular";
  const ready = !!batch && !batchSessions.isPending && !versions.isPending && !detail.isPending;

  return (
    <ActionDialog
      // a new batch pre-fills everything again
      key={`${batchId}-${ready}`}
      {...(trigger ? { trigger } : {})}
      open={isOpen}
      onOpenChange={(next) => {
        setOwnOpen(next);
        onOpenChange?.(next);
      }}
      title={replaces ? `Replace "${replaces.title}"` : "New class"}
      description="One class, or repeat it weekly. Times are IST. The class is filled in from the batch; change anything you need. The students and the trainer are told when it is scheduled."
      submitLabel="Schedule class"
      onFieldChange={(name, value) => name === "batch_id" && setBatchId(Number(value))}
      fields={[
        {
          name: "batch_id",
          label: "Batch",
          type: "select",
          required: true,
          value: String(batchId),
          options: batches.map((b) => ({ value: b.batch_id, label: `${b.display_name ?? b.batch_code} — ${b.course.title}` })),
        },
        {
          name: "title",
          label: "Title",
          required: true,
          value: replaces ? `${replaces.title} (replacement)` : (nextTopic?.title ?? (batch ? `${batch.course.title} class` : "")),
        },
        {
          name: "topic_id",
          label: "Curriculum topic",
          type: "select",
          options: [{ value: "", label: "Not linked to a topic" }, ...topics],
          value: replaces?.topic ? String(replaces.topic.topic_id) : String(nextTopic?.topic_id ?? ""),
        },
        { name: "starts_at", label: "Starts (IST)", type: "datetime", required: true, value: slot.start },
        { name: "ends_at", label: "Ends (IST)", type: "datetime", required: true, value: slot.end },
        {
          name: "trainer_user_id",
          label: "Trainer",
          type: "select",
          options: [
            { value: "", label: "The batch's lead trainer" },
            ...(detail.data?.trainers ?? []).map((t) => ({ value: t.user_id, label: `${t.full_name} (${t.role})` })),
          ],
          value: "",
        },
        {
          name: "mode",
          label: "Mode",
          type: "select",
          options: [
            { value: "", label: `As the batch (${batch?.mode ?? ""})` },
            ...["Classroom", "Live Online", "Hybrid"].map((m) => ({ value: m, label: m })),
          ],
          value: "",
        },
        { name: "room", label: "Room", placeholder: "Lab 1", value: batch && batch.mode !== "Live Online" ? (batch.location ?? "") : "" },
        {
          name: "repeat",
          label: "Repeat",
          type: "select",
          options: [
            { value: "none", label: "Does not repeat" },
            { value: "weekly", label: "Every week, same day and time" },
          ],
          value: "none",
          showIf: (v) => (v["purpose"] ?? purpose) === "Regular",
        },
        {
          name: "count",
          label: "Number of weekly classes",
          type: "number",
          min: 2,
          value: "4",
          hint: "2 to 60",
          showIf: (v) => v["repeat"] === "weekly" && (v["purpose"] ?? purpose) === "Regular",
        },
        {
          name: "purpose",
          label: "Kind of class",
          type: "select",
          options: PURPOSES,
          value: purpose,
          hint: "A replacement, remedial or extra class needs a Branch Manager's approval before students see it",
        },
        {
          name: "replaces_session_id",
          label: "Class being replaced",
          type: "select",
          required: true,
          showIf: (v) => v["purpose"] === "Replacement",
          value: replaces ? String(replaces.session_id) : String(owed[0]?.session_id ?? ""),
          options: owed.map((x) => ({ value: x.session_id, label: `${x.title} (${x.state_label})` })),
        },
        {
          name: "purpose_reference",
          label: "What it is for",
          type: "textarea",
          required: true,
          showIf: (v) => v["purpose"] === "Remedial" || v["purpose"] === "Extra",
          hint: "The class, topic or reason this one follows up",
        },
        {
          name: "owner_user_id",
          label: "Who sees it through",
          type: "select",
          options: ownerOptions,
          value: String(me),
          showIf: (v) => v["purpose"] !== "Regular",
        },
        { name: "due_on", label: "Hold it by", type: "date", required: true, showIf: (v) => v["purpose"] !== "Regular", value: slot.start.slice(0, 10) },
        { name: "meet_space_id", label: "Meet space ID", hint: "Optional; recorded as given", advanced: true },
        { name: "calendar_series_id", label: "Calendar series ID", hint: "Optional; recorded as given", advanced: true },
        ...(approver
          ? [{ name: "override_reason", label: "Why the warning is acceptable", type: "textarea" as const, required: true, afterWarnings: true }]
          : []),
      ]}
      onSubmit={(v) =>
        create.mutateAsync({
          batch_id: Number(v["batch_id"]),
          title: v["title"],
          topic_id: v["topic_id"] ? Number(v["topic_id"]) : undefined,
          starts_at: fromIstInput(v["starts_at"]!),
          ends_at: fromIstInput(v["ends_at"]!),
          trainer_user_id: v["trainer_user_id"] ? Number(v["trainer_user_id"]) : undefined,
          mode: v["mode"] || undefined,
          room: v["room"] || undefined,
          recurrence: v["repeat"] === "weekly" && (v["purpose"] ?? "Regular") === "Regular" ? { count: Number(v["count"] || 4) } : undefined,
          purpose: v["purpose"] || undefined,
          replaces_session_id: v["replaces_session_id"] ? Number(v["replaces_session_id"]) : undefined,
          purpose_reference: v["purpose_reference"] || undefined,
          owner_user_id: v["owner_user_id"] ? Number(v["owner_user_id"]) : undefined,
          due_on: v["due_on"] || undefined,
          meet_space_id: v["meet_space_id"] || undefined,
          calendar_series_id: v["calendar_series_id"] || undefined,
          override_reason: v["override_reason"] || undefined,
        })
      }
    />
  );
}
