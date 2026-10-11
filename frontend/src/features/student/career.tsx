/** Career: a four-step checklist (opt in, profile, CV reviewed, share with employers), then jobs, applications and offers. */
import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { Briefcase, Check } from "lucide-react";
import { careerApi, type CareerOverview, type CareerProfile, type CareerStepKey, type ProfileUpdate } from "@/api/career";
import { EmptyState } from "@/components/lms/empty-state";
import { Field, NativeSelect, applyServerErrors } from "@/components/lms/forms";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { DataTable, KeyValue, PageHead, QueryView, Section, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { fmtDate, fmtDateTime } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { useT, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const KEY = [["career"]];
const list = (text: string) =>
  text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

const STEP_TITLE: Record<CareerStepKey, TranslationKey> = {
  opt_in: "cr_step_opt_in",
  profile: "cr_step_profile",
  cv: "cr_step_cv",
  share: "cr_step_share",
};
const NEEDS_WORD: Record<CareerStepKey, TranslationKey> = {
  opt_in: "cr_need_opt_in",
  profile: "cr_need_profile",
  cv: "cr_need_cv",
  share: "cr_need_share",
};
const WORK_MODES = ["On-site", "Remote", "Hybrid", "Any"] as const;
const WORK_MODE_KEY: Record<(typeof WORK_MODES)[number], TranslationKey> = {
  "On-site": "cr_mode_onsite",
  Remote: "cr_mode_remote",
  Hybrid: "cr_mode_hybrid",
  Any: "cr_mode_any",
};
const LEVELS = ["Fresher", "Experienced"] as const;

/** Scrolls to a checklist step and puts focus on it, so "Needs: reviewed CV" lands on the step that fixes it. */
function goToStep(key: CareerStepKey) {
  const element = document.getElementById(`career-step-${key}`);
  element?.scrollIntoView({ behavior: "smooth", block: "center" });
  element?.focus({ preventScroll: true });
}

export function Career() {
  const t = useT();
  const query = useQuery({ queryKey: ["career", "me"], queryFn: careerApi.overview });
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead title={t("careerSupport")} description={t("cr_desc")} />
      <QueryView query={query} skeleton="cards">
        {(overview) => <CareerBody overview={overview} />}
      </QueryView>
    </div>
  );
}

function CareerBody({ overview }: { overview: CareerOverview }) {
  const t = useT();
  const { profile } = overview;
  const [editing, setEditing] = useState(false);
  const optIn = useApiMutation(() => careerApi.updateProfile({ opted_in: true }), {
    invalidate: KEY,
    success: t("cr_opted_in_toast"),
    next: t("cr_opted_in_next"),
  });
  const consent = useApiMutation((value: boolean) => careerApi.setConsent(value), {
    invalidate: KEY,
    success: (o) => (o.profile.sharing_consent ? t("cr_consent_given") : t("cr_consent_withdrawn")),
  });
  const apply = useApiMutation((id: number) => careerApi.apply(id), { invalidate: KEY, success: t("cr_applied_toast"), next: t("cr_applied_next") });
  const withdraw = useApiMutation((id: number) => careerApi.withdraw(id), { invalidate: KEY, success: t("cr_withdrawn_toast") });
  const needs = overview.apply_needs;

  return (
    <>
      <Checklist
        overview={overview}
        onOptIn={() => optIn.mutate()}
        optInBusy={optIn.isPending}
        onEdit={() => setEditing(true)}
        onConsent={(value) => consent.mutateAsync(value)}
        consentBusy={consent.isPending}
      />
      {profile.opted_in && <ProfileEditor profile={profile} open={editing} onOpenChange={setEditing} />}

      {profile.opted_in && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Section
            title={t("cr_profile_title")}
            actions={
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                {t("cr_edit_profile")}
              </Button>
            }
          >
            <KeyValue
              items={[
                [t("cr_k_support_period"), profile.support_end ? t("cr_until", { date: fmtDate(profile.support_end) }) : "—"],
                [t("cr_k_roles"), profile.preferred_roles.join(", ") || "—"],
                [t("cr_k_locations"), profile.preferred_locations.join(", ") || "—"],
                [
                  t("cr_k_skills"),
                  profile.skills.length ? (
                    <span className="flex flex-wrap gap-1">
                      {profile.skills.map((s) => (
                        <Tag key={s.name} tone={s.confidence === "Verified" ? "success" : "neutral"}>
                          {s.name} · {s.confidence === "Verified" ? t("cr_skill_verified") : t("cr_skill_reported")}
                        </Tag>
                      ))}
                    </span>
                  ) : (
                    "—"
                  ),
                ],
                [t("cr_k_readiness"), <StatusBadge domain="career" code={profile.readiness} />],
              ]}
            />
          </Section>
          <CvSection overview={overview} />
        </div>
      )}

      <Section id="career-jobs" title={t("cr_jobs_title")}>
        <p className="mb-3 text-xs text-muted-foreground">{t("noGuarantee")}</p>
        {!profile.opted_in ? (
          <EmptyState
            icon={Briefcase}
            reason={t("cr_jobs_opt_in_first")}
            action={
              <Button onClick={() => optIn.mutate()} disabled={optIn.isPending}>
                {t("cr_opt_in_button")}
              </Button>
            }
          />
        ) : overview.opportunities.length === 0 ? (
          <EmptyState icon={Briefcase} reason={t("cr_jobs_none")} />
        ) : (
          <>
            <p className="mb-3 text-sm">{t(overview.opportunities.length === 1 ? "cr_jobs_one" : "cr_jobs_many", { count: overview.opportunities.length })}</p>
            {needs.length > 0 && <NeedsLine needs={needs} />}
            <ul className="grid gap-3 md:grid-cols-2">
              {overview.opportunities.map((o) => (
                <li key={o.opportunity_id} className="rounded-lg border p-3 text-sm">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold">{o.title}</p>
                      <p>{o.employer_name}</p>
                    </div>
                    <StatusBadge domain="career" code="Verified" />
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {o.employment_type} · {o.work_mode}
                    {o.location ? ` · ${o.location}` : ""} · {o.compensation_text}
                    {o.closing_date ? ` · ${t("cr_closes", { date: fmtDate(o.closing_date) })}` : ""}
                  </p>
                  {o.required_skills.length > 0 && <p className="mt-1 text-xs">{t("cr_skills_needed", { skills: o.required_skills.join(", ") })}</p>}
                  <div className="mt-2">
                    {o.applied ? (
                      <StatusBadge domain="career" code="Applied" />
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => apply.mutate(o.opportunity_id)}
                        disabled={needs.length > 0 || apply.isPending}
                        aria-label={`${t("cr_apply")}: ${o.title}`}
                      >
                        {t("cr_apply")}
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </Section>

      <h2 className="text-lg font-semibold">{t("cr_applications_title")}</h2>
      <DataTable
        caption={t("cr_applications_title")}
        rows={overview.applications}
        getKey={(a) => a.application_id}
        empty={t("cr_applications_none")}
        cols={[
          { h: t("cr_col_role"), c: (a) => a.opportunity.title },
          { h: t("cr_col_employer"), c: (a) => a.opportunity.employer_name },
          {
            h: t("cr_col_interview"),
            c: (a) => (a.interview_round ? `${a.interview_round}${a.interview_at ? ` — ${fmtDateTime(a.interview_at)}` : ""}` : (a.status_note ?? "—")),
          },
          { h: t("cr_col_state"), c: (a) => <StatusBadge domain="career" code={a.status} /> },
          {
            h: t("cr_col_action"),
            c: (a) =>
              a.closed ? (
                "—"
              ) : (
                <ConfirmDialog
                  title={t("cr_withdraw_title")}
                  consequence={t("cr_withdraw_consequence")}
                  confirmLabel={t("cr_withdraw")}
                  cancelLabel={t("cancel")}
                  destructive
                  onConfirm={async () => void (await withdraw.mutateAsync(a.application_id))}
                >
                  <Button size="sm" variant="outline" aria-label={`${t("cr_withdraw")}: ${a.opportunity.title}`}>
                    {t("cr_withdraw")}
                  </Button>
                </ConfirmDialog>
              ),
          },
        ]}
      />
      {overview.outcomes.length > 0 && (
        <Section title={t("cr_outcomes_title")}>
          <DataTable
            caption={t("cr_outcomes_title")}
            rows={overview.outcomes}
            getKey={(o) => o.outcome_id}
            cols={[
              { h: t("cr_col_outcome"), c: (o) => o.outcome_type },
              { h: t("cr_col_role"), c: (o) => `${o.role_title} — ${o.employer_name}` },
              { h: t("cr_col_date"), c: (o) => fmtDate(o.event_date) },
              { h: t("cr_col_verification"), c: (o) => <StatusBadge domain="career" code={o.verification_status} /> },
            ]}
          />
          <p className="mt-3 text-xs text-muted-foreground">{t("cr_outcomes_note")}</p>
        </Section>
      )}
    </>
  );
}

/** "Needs: opt in, reviewed CV, permission to share", each one a link to its step. */
function NeedsLine({ needs }: { needs: CareerStepKey[] }) {
  const t = useT();
  return (
    <p className="mb-3 rounded-lg border border-warning/40 bg-warning-soft px-3 py-2 text-sm" data-testid="apply-needs">
      <strong>{t("cr_needs")}</strong>{" "}
      {needs.map((key, index) => (
        <span key={key}>
          {index > 0 && ", "}
          <button type="button" className="underline underline-offset-2" onClick={() => goToStep(key)}>
            {t(NEEDS_WORD[key])}
          </button>
        </span>
      ))}
      . {t("cr_needs_apply")}
    </p>
  );
}

function Checklist({
  overview,
  onOptIn,
  optInBusy,
  onEdit,
  onConsent,
  consentBusy,
}: {
  overview: CareerOverview;
  onOptIn: () => void;
  optInBusy: boolean;
  onEdit: () => void;
  onConsent: (value: boolean) => Promise<unknown>;
  consentBusy: boolean;
}) {
  const t = useT();
  const { profile } = overview;
  const done = overview.steps.filter((s) => s.done).length;
  const next = overview.steps.find((s) => !s.done)?.key;

  const detail = (key: CareerStepKey, state?: string): string => {
    switch (key) {
      case "opt_in":
        return profile.opted_in
          ? t("cr_opt_in_done", { date: fmtDate(profile.opted_in_at), end: profile.support_end ? fmtDate(profile.support_end) : "—" })
          : t("cr_opt_in_hint");
      case "profile":
        return overview.steps.find((s) => s.key === "profile")?.done ? t("cr_profile_done") : t("cr_profile_hint");
      case "cv":
        return state === "reviewed"
          ? t("cr_cv_reviewed")
          : state === "waiting"
            ? t("cr_cv_waiting")
            : state === "changes"
              ? t("cr_cv_changes")
              : t("cr_cv_none");
      case "share":
        return profile.sharing_consent ? t("cr_share_done") : t("cr_share_hint");
    }
  };

  const action = (key: CareerStepKey, stepDone: boolean) => {
    if (key === "opt_in" && !stepDone)
      return (
        <Button size="sm" onClick={onOptIn} disabled={optInBusy}>
          {t("cr_opt_in_button")}
        </Button>
      );
    if (!profile.opted_in) return null;
    if (key === "profile")
      return (
        <Button size="sm" variant={stepDone ? "outline" : "default"} onClick={onEdit}>
          {t("cr_edit_profile")}
        </Button>
      );
    if (key === "cv" && !stepDone)
      return (
        <Button size="sm" variant="outline" onClick={() => document.getElementById("cv-file")?.focus()}>
          {t("cr_upload_cv_short")}
        </Button>
      );
    if (key === "share") {
      return profile.sharing_consent ? (
        <ConfirmDialog
          title={t("cr_consent_withdraw_title")}
          consequence={t("cr_consent_withdraw_consequence")}
          confirmLabel={t("cr_consent_withdraw")}
          cancelLabel={t("cancel")}
          destructive
          onConfirm={async () => void (await onConsent(false))}
        >
          <Button size="sm" variant="outline">
            {t("cr_consent_withdraw")}
          </Button>
        </ConfirmDialog>
      ) : (
        <Button size="sm" onClick={() => void onConsent(true)} disabled={consentBusy}>
          {t("cr_consent_give")}
        </Button>
      );
    }
    return null;
  };

  return (
    <Section
      title={t("cr_checklist_title")}
      actions={<span className="text-sm text-muted-foreground">{t("cr_checklist_count", { done, total: overview.steps.length })}</span>}
    >
      <ol className="divide-y">
        {overview.steps.map((step, index) => (
          <li
            key={step.key}
            id={`career-step-${step.key}`}
            tabIndex={-1}
            className="flex flex-wrap items-center gap-3 py-3 outline-none first:pt-0 last:pb-0 focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span
              aria-hidden
              className={cn(
                "grid size-7 shrink-0 place-items-center rounded-full border-2 text-xs font-semibold",
                step.done
                  ? "border-primary bg-primary text-primary-foreground"
                  : step.key === next
                    ? "border-primary text-primary"
                    : "border-border text-muted-foreground",
              )}
            >
              {step.done ? <Check className="size-4" /> : index + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">
                {t(STEP_TITLE[step.key])}
                <span className="sr-only"> ({step.done ? t("stepDone") : t("stepTodo")})</span>
              </p>
              <p className="text-xs text-muted-foreground">{detail(step.key, step.state)}</p>
            </div>
            <div className="shrink-0">{action(step.key, step.done)}</div>
          </li>
        ))}
      </ol>
    </Section>
  );
}

function CvSection({ overview }: { overview: CareerOverview }) {
  const t = useT();
  const [label, setLabel] = useState("");
  const file = useRef<HTMLInputElement>(null);
  const upload = useApiMutation((vars: { file: File; label: string }) => careerApi.uploadCv(vars.file, vars.label), {
    invalidate: KEY,
    success: (cv) => t("cr_cv_uploaded", { n: cv.version_no }),
    next: t("cr_cv_uploaded_next"),
    onSuccess: () => {
      setLabel("");
      if (file.current) file.current.value = "";
    },
  });
  return (
    <Section title={t("cr_cv_title")}>
      {overview.cvs.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("cr_cv_empty")}</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {overview.cvs.map((cv) => (
            <li key={cv.cv_id} className="flex flex-wrap items-center justify-between gap-2">
              <span>
                <button
                  className="underline-offset-2 hover:underline"
                  onClick={() => void careerApi.downloadCv(cv)}
                  aria-label={`${t("cr_download")}: ${cv.label}`}
                >
                  {cv.label}
                </button>{" "}
                <span className="text-xs text-muted-foreground">
                  v{cv.version_no} · {fmtDate(cv.uploaded_at)}
                </span>
                {cv.review_feedback && <span className="block text-xs">{t("cr_feedback", { text: cv.review_feedback })}</span>}
              </span>
              <StatusBadge domain="cv" code={cv.review_status} />
            </li>
          ))}
        </ul>
      )}
      <form
        className="mt-3 space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          const chosen = file.current?.files?.[0];
          if (chosen) upload.mutate({ file: chosen, label });
        }}
      >
        <Field label={t("cr_cv_file")} htmlFor="cv-file">
          <Input id="cv-file" ref={file} type="file" accept=".pdf,.doc,.docx" />
        </Field>
        <Field label={t("cr_cv_label")} htmlFor="cv-label">
          <Input id="cv-label" value={label} onChange={(e) => setLabel(e.target.value)} placeholder={t("cr_cv_label_example")} />
        </Field>
        <Button type="submit" disabled={upload.isPending}>
          {t("cr_cv_upload")}
        </Button>
      </form>
    </Section>
  );
}

type ProfileForm = {
  preferred_roles: string;
  preferred_locations: string;
  skills: string;
  work_mode: string;
  qualification: string;
  graduation_year: string;
  experience_level: string;
  portfolio_url: string;
  availability: string;
};

function ProfileEditor({ profile, open, onOpenChange }: { profile: CareerProfile; open: boolean; onOpenChange: (open: boolean) => void }) {
  const t = useT();
  const form = useForm<ProfileForm>({
    values: {
      preferred_roles: profile.preferred_roles.join(", "),
      preferred_locations: profile.preferred_locations.join(", "),
      skills: profile.skills.map((s) => s.name).join(", "),
      work_mode: profile.work_mode ?? "",
      qualification: profile.qualification ?? "",
      graduation_year: profile.graduation_year?.toString() ?? "",
      experience_level: profile.experience_level ?? "",
      portfolio_url: profile.portfolio_url ?? "",
      availability: profile.availability ?? "",
    },
  });
  const save = useApiMutation(
    (values: ProfileForm) => {
      const body: ProfileUpdate = {
        preferred_roles: list(values.preferred_roles),
        preferred_locations: list(values.preferred_locations),
        skills: list(values.skills),
        work_mode: values.work_mode || null,
        qualification: values.qualification || null,
        graduation_year: values.graduation_year ? Number(values.graduation_year) : null,
        experience_level: values.experience_level || null,
        portfolio_url: values.portfolio_url || null,
        availability: values.availability || null,
      };
      return careerApi.updateProfile(body);
    },
    {
      invalidate: KEY,
      success: t("cr_profile_saved"),
      silentValidation: true,
      onSuccess: () => onOpenChange(false),
      onError: (error) => applyServerErrors(form, error),
    },
  );
  const errors = form.formState.errors;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <form className="space-y-3" noValidate onSubmit={form.handleSubmit((values) => save.mutate(values))}>
          <DialogHeader>
            <DialogTitle>{t("cr_profile_title")}</DialogTitle>
            <DialogDescription>{t("cr_profile_help")}</DialogDescription>
          </DialogHeader>
          <Field label={t("cr_k_roles")} htmlFor="cp-roles" error={errors.preferred_roles?.message}>
            <Input id="cp-roles" {...form.register("preferred_roles")} />
          </Field>
          <Field label={t("cr_k_locations")} htmlFor="cp-locations" error={errors.preferred_locations?.message}>
            <Input id="cp-locations" {...form.register("preferred_locations")} />
          </Field>
          <Field label={t("cr_k_skills")} htmlFor="cp-skills" error={errors.skills?.message}>
            <Input id="cp-skills" {...form.register("skills")} />
          </Field>
          <Field label={t("cr_f_work_mode")} htmlFor="cp-mode" error={errors.work_mode?.message}>
            <NativeSelect
              id="cp-mode"
              placeholder={t("cr_not_set")}
              {...form.register("work_mode")}
              options={WORK_MODES.map((v) => ({ value: v, label: t(WORK_MODE_KEY[v]) }))}
            />
          </Field>
          <Field label={t("cr_f_qualification")} htmlFor="cp-qualification" error={errors.qualification?.message}>
            <Input id="cp-qualification" {...form.register("qualification")} />
          </Field>
          <Field label={t("cr_f_year")} htmlFor="cp-year" error={errors.graduation_year?.message}>
            <Input id="cp-year" inputMode="numeric" {...form.register("graduation_year")} />
          </Field>
          <Field label={t("cr_f_level")} htmlFor="cp-level" error={errors.experience_level?.message}>
            <NativeSelect
              id="cp-level"
              placeholder={t("cr_not_set")}
              {...form.register("experience_level")}
              options={LEVELS.map((v) => ({ value: v, label: t(v === "Fresher" ? "cr_level_fresher" : "cr_level_experienced") }))}
            />
          </Field>
          <Field label={t("cr_f_portfolio")} htmlFor="cp-portfolio" error={errors.portfolio_url?.message}>
            <Input id="cp-portfolio" placeholder="https://" {...form.register("portfolio_url")} />
          </Field>
          <Field label={t("cr_f_availability")} htmlFor="cp-availability" error={errors.availability?.message}>
            <Input id="cp-availability" {...form.register("availability")} />
          </Field>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t("cancel")}
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {t("cr_profile_save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
