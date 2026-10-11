/** One support request for the student: who is handling it, the conversation ("You" for the student's own lines), a reply box and what to do once it is resolved. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getRouteApi } from "@tanstack/react-router";
import { supportApi, type SupportDetail, type SupportMessage } from "@/api/support";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { KeyValue, PageHead, QueryView, Section, StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { AttachmentLinks, FilePicker } from "@/features/shared/support-attachments";
import { fmtDateTime } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { CATEGORY_KEY, attachText } from "./support";

const routeApi = getRouteApi("/support/$requestId");

export function SupportRequestPage() {
  const t = useT();
  const { requestId } = routeApi.useParams();
  const id = Number(requestId);
  // New replies show up without a reload
  const query = useQuery({ queryKey: ["support", "detail", id], queryFn: () => supportApi.get(id), refetchInterval: 30_000 });
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <QueryView query={query} skeleton="detail">
        {(request) => (
          <>
            <Breadcrumbs items={[{ label: t("support"), to: "/support" }, { label: request.request_code }]} />
            <PageHead title={request.subject} description={`${request.request_code} · ${t(CATEGORY_KEY[request.category])}`} />
            <RequestBody request={request} />
          </>
        )}
      </QueryView>
    </div>
  );
}

function RequestBody({ request }: { request: SupportDetail }) {
  const t = useT();
  const id = request.support_request_id;
  const finished = request.status === "Resolved" || request.status === "Closed";
  const needsReply = request.status === "Waiting on Student";
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const refresh = { invalidate: [["support"], ["nav"]] };

  const reply = useApiMutation((vars: { body: string; files: File[] }) => supportApi.message(id, vars.body, false, vars.files), {
    ...refresh,
    success: t("sp_reply_sent"),
    next: t("sp_reply_sent_next"),
    onSuccess: () => {
      setText("");
      setFiles([]);
    },
  });
  const close = useApiMutation(() => supportApi.close(id), { ...refresh, success: t("sp_closed_toast") });
  const reopen = useApiMutation((reason: string) => supportApi.reopen(id, reason), {
    ...refresh,
    success: t("sp_reopened_toast"),
    next: t("sp_reopened_next"),
  });

  return (
    <>
      {needsReply && <StatusNote tone="warning">{t("sp_waiting_banner")}</StatusNote>}
      {request.status === "Resolved" && (
        <StatusNote tone="success" title={`${t("sp_resolved")}`}>
          {request.resolution_note} {t("sp_resolved_next")}
        </StatusNote>
      )}
      <Section>
        <KeyValue
          items={[
            [
              t("sp_k_status"),
              <span className="flex flex-wrap gap-1.5">
                <StatusBadge domain="support" code={request.status} />
                {request.sla_breached && <Tag tone="danger">{t("sp_reply_overdue")}</Tag>}
              </span>,
            ],
            [t("sp_k_handled_by"), request.owner.label],
            [t("sp_k_raised"), fmtDateTime(request.created_at)],
            ...(finished ? [] : ([[t("sp_k_reply_by"), fmtDateTime(request.sla_due_at)]] as [string, string][])),
          ]}
        />
      </Section>

      <Section title={t("sp_conversation")}>
        <ol className="space-y-3" aria-label={t("sp_conversation")}>
          {request.messages.map((m) => (
            <Message key={m.support_message_id} message={m} />
          ))}
        </ol>
      </Section>

      {!finished && (
        <Section title={t("sp_reply")}>
          <div className="space-y-2">
            <Label htmlFor="support-reply" className="sr-only">
              {t("sp_reply")}
            </Label>
            <Textarea id="support-reply" rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder={t("sp_reply_placeholder")} />
            <FilePicker files={files} onChange={setFiles} inputId="support-reply-files" text={attachText(t)} />
            <Button disabled={!text.trim() || reply.isPending} onClick={() => reply.mutate({ body: text.trim(), files })}>
              {t("sp_send_reply")}
            </Button>
          </div>
        </Section>
      )}

      {request.status === "Resolved" && (
        <Section title={t("sp_is_it_fixed")}>
          <p className="mb-3 text-sm text-muted-foreground">{t("sp_is_it_fixed_help")}</p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => close.mutate(undefined)} disabled={close.isPending}>
              {t("sp_confirm_close")}
            </Button>
            <ReopenDialog busy={reopen.isPending} onSubmit={(reason) => reopen.mutateAsync(reason)} />
          </div>
        </Section>
      )}
      {request.status === "Closed" && (
        <Section>
          <p className="mb-3 text-sm text-muted-foreground">{t("sp_closed_help")}</p>
          <ReopenDialog busy={reopen.isPending} onSubmit={(reason) => reopen.mutateAsync(reason)} />
        </Section>
      )}
    </>
  );
}

/** One line of the conversation. The student's own lines say "You" and sit on the right; history lines (status changes) are small. */
function Message({ message }: { message: SupportMessage }) {
  const t = useT();
  if (message.kind !== "Message")
    return (
      <li className="text-center text-xs text-muted-foreground">
        {message.body} · {fmtDateTime(message.created_at)}
      </li>
    );
  const mine = message.from_student;
  return (
    <li className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-[90%] rounded-2xl border px-3.5 py-2.5 text-sm", mine ? "rounded-br-sm bg-primary/10" : "rounded-bl-sm bg-card")}>
        <p className="mb-0.5 text-xs text-muted-foreground">
          <strong className="font-semibold text-foreground">{mine ? t("sp_you") : message.author.full_name}</strong> · {fmtDateTime(message.created_at)}
        </p>
        <p className="whitespace-pre-wrap break-words">{message.body}</p>
        <AttachmentLinks attachments={message.attachments} downloadLabel={t("sp_download")} />
      </div>
    </li>
  );
}

function ReopenDialog({ busy, onSubmit }: { busy: boolean; onSubmit: (reason: string) => Promise<unknown> }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const submit = async () => {
    try {
      await onSubmit(reason.trim());
      setOpen(false);
      setReason("");
    } catch {
      /* the mutation already showed the error; keep the dialog open */
    }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">{t("sp_reopen")}</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("sp_reopen_title")}</DialogTitle>
          <DialogDescription>{t("sp_reopen_help")}</DialogDescription>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="support-reopen-reason">{t("sp_reopen_reason")}</Label>
          <Textarea id="support-reopen-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
          {reason.trim().length < 3 && <p className="text-xs text-muted-foreground">{t("sp_reopen_min")}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            {t("cancel")}
          </Button>
          <Button disabled={busy || reason.trim().length < 3} onClick={() => void submit()}>
            {t("sp_reopen")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
