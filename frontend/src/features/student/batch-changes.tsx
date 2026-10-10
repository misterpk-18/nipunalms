/** The preferred-slot request: shown on Home only while a course has no batch yet. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi, type SlotOption, type SlotPreference } from "@/api/delivery";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/lms/forms";
import { Note, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { ActionDialog, fmtDay } from "@/features/shared/delivery-ui";
import { fmtDate } from "@/features/shared/format";
import { useDelivery } from "@/features/shared/sessions";
import { useT } from "@/lib/i18n";

// ---------------------------------------------------------------- preferred slot

const OPEN_STATUSES = ["Requested", "Waitlisted"];

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
  const t = useT();
  const withdraw = useDelivery((id: number) => deliveryApi.withdrawSlot(id), t("slot_withdrawn"));
  const details = [
    preference.batch ? `Batch ${preference.batch.batch_code}` : null,
    preference.preferred_days.length ? preference.preferred_days.join(", ") : null,
    preference.preferred_start && preference.preferred_end ? `${preference.preferred_start}–${preference.preferred_end}` : null,
    preference.preferred_mode,
  ].filter(Boolean);
  return (
    <div className="space-y-2 rounded-xl border p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge domain="slot" code={preference.status} />
        <span>{details.join(" · ") || t("slot_your_request")}</span>
      </div>
      {preference.note && <p className="text-muted-foreground">{t("slot_your_note", { note: preference.note })}</p>}
      {preference.status_note && <p>{t("slot_from_team", { note: preference.status_note })}</p>}
      <p className="text-xs text-muted-foreground">{t("slot_requested_on", { when: fmtDate(preference.created_at) })}</p>
      {OPEN_STATUSES.includes(preference.status) && (
        <Button size="sm" variant="outline" onClick={() => withdraw.mutate(preference.preference_id)}>
          {t("slot_withdraw")}
        </Button>
      )}
    </div>
  );
}

function SlotForm({ enrolmentId, options }: { enrolmentId: number; options: SlotOption[] }) {
  const t = useT();
  const request = useDelivery((body: Record<string, unknown>) => deliveryApi.requestSlot(body), t("slot_sent"));
  return (
    <ActionDialog
      trigger={<Button size="sm">{t("slot_request_button")}</Button>}
      title={t("slot_request_button")}
      description={t("slot_request_help")}
      fields={[
        {
          name: "batch_id",
          label: t("slot_batch_field"),
          type: "select",
          options: [{ value: "", label: t("slot_no_batch") }, ...options.map((o) => ({ value: o.batch_id, label: optionLabel(o) }))],
          value: "",
        },
        { name: "preferred_days", label: t("slot_days"), type: "days" },
        { name: "preferred_start", label: t("slot_start"), type: "time" },
        { name: "preferred_end", label: t("slot_end"), type: "time" },
        {
          name: "preferred_mode",
          label: t("slot_mode"),
          type: "select",
          options: [{ value: "", label: t("slot_any") }, ...["Classroom", "Live Online", "Hybrid"].map((m) => ({ value: m, label: m }))],
          value: "",
        },
        { name: "note", label: t("slot_anything"), type: "textarea" },
      ]}
      submitLabel={t("slot_send")}
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
  const t = useT();
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
    <Section title={t("slot_title")}>
      <p className="mb-3 text-sm text-muted-foreground">{t("preferredSlotHelp")}</p>
      {rows.length > 1 && (
        <div className="mb-3 max-w-md">
          <NativeSelect
            aria-label={t("slot_course_label")}
            options={rows.map((e) => ({ value: e.enrolment_id, label: `${e.course.course_code} — ${e.course.title}` }))}
            value={enrolmentId}
            onChange={(e) => setChosen(Number(e.target.value))}
          />
        </div>
      )}
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("slot_none_course")}</p>
      ) : (
        <div className="space-y-3">
          <QueryView query={preferences}>
            {() => (current ? <CurrentRequest preference={current} /> : <p className="text-sm text-muted-foreground">{t("slot_none_open")}</p>)}
          </QueryView>
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
                  {list.length === 0 && <p className="text-sm text-muted-foreground">{t("slot_no_batches")}</p>}
                  <SlotForm enrolmentId={enrolmentId} options={list} />
                </>
              )}
            </QueryView>
          )}
        </div>
      )}
      <div className="mt-3">
        <Note>{t("slot_note")}</Note>
      </div>
    </Section>
  );
}
