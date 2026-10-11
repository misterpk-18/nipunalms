/** Support: requests waiting on the student come first, a guided form raises a new one, and the new request opens straight away. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, getRouteApi, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { LifeBuoy, Plus } from "lucide-react";
import { SUPPORT_CATEGORIES, supportApi, type SupportCategory, type SupportSummary } from "@/api/support";
import { EmptyState } from "@/components/lms/empty-state";
import { Field, NativeSelect, applyServerErrors } from "@/components/lms/forms";
import { LoadingSkeleton, PageHead, StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { FilePicker } from "@/features/shared/support-attachments";
import { fmtDate } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { useT, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const routeApi = getRouteApi("/support/");

export const CATEGORY_KEY: Record<SupportCategory, TranslationKey> = {
  Academic: "sp_cat_academic",
  LMS: "sp_cat_lms",
  Account: "sp_cat_account",
  "Recording access": "sp_cat_recording",
  "Device access": "sp_cat_device",
  Other: "sp_cat_other",
};
/** What each kind of request is for and who answers it: shown under the category so the student picks the right one. */
const CATEGORY_HELP: Record<SupportCategory, TranslationKey> = {
  Academic: "sp_help_academic",
  LMS: "sp_help_lms",
  Account: "sp_help_account",
  "Recording access": "sp_help_recording",
  "Device access": "sp_help_device",
  Other: "sp_help_other",
};

export function Support() {
  const t = useT();
  const search = routeApi.useSearch();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["support", "list", { page }], queryFn: () => supportApi.list({ page }) });
  const waiting = (query.data?.data ?? []).filter((r) => r.status === "Waiting on Student").length;
  const open = search.new === 1;
  const setOpen = (next: boolean) => void navigate({ to: "/support", search: next ? { new: 1 } : {}, replace: true });

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <PageHead
        title={t("support")}
        description={t("sp_desc")}
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus aria-hidden /> {t("sp_new")}
          </Button>
        }
      />
      {waiting > 0 && <StatusNote tone="warning">{t(waiting === 1 ? "sp_waiting_one" : "sp_waiting_many", { count: waiting })}</StatusNote>}
      {query.isPending ? (
        <LoadingSkeleton kind="cards" />
      ) : query.isError ? (
        <StatusNote tone="danger">{t("sp_load_error")}</StatusNote>
      ) : query.data.data.length === 0 ? (
        <EmptyState
          icon={LifeBuoy}
          reason={t("sp_none")}
          action={
            <Button onClick={() => setOpen(true)}>
              <Plus aria-hidden /> {t("sp_new")}
            </Button>
          }
        />
      ) : (
        <>
          <ul className="space-y-3" aria-label={t("sp_your_requests")}>
            {query.data.data.map((request) => (
              <RequestRow key={request.support_request_id} request={request} />
            ))}
          </ul>
          {query.data.meta.pages > 1 && (
            <div className="flex items-center justify-end gap-2 text-sm">
              <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                {t("sp_previous")}
              </Button>
              <span>{t("sp_page", { page: query.data.meta.page, pages: query.data.meta.pages })}</span>
              <Button size="sm" variant="outline" disabled={page >= query.data.meta.pages} onClick={() => setPage(page + 1)}>
                {t("sp_next")}
              </Button>
            </div>
          )}
        </>
      )}
      {open && <NewRequest onClose={() => setOpen(false)} />}
    </div>
  );
}

function RequestRow({ request }: { request: SupportSummary }) {
  const t = useT();
  const needsReply = request.status === "Waiting on Student";
  const finished = request.status === "Resolved" || request.status === "Closed";
  return (
    <li>
      <Link
        to="/support/$requestId"
        params={{ requestId: String(request.support_request_id) }}
        className={cn(
          "tap block rounded-xl border bg-card p-4 shadow-sm hover:bg-accent/40",
          needsReply && "border-warning bg-warning-soft/40",
          finished && "text-muted-foreground",
        )}
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="font-semibold text-foreground">{request.subject}</p>
            <p className="text-xs">
              <span className="font-mono">{request.request_code}</span> · {t(CATEGORY_KEY[request.category])} · {fmtDate(request.created_at)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {needsReply && <Tag tone="warning">{t("sp_needs_reply")}</Tag>}
            <StatusBadge domain="support" code={request.status} />
            {request.sla_breached && <Tag tone="danger">{t("sp_reply_overdue")}</Tag>}
          </div>
        </div>
        <p className="mt-2 text-xs">{t("sp_handled_by", { owner: request.owner.label })}</p>
      </Link>
    </li>
  );
}

type Values = { category: SupportCategory | ""; subject: string; details: string };

/** The guided form: a subject, a kind of request (with what it is for), what happened, and files that show it. */
function NewRequest({ onClose }: { onClose: () => void }) {
  const t = useT();
  const navigate = useNavigate();
  const search = routeApi.useSearch();
  const [files, setFiles] = useState<File[]>([]);
  const form = useForm<Values>({ defaultValues: { category: search.category ?? "", subject: search.subject ?? "", details: search.details ?? "" } });
  const category = form.watch("category");
  const errors = form.formState.errors;
  const raise = useApiMutation(
    (values: Values) =>
      supportApi.raise({ category: values.category as SupportCategory, subject: values.subject.trim(), details: values.details.trim() }, files),
    {
      success: (request) => t("sp_raised", { code: request.request_code }),
      next: (request) => t("sp_raised_next", { owner: request.owner.label }),
      invalidate: [["support"], ["nav"]],
      silentValidation: true,
      onSuccess: (request) => void navigate({ to: "/support/$requestId", params: { requestId: String(request.support_request_id) } }),
      onError: (error) => applyServerErrors(form, error),
    },
  );

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <form className="space-y-4" noValidate onSubmit={form.handleSubmit((values) => raise.mutate(values))}>
          <DialogHeader>
            <DialogTitle>{t("raiseRequest")}</DialogTitle>
            <DialogDescription>{t("sp_form_intro")}</DialogDescription>
          </DialogHeader>
          <Field
            label={t("sp_f_category")}
            htmlFor="support-new-category"
            error={errors.category?.message}
            hint={category ? t(CATEGORY_HELP[category]) : t("sp_f_category_hint")}
          >
            <NativeSelect
              id="support-new-category"
              placeholder={t("sp_choose")}
              {...form.register("category", { required: t("requiredField") })}
              options={SUPPORT_CATEGORIES.map((c) => ({ value: c, label: t(CATEGORY_KEY[c]) }))}
            />
          </Field>
          <Field label={t("sp_f_subject")} htmlFor="support-new-subject" error={errors.subject?.message} hint={t("sp_f_subject_hint")}>
            <Input
              id="support-new-subject"
              maxLength={200}
              {...form.register("subject", { required: t("requiredField"), minLength: { value: 3, message: t("requiredField") } })}
            />
          </Field>
          <Field label={t("sp_f_details")} htmlFor="support-new-details" error={errors.details?.message} hint={t("sp_f_details_hint")}>
            <Textarea
              id="support-new-details"
              rows={4}
              {...form.register("details", { required: t("requiredField"), minLength: { value: 3, message: t("requiredField") } })}
            />
          </Field>
          <div className="space-y-1.5">
            <p className="text-sm font-medium">{t("sp_f_files")}</p>
            <FilePicker files={files} onChange={setFiles} inputId="support-new-files" text={attachText(t)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              {t("cancel")}
            </Button>
            <Button type="submit" disabled={raise.isPending}>
              {t("submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** The picker's words in the reader's language. */
export function attachText(t: ReturnType<typeof useT>) {
  return {
    add: t("sp_attach_add"),
    hint: t("sp_attach_hint"),
    tooBig: (name: string) => t("sp_attach_too_big", { name }),
    wrongType: (name: string) => t("sp_attach_wrong_type", { name }),
    tooMany: t("sp_attach_too_many"),
    remove: (name: string) => t("sp_attach_remove", { name }),
  };
}
