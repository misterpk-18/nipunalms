/** Two cards on My Courses: changes to a batch that need the student's agreement (Module 15 §12) and the preferred-slot request. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi, type MyMaterialChange, type SlotOption, type SlotPreference } from "@/api/delivery";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/lms/forms";
import { Note, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { ActionDialog, fmtDate, fmtDay, mono } from "@/features/shared/delivery-ui";
import { useDelivery } from "@/features/shared/sessions";

// ---------------------------------------------------------------- changes needing agreement

function ChangeCard({ change }: { change: MyMaterialChange }) {
  const respond = useDelivery(
    (v: { response: "Agreed" | "Declined"; note?: string }) => deliveryApi.respondToChange(change.change_id, v),
    "Your answer is recorded",
  );
  const mine = change.my_response;
  const answered = mine.response !== "Pending";
  return (
    <li className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge tone="info">{change.kind}</StatusBadge>
        {mono(change.batch.batch_code)}
        {answered && <StatusBadge tone={mine.response === "Agreed" ? "success" : "warning"}>You {mine.response.toLowerCase()}</StatusBadge>}
      </div>
      <p className="mt-2 text-sm">
        <span className="text-muted-foreground">Now: </span>
        {change.current_plan ?? "—"}
      </p>
      <p className="text-sm">
        <span className="text-muted-foreground">Proposed: </span>
        {change.proposed_plan}
      </p>
      <p className="text-sm">
        <span className="text-muted-foreground">Why: </span>
        {change.reason}
      </p>
      {change.alternative && (
        <p className="text-sm">
          <span className="text-muted-foreground">If you do not agree: </span>
          {change.alternative}
        </p>
      )}
      {answered ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Answered {mine.responded_at ? fmtDate(mine.responded_at) : ""}
          {mine.note ? ` · ${mine.note}` : ""}
        </p>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          <ActionDialog
            trigger={<Button size="sm">Agree</Button>}
            title="Agree to this change"
            description="You are agreeing to the proposed plan above for this batch."
            fields={[{ name: "note", label: "Note (optional)", type: "textarea" }]}
            submitLabel="Agree"
            onSubmit={(v) => respond.mutateAsync({ response: "Agreed", note: v["note"] || undefined })}
          />
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Decline
              </Button>
            }
            title="Decline this change"
            description="Your coordinator will arrange the alternative with you."
            fields={[{ name: "note", label: "Note (optional)", type: "textarea" }]}
            submitLabel="Decline"
            onSubmit={(v) => respond.mutateAsync({ response: "Declined", note: v["note"] || undefined })}
          />
        </div>
      )}
    </li>
  );
}

export function MaterialChangesCard() {
  const query = useQuery({ queryKey: ["delivery", "my-material-changes"], queryFn: deliveryApi.myChanges });
  return (
    <Section title="Changes needing your agreement">
      <QueryView query={query} isEmpty={(rows) => rows.length === 0} empty="Nothing needs your agreement right now.">
        {(rows) => (
          <ul className="space-y-3">
            {rows.map((c) => (
              <ChangeCard key={c.change_id} change={c} />
            ))}
          </ul>
        )}
      </QueryView>
      <div className="mt-3">
        <Note>Reading a notice is not agreement. A change to your batch only goes ahead for you once you answer Agree here, or your coordinator records your answer.</Note>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------- preferred slot

const OPEN_STATUSES = ["Requested", "Waitlisted"];
const STATUS_TONE = { Requested: "info", Waitlisted: "warning", Confirmed: "success", "Not Possible": "danger", Withdrawn: "neutral" } as const;

const optionLabel = (o: SlotOption) =>
  [
    o.display_name ?? o.batch_code,
    o.display_name ? o.batch_code : null,
    o.schedule_days.length ? o.schedule_days.join(", ") : null,
    o.start_time && o.end_time ? `${o.start_time}–${o.end_time}` : null,
    o.mode,
    o.planned_start ? `starts ${o.planned_start}` : null,
    o.state_label,
    o.is_full ? "full" : null,
  ]
    .filter(Boolean)
    .join(" · ");

function CurrentRequest({ preference }: { preference: SlotPreference }) {
  const withdraw = useDelivery((id: number) => deliveryApi.withdrawSlot(id), "Request withdrawn");
  const details = [
    preference.batch ? `Batch ${preference.batch.batch_code}` : null,
    preference.preferred_days.length ? preference.preferred_days.join(", ") : null,
    preference.preferred_start && preference.preferred_end ? `${preference.preferred_start}–${preference.preferred_end}` : null,
    preference.preferred_mode,
  ].filter(Boolean);
  return (
    <div className="space-y-2 rounded-xl border p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge tone={STATUS_TONE[preference.status]}>{preference.status}</StatusBadge>
        <span>{details.join(" · ") || "Your request"}</span>
      </div>
      {preference.note && <p className="text-muted-foreground">Your note: {preference.note}</p>}
      {preference.status_note && <p>From the academic team: {preference.status_note}</p>}
      <p className="text-xs text-muted-foreground">Requested {fmtDate(preference.created_at)}.</p>
      {OPEN_STATUSES.includes(preference.status) && (
        <Button size="sm" variant="outline" onClick={() => withdraw.mutate(preference.preference_id)}>
          Withdraw request
        </Button>
      )}
    </div>
  );
}

function SlotForm({ enrolmentId, options }: { enrolmentId: number; options: SlotOption[] }) {
  const request = useDelivery((body: Record<string, unknown>) => deliveryApi.requestSlot(body), "Request sent — it does not reserve a seat");
  return (
    <ActionDialog
      trigger={<Button size="sm">Request a preferred slot</Button>}
      title="Request a preferred slot"
      description="Choose a batch, or say which days and times suit you. A request does not reserve a seat."
      fields={[
        { name: "batch_id", label: "A batch you would like", type: "select", options: [{ value: "", label: "No particular batch" }, ...options.map((o) => ({ value: o.batch_id, label: optionLabel(o) }))], value: "" },
        { name: "preferred_days", label: "Days that suit you", type: "days" },
        { name: "preferred_start", label: "Earliest start (IST)", type: "time" },
        { name: "preferred_end", label: "Latest finish (IST)", type: "time" },
        {
          name: "preferred_mode",
          label: "Mode",
          type: "select",
          options: [{ value: "", label: "Any" }, ...["Classroom", "Live Online", "Hybrid"].map((m) => ({ value: m, label: m }))],
          value: "",
        },
        { name: "note", label: "Anything we should know", type: "textarea" },
      ]}
      submitLabel="Send request"
      onSubmit={(v) =>
        request.mutateAsync({
          enrolment_id: enrolmentId,
          batch_id: v["batch_id"] ? Number(v["batch_id"]) : undefined,
          preferred_days: v["preferred_days"] ? v["preferred_days"].split(",") : undefined,
          preferred_start: v["preferred_start"] || undefined,
          preferred_end: v["preferred_end"] || undefined,
          preferred_mode: v["preferred_mode"] || undefined,
          note: v["note"] || undefined,
        })
      }
    />
  );
}

export function SlotPreferenceCard() {
  const enrolments = useQuery({ queryKey: ["delivery", "my-enrolments"], queryFn: deliveryApi.myEnrolments });
  const [chosen, setChosen] = useState<number | null>(null);
  const rows = (enrolments.data ?? []).filter((e) => !e.parent_enrolment_id);
  const enrolmentId = chosen ?? rows.find((e) => !e.batch)?.enrolment_id ?? rows[0]?.enrolment_id ?? 0;
  const preferences = useQuery({ queryKey: ["delivery", "my-slot-preferences"], queryFn: deliveryApi.mySlotPreferences });
  const options = useQuery({
    queryKey: ["delivery", "slot-options", enrolmentId],
    queryFn: () => deliveryApi.slotOptions(enrolmentId),
    enabled: enrolmentId > 0,
  });
  const forEnrolment = (preferences.data ?? []).filter((p) => p.enrolment_id === enrolmentId && p.status !== "Withdrawn");
  const current = forEnrolment.find((p) => OPEN_STATUSES.includes(p.status)) ?? forEnrolment[0];
  return (
    <Section title="Preferred slot">
      {rows.length > 1 && (
        <div className="mb-3 max-w-md">
          <NativeSelect
            aria-label="Course for the slot request"
            options={rows.map((e) => ({ value: e.enrolment_id, label: `${e.course.course_code} — ${e.course.title}` }))}
            value={enrolmentId}
            onChange={(e) => setChosen(Number(e.target.value))}
          />
        </div>
      )}
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">You have no course enrolment to ask about yet.</p>
      ) : (
        <div className="space-y-3">
          <QueryView query={preferences}>{() => (current ? <CurrentRequest preference={current} /> : <p className="text-sm text-muted-foreground">You have no open slot request for this course.</p>)}</QueryView>
          {(!current || !OPEN_STATUSES.includes(current.status)) && (
            <QueryView query={options}>
              {(list) => (
                <>
                  {list.length > 0 && (
                    <ul className="space-y-1 text-sm">
                      {list.map((o) => (
                        <li key={o.batch_id}>
                          {optionLabel(o)}
                          {o.planned_start ? ` (${fmtDay(o.planned_start)})` : ""}
                        </li>
                      ))}
                    </ul>
                  )}
                  {list.length === 0 && <p className="text-sm text-muted-foreground">No open batch is listed for your course at your branch right now. You can still say which days and times suit you.</p>}
                  <SlotForm enrolmentId={enrolmentId} options={list} />
                </>
              )}
            </QueryView>
          )}
        </div>
      )}
      <div className="mt-3">
        <Note>A request does not reserve a seat. A seat comes only from an allocation to a batch, which your coordinator makes after checking the batch has room.</Note>
      </div>
    </Section>
  );
}
