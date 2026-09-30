import { useForm } from "react-hook-form";
import { SUPPORT_CATEGORIES, supportApi, type SupportCategory } from "@/api/support";
import { Field, NativeSelect, applyServerErrors } from "@/components/lms/forms";
import { PageHead, Section } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";
import { useLanguage, useT } from "@/lib/i18n";
import { SupportDesk } from "@/features/shared/support-desk";

type Values = { category: SupportCategory | ""; details: string };

const CATEGORY_TE: Record<SupportCategory, string> = {
  Academic: "విద్యా సంబంధిత",
  LMS: "LMS",
  Account: "ఖాతా",
  "Recording access": "రికార్డింగ్ యాక్సెస్",
  "Device access": "పరికర యాక్సెస్",
  Other: "ఇతర",
};

export function Support() {
  const t = useT();
  const { lang } = useLanguage();
  const te = lang === "te";
  const form = useForm<Values>({ defaultValues: { category: "", details: "" } });
  const raise = useApiMutation((values: Values) => supportApi.raise({ category: values.category as SupportCategory, details: values.details }), {
    success: (request) => `Request ${request.request_code} raised. Owner: ${request.owner.label}`,
    invalidate: [["support"]],
    silentValidation: true,
    onSuccess: () => form.reset(),
    onError: (error) => applyServerErrors(form, error),
  });

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead
        title={t("support")}
        description={
          te ? "విద్యా, LMS మరియు ఖాతా అభ్యర్థనలు — ప్రతిదానికి పేరున్న యజమాని ఉంటారు." : "Academic, LMS and account requests, each with a named owner."
        }
      />
      <Section title={t("raiseRequest")}>
        <form className="space-y-3" noValidate onSubmit={form.handleSubmit((values) => raise.mutate(values))}>
          <Field label={te ? "వర్గం" : "Category"} htmlFor="support-new-category" error={form.formState.errors.category?.message}>
            <NativeSelect
              id="support-new-category"
              placeholder={te ? "ఎంచుకోండి" : "Choose"}
              {...form.register("category", { required: t("requiredField") })}
              options={SUPPORT_CATEGORIES.map((c) => ({ value: c, label: te ? CATEGORY_TE[c] : c }))}
            />
          </Field>
          <Field label={te ? "వివరాలు" : "Details"} htmlFor="support-new-details" error={form.formState.errors.details?.message}>
            <Textarea
              id="support-new-details"
              rows={3}
              {...form.register("details", { required: t("requiredField"), minLength: { value: 3, message: t("requiredField") } })}
            />
          </Field>
          <Button type="submit" disabled={raise.isPending}>
            {t("submit")}
          </Button>
        </form>
      </Section>
      <Section title={te ? "నా అభ్యర్థనలు" : "My requests"}>
        <SupportDesk mode="student" caption="My requests" empty={te ? "ఇంకా అభ్యర్థనలు లేవు." : "You have not raised any requests yet."} />
      </Section>
    </div>
  );
}
