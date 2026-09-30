import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi } from "@/api/delivery";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/lms/forms";
import { Note, PageHead, QueryView, Section } from "@/components/lms/ui";
import { ActionDialog, fromIstInput, toIstInput, useCanManage } from "@/features/shared/delivery-ui";
import { RequestsPanel, SessionsTable, useDelivery } from "@/features/shared/sessions";
import { useAuth } from "@/auth/auth";

const STATES = ["Scheduled", "Rescheduled", "Live", "Delivered", "Cancelled"];
const DAY_MS = 24 * 60 * 60 * 1000;

/** Schedule one class or a weekly series for a batch: the trainer, topic and room are chosen from what the batch actually has. */
function NewSessionDialog({ batches }: { batches: { batch_id: number; batch_code: string; course: { course_id: number; title: string }; mode: string }[] }) {
  const [batchId, setBatchId] = useState(batches[0]?.batch_id ?? 0);
  const batch = batches.find((b) => b.batch_id === batchId);
  const detail = useQuery({ queryKey: ["delivery", "batch", batchId], queryFn: () => deliveryApi.batch(batchId), enabled: batchId > 0 });
  const versions = useQuery({
    queryKey: ["delivery", "versions", "active", batch?.course.course_id],
    queryFn: () => deliveryApi.versions({ course_id: batch?.course.course_id, status: "Active", with_content: true }),
    enabled: !!batch,
  });
  const create = useDelivery((body: Record<string, unknown>) => deliveryApi.createSessions(body), "Session(s) scheduled — the batch has been told");
  const tomorrow = toIstInput(new Date(Date.now() + DAY_MS).toISOString()).slice(0, 11) + "10:00";
  const topics = (versions.data ?? []).flatMap((v) =>
    (v.modules ?? []).flatMap((m) => m.topics.map((t) => ({ value: t.topic_id, label: `${m.title} › ${t.title} (${v.version_label})` }))),
  );

  return (
    <ActionDialog
      trigger={<Button>New class session</Button>}
      title="Schedule a class session"
      description="One class, or repeat it weekly. Times are IST."
      submitLabel="Schedule"
      onFieldChange={(name, value) => name === "batch_id" && setBatchId(Number(value))}
      fields={[
        {
          name: "batch_id",
          label: "Batch",
          type: "select",
          required: true,
          options: batches.map((b) => ({ value: b.batch_id, label: `${b.batch_code} — ${b.course.title}` })),
        },
        { name: "title", label: "Title", required: true },
        { name: "topic_id", label: "Curriculum topic", type: "select", options: [{ value: "", label: "Not linked to a topic" }, ...topics], value: "" },
        { name: "starts_at", label: "Starts (IST)", type: "datetime", required: true, value: tomorrow },
        { name: "ends_at", label: "Ends (IST)", type: "datetime", required: true, value: tomorrow.slice(0, 11) + "12:00" },
        {
          name: "trainer_user_id",
          label: "Trainer",
          type: "select",
          options: [
            { value: "", label: "Batch lead trainer" },
            ...(detail.data?.trainers ?? []).map((t) => ({ value: t.user_id, label: `${t.full_name} (${t.role})` })),
          ],
          value: "",
        },
        {
          name: "mode",
          label: "Mode",
          type: "select",
          options: [
            { value: "", label: `Batch default (${batch?.mode ?? ""})` },
            ...["Classroom", "Live Online", "Hybrid"].map((m) => ({ value: m, label: m })),
          ],
          value: "",
        },
        { name: "room", label: "Room", placeholder: "Lab 1" },
        {
          name: "repeat",
          label: "Repeat",
          type: "select",
          options: [
            { value: "none", label: "Does not repeat" },
            { value: "weekly", label: "Every week, same day and time" },
          ],
          value: "none",
        },
        { name: "count", label: "Number of weekly sessions", type: "number", min: 2, value: "4", hint: "Used when repeating weekly (2–60)" },
        { name: "ack", label: "Room conflict", type: "checkbox", hint: "Allow a room that is already booked" },
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
          recurrence: v["repeat"] === "weekly" ? { count: Number(v["count"] || 4) } : undefined,
          acknowledge_room_conflict: v["ack"] === "true",
        })
      }
    />
  );
}

export function AcademicSchedule() {
  const manager = useCanManage();
  const { profile } = useAuth();
  const [batch, setBatch] = useState("");
  const [state, setState] = useState("");
  const batches = useQuery({ queryKey: ["delivery", "batches", "open"], queryFn: () => deliveryApi.batches({}) });
  const sessions = useQuery({
    queryKey: ["delivery", "sessions", "academic", batch, state],
    queryFn: () => deliveryApi.sessions({ batch_id: batch || undefined, state: state || undefined }),
  });
  const open = (batches.data?.data ?? []).filter((b) => b.state !== "Completed" && b.state !== "Cancelled");
  return (
    <>
      <PageHead
        title="Schedule / Actual Class Sessions"
        description="Scheduled classes, the actual Class Session, and the Meet association for each online class."
        actions={manager && open.length > 0 ? <NewSessionDialog batches={open} /> : undefined}
      />
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <NativeSelect
          aria-label="Filter by batch"
          placeholder="All batches"
          options={(batches.data?.data ?? []).map((b) => ({ value: b.batch_id, label: `${b.batch_code} — ${b.course.course_code}` }))}
          value={batch}
          onChange={(e) => setBatch(e.target.value)}
        />
        <NativeSelect
          aria-label="Filter by state"
          placeholder="All states"
          options={STATES.map((s) => ({ value: s, label: s }))}
          value={state}
          onChange={(e) => setState(e.target.value)}
        />
      </div>
      <QueryView query={sessions}>
        {(page) => (
          <SessionsTable
            caption="Class sessions"
            rows={page.data}
            withBranch={(profile?.allowed_branches.length ?? 0) > 1}
            actions={manager ? { manager: true, trainer: false } : null}
          />
        )}
      </QueryView>
      <Section className="mt-6" title="Reschedule requests from trainers">
        <RequestsPanel manager={manager} />
      </Section>
      <div className="mt-4">
        <Note>
          The LMS manages the scheduled class, the Calendar / Meet association, the actual Class Session and attendance evidence. It records Meet state; no
          Google connection is made until the integration is verified.
        </Note>
      </div>
    </>
  );
}
