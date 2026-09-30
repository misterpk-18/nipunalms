import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { careerApi, type CareerOverview, type CareerProfile, type ProfileUpdate } from "@/api/career";
import { Field, NativeSelect, applyServerErrors } from "@/components/lms/forms";
import { ConfirmAction, DataTable, KeyValue, Note, PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { formatDate, formatIst } from "@/features/shared/ist";
import { useApiMutation } from "@/lib/mutation";
import { useT } from "@/lib/i18n";

const KEY = [["career"]];
const list = (text: string) =>
  text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

export function Career() {
  const t = useT();
  const query = useQuery({ queryKey: ["career", "me"], queryFn: careerApi.overview });
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead title={t("careerSupport")} description="Source: placement records (verified outcomes)" />
      <QueryView query={query}>{(overview) => <CareerBody overview={overview} />}</QueryView>
    </div>
  );
}

function CareerBody({ overview }: { overview: CareerOverview }) {
  const t = useT();
  const { profile } = overview;
  const optIn = useApiMutation(() => careerApi.updateProfile({ opted_in: true }), { invalidate: KEY, success: "You have opted in to career support" });
  const consent = useApiMutation((value: boolean) => careerApi.setConsent(value), {
    invalidate: KEY,
    success: (o) => (o.profile.sharing_consent ? "Employer sharing consent given" : "Employer sharing consent withdrawn"),
  });
  const apply = useApiMutation((id: number) => careerApi.apply(id), { invalidate: KEY, success: "Application recorded" });
  const withdraw = useApiMutation((id: number) => careerApi.withdraw(id), { invalidate: KEY, success: "Application withdrawn" });

  return (
    <>
      <p role="note" className="rounded-lg border-2 border-warning bg-warning-soft p-3 font-semibold text-warning">
        {t("noGuarantee")}
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Career Profile" actions={profile.opted_in && <ProfileEditor profile={profile} />}>
          {!profile.opted_in ? (
            <div className="space-y-3">
              <p className="text-sm">
                Opt in to prepare your profile and CV and see approved opportunities. Opting in is your choice and is separate from sharing your details with an
                employer.
              </p>
              <Button onClick={() => optIn.mutate()} disabled={optIn.isPending}>
                Opt in to career support
              </Button>
            </div>
          ) : (
            <>
              <KeyValue
                items={[
                  ["Opt-in", <StatusBadge tone="success">Opted in — {formatDate(profile.opted_in_at)}</StatusBadge>],
                  ["Support period", profile.support_end ? `Until ${formatDate(profile.support_end)}` : "—"],
                  ["Preferred roles", profile.preferred_roles.join(", ") || "—"],
                  ["Preferred locations", profile.preferred_locations.join(", ") || "—"],
                  [
                    "Skills",
                    profile.skills.length ? (
                      <span className="flex flex-wrap gap-1">
                        {profile.skills.map((s) => (
                          <StatusBadge key={s.name} tone={s.confidence === "Verified" ? "success" : "neutral"}>
                            {s.name} · {s.confidence}
                          </StatusBadge>
                        ))}
                      </span>
                    ) : (
                      "—"
                    ),
                  ],
                  ["Referral readiness", <StatusBadge>{profile.readiness}</StatusBadge>],
                  [
                    "Consent for employer referral",
                    <StatusBadge tone={profile.sharing_consent ? "success" : "warning"}>
                      {profile.sharing_consent ? "Active — renewable" : "Not given"}
                    </StatusBadge>,
                  ],
                  [
                    "Profile completeness",
                    `${profile.completeness.percent}%${profile.completeness.missing.length ? ` — add: ${profile.completeness.missing.slice(0, 2).join(", ")}` : ""}`,
                  ],
                ]}
              />
              <div className="mt-3 flex flex-wrap gap-2">
                {profile.sharing_consent ? (
                  <ConfirmAction
                    title="Withdraw consent?"
                    description="Withdrawing stops future sharing of your profile with employers. Applications already sent stay on record."
                    confirmLabel="Withdraw consent"
                    destructive
                    onConfirm={async () => void (await consent.mutateAsync(false))}
                  >
                    <Button variant="outline">Withdraw consent</Button>
                  </ConfirmAction>
                ) : (
                  <Button onClick={() => consent.mutate(true)} disabled={consent.isPending}>
                    Give consent to share with employers
                  </Button>
                )}
              </div>
            </>
          )}
        </Section>
        <CvSection overview={overview} />
      </div>

      <Section title="Approved Job Opportunities">
        {!profile.opted_in ? (
          <p className="text-sm">Opt in to see the approved opportunities that match your courses and branch.</p>
        ) : overview.opportunities.length === 0 ? (
          <p className="text-sm">No approved opportunities match your profile right now.</p>
        ) : (
          <>
            <p className="mb-3 text-sm">
              {overview.opportunities.length} verified {overview.opportunities.length === 1 ? "opportunity matches" : "opportunities match"} your profile.
              Applying needs your consent, a reviewed CV and an opt-in.
            </p>
            <ul className="grid gap-3 md:grid-cols-2">
              {overview.opportunities.map((o) => (
                <li key={o.opportunity_id} className="rounded-lg border p-3 text-sm">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold">{o.title}</p>
                      <p>{o.employer_name}</p>
                    </div>
                    <StatusBadge tone="success">Verified</StatusBadge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {o.employment_type} · {o.work_mode}
                    {o.location ? ` · ${o.location}` : ""} · {o.compensation_text}
                    {o.closing_date ? ` · closes ${formatDate(o.closing_date)}` : ""}
                  </p>
                  {o.required_skills.length > 0 && <p className="mt-1 text-xs">Skills: {o.required_skills.join(", ")}</p>}
                  <div className="mt-2">
                    {o.applied ? (
                      <StatusBadge tone="info">Applied</StatusBadge>
                    ) : (
                      <Button size="sm" onClick={() => apply.mutate(o.opportunity_id)} disabled={apply.isPending} aria-label={`Apply for ${o.title}`}>
                        Apply
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </Section>

      <h2 className="text-lg font-semibold">My Applications, interviews &amp; offers</h2>
      <DataTable
        caption="Applications"
        rows={overview.applications}
        getKey={(a) => a.application_id}
        empty="You have not applied to any opportunity yet."
        cols={[
          { h: "Role", c: (a) => a.opportunity.title },
          { h: "Employer", c: (a) => a.opportunity.employer_name },
          {
            h: "Interview round",
            c: (a) => (a.interview_round ? `${a.interview_round}${a.interview_at ? ` — ${formatIst(a.interview_at)}` : ""}` : (a.status_note ?? "—")),
          },
          { h: "State", c: (a) => <StatusBadge>{a.status}</StatusBadge> },
          {
            h: "Action",
            c: (a) =>
              a.closed ? (
                "—"
              ) : (
                <ConfirmAction
                  title="Withdraw this application?"
                  confirmLabel="Withdraw"
                  destructive
                  onConfirm={async () => void (await withdraw.mutateAsync(a.application_id))}
                >
                  <Button size="sm" variant="outline" aria-label={`Withdraw ${a.opportunity.title}`}>
                    Withdraw
                  </Button>
                </ConfirmAction>
              ),
          },
        ]}
      />
      {overview.outcomes.length > 0 && (
        <Section title="Offers & joining recorded by Placement">
          <DataTable
            caption="Placement outcomes"
            rows={overview.outcomes}
            getKey={(o) => o.outcome_id}
            cols={[
              { h: "Outcome", c: (o) => o.outcome_type },
              { h: "Role", c: (o) => `${o.role_title} — ${o.employer_name}` },
              { h: "Date", c: (o) => formatDate(o.event_date) },
              {
                h: "Verification",
                c: (o) => <StatusBadge>{o.verification_status === "Pending Verification" ? "Confirmation Pending" : o.verification_status}</StatusBadge>,
              },
            ]}
          />
        </Section>
      )}
      <Section title="Next action">
        <p className="text-sm">{overview.next_action}</p>
      </Section>
      <Note>Verified outcomes (offers, joining) come only from Placement records.</Note>
    </>
  );
}

function CvSection({ overview }: { overview: CareerOverview }) {
  const [label, setLabel] = useState("");
  const file = useRef<HTMLInputElement>(null);
  const upload = useApiMutation((vars: { file: File; label: string }) => careerApi.uploadCv(vars.file, vars.label), {
    invalidate: KEY,
    success: (cv) => `CV v${cv.version_no} uploaded for review`,
    onSuccess: () => {
      setLabel("");
      if (file.current) file.current.value = "";
    },
  });
  const disabled = !overview.profile.opted_in;
  return (
    <Section title="CV versions">
      {overview.cvs.length === 0 ? (
        <p className="text-sm">No CV uploaded yet.</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {overview.cvs.map((cv) => (
            <li key={cv.cv_id} className="flex flex-wrap items-center justify-between gap-2">
              <span>
                <button className="underline-offset-2 hover:underline" onClick={() => void careerApi.downloadCv(cv)} aria-label={`Download ${cv.label}`}>
                  {cv.label}
                </button>{" "}
                <span className="text-xs text-muted-foreground">
                  v{cv.version_no} · {formatDate(cv.uploaded_at)}
                </span>
                {cv.review_feedback && <span className="block text-xs">Feedback: {cv.review_feedback}</span>}
              </span>
              <StatusBadge>{cv.review_status}</StatusBadge>
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
        <Field label="CV file (PDF, DOC or DOCX, up to 5 MB)" htmlFor="cv-file">
          <Input id="cv-file" ref={file} type="file" accept=".pdf,.doc,.docx" disabled={disabled} />
        </Field>
        <Field label="Label (optional)" htmlFor="cv-label">
          <Input id="cv-label" value={label} onChange={(e) => setLabel(e.target.value)} disabled={disabled} placeholder="e.g. CV — Data roles" />
        </Field>
        <Button type="submit" disabled={disabled || upload.isPending}>
          Upload new CV
        </Button>
        {disabled && <p className="text-xs text-muted-foreground">Opt in to career support to upload a CV.</p>}
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

function ProfileEditor({ profile }: { profile: CareerProfile }) {
  const [open, setOpen] = useState(false);
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
      success: "Career profile saved",
      silentValidation: true,
      onSuccess: () => setOpen(false),
      onError: (error) => applyServerErrors(form, error),
    },
  );
  const errors = form.formState.errors;

  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        Edit profile
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <form className="space-y-3" noValidate onSubmit={form.handleSubmit((values) => save.mutate(values))}>
            <DialogHeader>
              <DialogTitle>Career profile</DialogTitle>
              <DialogDescription>Separate lists with commas. Skills you add are shown as Student Reported until staff verify them.</DialogDescription>
            </DialogHeader>
            <Field label="Preferred roles" htmlFor="cp-roles" error={errors.preferred_roles?.message}>
              <Input id="cp-roles" {...form.register("preferred_roles")} />
            </Field>
            <Field label="Preferred locations" htmlFor="cp-locations" error={errors.preferred_locations?.message}>
              <Input id="cp-locations" {...form.register("preferred_locations")} />
            </Field>
            <Field label="Skills" htmlFor="cp-skills" error={errors.skills?.message}>
              <Input id="cp-skills" {...form.register("skills")} />
            </Field>
            <Field label="Work mode" htmlFor="cp-mode" error={errors.work_mode?.message}>
              <NativeSelect
                id="cp-mode"
                placeholder="Not set"
                {...form.register("work_mode")}
                options={["On-site", "Remote", "Hybrid", "Any"].map((v) => ({ value: v, label: v }))}
              />
            </Field>
            <Field label="Qualification" htmlFor="cp-qualification" error={errors.qualification?.message}>
              <Input id="cp-qualification" {...form.register("qualification")} />
            </Field>
            <Field label="Graduation year" htmlFor="cp-year" error={errors.graduation_year?.message}>
              <Input id="cp-year" inputMode="numeric" {...form.register("graduation_year")} />
            </Field>
            <Field label="Fresher or experienced" htmlFor="cp-level" error={errors.experience_level?.message}>
              <NativeSelect
                id="cp-level"
                placeholder="Not set"
                {...form.register("experience_level")}
                options={["Fresher", "Experienced"].map((v) => ({ value: v, label: v }))}
              />
            </Field>
            <Field label="Portfolio or project link" htmlFor="cp-portfolio" error={errors.portfolio_url?.message}>
              <Input id="cp-portfolio" placeholder="https://" {...form.register("portfolio_url")} />
            </Field>
            <Field label="Availability" htmlFor="cp-availability" error={errors.availability?.message}>
              <Input id="cp-availability" {...form.register("availability")} />
            </Field>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={save.isPending}>
                Save profile
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
