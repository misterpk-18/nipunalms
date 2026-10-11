/** My Account (student): the Profile tab (who you are, email, language, messages, devices, password) and the Fees & Receipts tab. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { Download, Mail } from "lucide-react";
import { profileApi, type FinanceEntry, type FinanceSchedule, type MyProfile, type NextPayment } from "@/api/profile";
import type { Language } from "@/api/types";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { Field } from "@/components/lms/forms";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { DataTable, KeyValue, PageHead, PillTabs, QueryView, Section, StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { fmtDate, fmtDateTime } from "@/features/shared/format";
import { NotificationPreferences } from "@/features/shared/notification-preferences";
import { formatMoney, todayIso } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";
import { useLanguage, useT, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const TABS = ["profile", "fees"] as const;
type Tab = (typeof TABS)[number];

export function MyAccount() {
  const t = useT();
  const { tab = "profile" } = useSearch({ from: "/my-account" });
  const navigate = useNavigate({ from: "/my-account" });
  const labels: Record<Tab, string> = { profile: t("profile"), fees: t("finance") };
  return (
    <div className="mx-auto max-w-4xl">
      <PageHead title={t("myAccount")} description={t("acc_desc")} />
      <PillTabs
        tabs={TABS}
        value={tab}
        label={t("acc_views")}
        labels={labels}
        onChange={(next) => void navigate({ search: next === "profile" ? {} : { tab: next }, replace: true })}
      />
      {tab === "profile" ? <ProfileTab /> : <FeesTab />}
    </div>
  );
}

// ---------------------------------------------------------------- profile

function ProfileTab() {
  const t = useT();
  const { lang, setLang } = useLanguage();
  const query = useQuery({ queryKey: ["profile"], queryFn: profileApi.get });
  const refresh = { invalidate: [["profile"], ["me"]] };
  const setLanguage = useApiMutation((language: Language) => profileApi.setLanguage(language), refresh);
  const signOut = useApiMutation((sessionId: string) => profileApi.signOutDevice(sessionId), { ...refresh, success: t("acc_signed_out") });
  const signOutOthers = useApiMutation(() => profileApi.signOutOthers(), { ...refresh, success: (r) => t("acc_others_signed_out", { n: r.signed_out }) });
  const choose = (language: Language) => {
    setLang(language);
    setLanguage.mutate(language);
  };

  return (
    <QueryView query={query} skeleton="detail">
      {(profile) => {
        const student = profile.student;
        if (!student) return null;
        return (
          <div className="space-y-4">
            <Section title={t("acc_identity")}>
              <KeyValue
                items={[
                  [t("acc_student_id"), <span className="font-mono">{student.student_code}</span>],
                  [t("acc_name"), lang === "te" && student.name_te ? student.name_te : student.full_name],
                  [t("acc_email"), <EmailRow profile={profile} />],
                  [t("acc_mobile"), student.mobile_masked ?? "—"],
                  [t("acc_branch"), student.service_branch.branch_name],
                  [t("acc_account_status"), <StatusBadge domain="account" code={student.activation_status} />],
                ]}
              />
              <p className="mt-3 text-xs text-muted-foreground">{t("acc_contact_branch")}</p>
            </Section>

            <Section title={t("language")}>
              <div className="flex gap-2">
                <Button variant={lang === "en" ? "default" : "outline"} onClick={() => choose("en")}>
                  English
                </Button>
                <Button variant={lang === "te" ? "default" : "outline"} onClick={() => choose("te")}>
                  <span lang="te">తెలుగు</span>
                </Button>
              </div>
            </Section>

            <NotificationPreferences translated />

            <Section
              title={t("acc_devices")}
              actions={
                profile.devices.length > 1 && (
                  <ConfirmDialog
                    title={t("acc_others_title")}
                    consequence={t("acc_others_consequence")}
                    confirmLabel={t("acc_others_confirm")}
                    cancelLabel={t("cancel")}
                    onConfirm={async () => void (await signOutOthers.mutateAsync())}
                  >
                    <Button variant="outline" size="sm">
                      {t("acc_others_button")}
                    </Button>
                  </ConfirmDialog>
                )
              }
            >
              <ul className="space-y-2 text-sm">
                {profile.devices.map((d) => (
                  <li key={d.session_id} className="flex flex-wrap items-center justify-between gap-2">
                    <span>
                      {d.label} — {d.current ? t("acc_this_device") : fmtDateTime(d.last_seen_at)}
                    </span>
                    {d.current ? (
                      <Tag tone="success">{t("acc_active")}</Tag>
                    ) : (
                      <Button variant="outline" size="sm" onClick={() => signOut.mutate(d.session_id)} aria-label={`${t("acc_sign_out")}: ${d.label}`}>
                        {t("acc_sign_out")}
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            </Section>

            <Section title={t("acc_password")}>
              <KeyValue
                items={[
                  [t("password"), profile.password_changed_at ? t("acc_pw_changed", { date: fmtDate(profile.password_changed_at) }) : t("acc_pw_set")],
                  [t("acc_recovery"), student.email ? t("acc_recovery_email") : t("acc_recovery_whatsapp")],
                  [t("acc_last_sign_in"), fmtDateTime(profile.last_login_at)],
                ]}
              />
              <div className="mt-3">
                <Button variant="outline" asChild>
                  <Link to="/change-password">{t("changePassword")}</Link>
                </Button>
              </div>
            </Section>
          </div>
        );
      }}
    </QueryView>
  );
}

function EmailRow({ profile }: { profile: MyProfile }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const email = profile.student?.email ?? null;
  return (
    <span className="flex flex-wrap items-center gap-2">
      <span className={cn(!email && "text-muted-foreground")}>{email ?? t("acc_no_email")}</span>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        <Mail aria-hidden /> {email ? t("acc_change_email") : t("acc_add_email")}
      </Button>
      {open && <EmailDialog current={email} onClose={() => setOpen(false)} />}
    </span>
  );
}

/** Two steps: type the new address and ask for a code (sent to the WhatsApp number on file), then type the code. */
function EmailDialog({ current, onClose }: { current: string | null; onClose: () => void }) {
  const t = useT();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [notSent, setNotSent] = useState(false);

  const request = useApiMutation((address: string) => profileApi.requestEmailCode(address), {
    silentValidation: true,
    onSuccess: (answer, address) => {
      setProblem(null);
      setNotSent(!answer.sent);
      setAsked(answer.sent ? address : null);
    },
    onError: (error) => setProblem(error instanceof Error ? error.message : t("acc_email_failed")),
  });
  const confirm = useApiMutation((value: string) => profileApi.confirmEmail(value), {
    invalidate: [["profile"], ["me"]],
    success: t("acc_email_saved"),
    next: t("acc_email_saved_next"),
    silentValidation: true,
    onSuccess: () => onClose(),
    onError: (error) => setProblem(error instanceof Error ? error.message : t("acc_email_failed")),
  });

  const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{current ? t("acc_change_email") : t("acc_add_email")}</DialogTitle>
          <DialogDescription>{t("acc_email_intro")}</DialogDescription>
        </DialogHeader>
        {asked === null ? (
          <form
            className="space-y-3"
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              if (validEmail) request.mutate(email.trim());
            }}
          >
            <Field label={t("acc_new_email")} htmlFor="acc-new-email" error={problem ?? undefined}>
              <Input id="acc-new-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            {notSent && <StatusNote tone="warning">{t("acc_email_not_sent")}</StatusNote>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>
                {t("cancel")}
              </Button>
              <Button type="submit" disabled={!validEmail || request.isPending}>
                {t("acc_send_code")}
              </Button>
            </DialogFooter>
          </form>
        ) : (
          <form
            className="space-y-3"
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              if (code.trim().length >= 4) confirm.mutate(code.trim());
            }}
          >
            <StatusNote tone="info">{t("acc_code_sent", { email: asked })}</StatusNote>
            <Field label={t("acc_code")} htmlFor="acc-email-code" error={problem ?? undefined} hint={t("acc_code_hint")}>
              <Input
                id="acc-email-code"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={12}
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </Field>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => request.mutate(asked)} disabled={request.isPending}>
                {t("acc_send_again")}
              </Button>
              <Button type="submit" disabled={code.trim().length < 4 || confirm.isPending}>
                {t("acc_confirm_email")}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------- fees & receipts

function FeesTab() {
  const t = useT();
  const query = useQuery({ queryKey: ["finance", "me"], queryFn: profileApi.finance });
  return (
    <QueryView query={query} skeleton="cards" isEmpty={(d) => d.admissions.length === 0} empty={t("fin_none")}>
      {(data) => (
        <div className="space-y-4">
          <NextPaymentCard next={data.next_payment} />
          {data.admissions.map((entry) => (
            <AdmissionFinance key={entry.admission.admission_id} entry={entry} />
          ))}
          {data.schedules.length > 0 && <h2 className="pt-2 text-lg font-semibold">{t("fin_instalments")}</h2>}
          {data.schedules.map((schedule) => (
            <ScheduleFinance key={schedule.schedule_key} schedule={schedule} />
          ))}
          <HowThisWorks title={t("fin_how_title")}>
            <p>{t("fin_how_records")}</p>
            <p className="mt-2">{t("fin_how_receipts")}</p>
          </HowThisWorks>
        </div>
      )}
    </QueryView>
  );
}

function daysBetween(fromIso: string, toIso: string): number {
  return Math.round((Date.parse(`${toIso}T00:00:00Z`) - Date.parse(`${fromIso}T00:00:00Z`)) / 86_400_000);
}

/** The first thing on Fees: what to pay next, when, and how. Overdue turns red. */
export function NextPaymentCard({ next }: { next: NextPayment }) {
  const t = useT();
  if (next.state === "unknown") return <StatusNote tone="info">{t("fin_next_unknown")}</StatusNote>;
  if (next.state === "paid")
    return (
      <StatusNote tone="success" title={t("fin_next_title")}>
        {t("fin_next_paid")}
      </StatusNote>
    );
  const late = next.is_overdue;
  const amount = Number(next.overdue_amount) > 0 ? next.overdue_amount : next.amount;
  const days = next.due_date ? daysBetween(next.due_date, todayIso()) : 0;
  const instructions = next.how_to_pay.instructions;
  return (
    <section
      aria-label={t("fin_next_title")}
      data-testid="next-payment"
      data-overdue={late ? "true" : "false"}
      className={cn("rounded-xl border p-4 shadow-sm sm:p-5", late ? "border-destructive/50 bg-destructive/5" : "bg-card")}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{t("fin_next_title")}</p>
          <p className={cn("mt-1 text-3xl font-semibold tabular-nums", late && "text-destructive")}>{formatMoney(amount)}</p>
          <p className="mt-1 text-sm">
            {next.due_date ? t("fin_due_on", { date: fmtDate(next.due_date) }) : null}
            {late && (
              <span className="ml-2 font-medium text-destructive">
                {days > 0 ? t(days === 1 ? "fin_overdue_day" : "fin_overdue_days", { n: days }) : t("fin_overdue")}
              </span>
            )}
          </p>
          {next.courses.length > 0 && <p className="mt-1 text-xs text-muted-foreground">{next.courses.join(" + ")}</p>}
        </div>
      </div>
      <div className="mt-4 rounded-lg border bg-background p-3 text-sm">
        <p className="font-medium">{t("fin_how_to_pay")}</p>
        <p className="mt-1 whitespace-pre-line text-muted-foreground">{instructions ?? t("fin_pay_default", { branch: next.how_to_pay.branch.branch_name })}</p>
        <p className="mt-2 text-xs text-muted-foreground">{t("fin_no_online")}</p>
      </div>
    </section>
  );
}

function Amount({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function AdmissionFinance({ entry }: { entry: FinanceEntry }) {
  const t = useT();
  const summary = entry.summary;
  const download = useApiMutation((receiptNumber: string) => profileApi.receiptPdf(entry.admission.admission_id, receiptNumber), {
    success: t("fin_receipt_downloaded"),
  });
  return (
    <Section title={`${entry.admission.admission_code} · ${entry.course.title}`}>
      {summary === null ? (
        <StatusNote tone="warning">{t("fin_no_summary")}</StatusNote>
      ) : (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <Amount label={t("fin_fee")} value={formatMoney(summary.fee_total)} />
            <Amount label={t("fin_paid")} value={formatMoney(summary.verified_paid)} />
            <Amount label={t("fin_dues")} value={formatMoney(summary.balance)} />
          </div>
          {Number(summary.pending_verification) > 0 && (
            <p className="text-sm text-muted-foreground">{t("fin_pending", { amount: formatMoney(summary.pending_verification) })}</p>
          )}
          {summary.installments_scope === "invoice" && summary.invoice_numbers[0] && (
            <p className="text-sm text-muted-foreground">
              {t(summary.invoice_course_count > 1 ? "fin_invoice_shared" : "fin_invoice", {
                invoice: summary.invoice_numbers[0],
                n: summary.invoice_course_count,
              })}
            </p>
          )}
          <DataTable
            caption={t("fin_receipts_for", { code: entry.admission.admission_code })}
            rows={summary.receipts}
            getKey={(r) => r.receipt_number}
            empty={t("fin_no_receipts")}
            cols={[
              { h: t("fin_col_receipt"), c: (r) => <span className="font-mono text-xs">{r.receipt_number}</span> },
              { h: t("fin_col_amount"), c: (r) => formatMoney(r.amount) },
              { h: t("fin_col_date"), c: (r) => fmtDate(r.date) },
              {
                h: t("fin_col_pdf"),
                c: (r) => (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => download.mutate(r.receipt_number)}
                    disabled={download.isPending}
                    aria-label={`${t("fin_download")}: ${r.receipt_number}`}
                  >
                    <Download aria-hidden /> {t("fin_download")}
                  </Button>
                ),
              },
            ]}
          />
          <p className="text-xs text-muted-foreground">{t("fin_as_of", { when: fmtDateTime(summary.as_of) })}</p>
        </div>
      )}
    </Section>
  );
}

const POSITION: Record<string, TranslationKey> = {
  Paid: "fin_pos_paid",
  "Due soon": "fin_pos_soon",
  Overdue: "fin_pos_overdue",
  Upcoming: "fin_pos_upcoming",
  Due: "fin_pos_due",
};

/** One schedule, shown once: an invoice's instalments cover every course on that invoice. */
function ScheduleFinance({ schedule }: { schedule: FinanceSchedule }) {
  const t = useT();
  const courses = schedule.admissions.map((a) => a.course.title).join(" + ");
  const title = schedule.invoice_number ? `${schedule.invoice_number} · ${courses}` : `${t("fin_instalments")} · ${courses}`;
  return (
    <Section title={title}>
      <div className="space-y-3">
        <DataTable
          caption={t("fin_instalments_for", { title })}
          rows={schedule.installments}
          getKey={(i) => i.installment_no}
          empty={t("fin_no_schedule")}
          cols={[
            { h: "#", c: (i) => i.installment_no },
            { h: t("fin_col_due"), c: (i) => fmtDate(i.due_date) },
            { h: t("fin_col_amount"), c: (i) => formatMoney(i.amount) },
            { h: t("fin_col_covered"), c: (i) => formatMoney(i.covered) },
            { h: t("fin_col_balance"), c: (i) => formatMoney(i.balance) },
            {
              h: t("fin_col_state"),
              c: (i) =>
                i.due_position ? (
                  <Tag tone={i.due_position === "Overdue" ? "danger" : i.due_position === "Paid" ? "success" : "neutral"}>
                    {POSITION[i.due_position] ? t(POSITION[i.due_position]!) : i.due_position}
                  </Tag>
                ) : (
                  "—"
                ),
            },
          ]}
        />
        <p className="text-xs text-muted-foreground">{t("fin_as_of", { when: fmtDateTime(schedule.as_of) })}</p>
      </div>
    </Section>
  );
}
