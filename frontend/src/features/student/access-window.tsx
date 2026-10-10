/** What a student may use and until when: one line per course ("Available until 12 Jan 2027 · Request extension"), the extension dialog, and the rules. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { contentApi, formatDate, type AccessOverview, type AccessState } from "@/api/content";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { QueryView, Tag } from "@/components/lms/ui";
import { Field, NativeSelect } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";
import { useT } from "@/lib/i18n";

const SCOPES = ["Both", "Recording", "Material"] as const;
type T = ReturnType<typeof useT>;

function accessLine(state: AccessState, t: T): string {
  if (state.state === "Pending") return t("accessPending");
  const text = state.state === "Expired" ? t("accessEnded", { date: formatDate(state.expiry) }) : t("accessAvailable", { date: formatDate(state.expiry) });
  return state.extended ? `${text} (${t("accessExtended")})` : text;
}

/** The access line of each course for one tab: recordings or files. The extension dialog opens from the "Request extension" button. */
export function AccessLines({ focus }: { focus: "Recording" | "Material" }) {
  const t = useT();
  const query = useQuery({ queryKey: ["me", "access"], queryFn: contentApi.access });
  const [requesting, setRequesting] = useState<AccessOverview | null>(null);
  const rows = query.data ?? [];
  return (
    <>
      {query.isPending && <Skeleton className="mb-4 h-10 rounded-lg" />}
      {query.isError && (
        <div className="mb-4">
          <QueryView query={query}>{() => null}</QueryView>
        </div>
      )}
      {rows.length > 0 && (
        <ul className="mb-4 space-y-2">
          {rows.map((row) => {
            const state = focus === "Recording" ? row.recording : row.material;
            const pending = row.pending_requests[0];
            const canRequest = row.can_request.Recording || row.can_request.Material;
            return (
              <li key={row.enrolment.enrolment_id} className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border bg-card px-3 py-2 text-sm">
                <span className="font-medium">{row.enrolment.course.title}</span>
                <span className={state.state === "Expired" ? "text-destructive" : "text-muted-foreground"}>{accessLine(state, t)}</span>
                {pending && <Tag tone="warning">{t("extensionWaiting")}</Tag>}
                {canRequest ? (
                  <>
                    <span className="text-muted-foreground" aria-hidden>
                      ·
                    </span>
                    <Button variant="link" className="h-auto p-0" onClick={() => setRequesting(row)}>
                      {t("requestExtension")}
                    </Button>
                  </>
                ) : (
                  !pending && row.joining_date && <span className="text-xs text-muted-foreground">· {t("extensionUsed")}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {requesting && <ExtensionDialog row={requesting} onClose={() => setRequesting(null)} />}
    </>
  );
}

/** The policy behind the access lines, folded away. */
export function AccessRules() {
  const t = useT();
  return (
    <HowThisWorks title={t("howAccessWorks")}>
      <ul className="list-disc space-y-1 pl-5">
        {(["accessRule1", "accessRule2", "accessRule3", "accessRule4", "accessRule5"] as const).map((key) => (
          <li key={key}>{t(key)}</li>
        ))}
        <li>{t("recordingsPlayNote")}</li>
      </ul>
    </HowThisWorks>
  );
}

function ExtensionDialog({ row, onClose }: { row: AccessOverview; onClose: () => void }) {
  const t = useT();
  const allowed = SCOPES.filter((scope) => (scope === "Both" ? row.can_request.Recording && row.can_request.Material : row.can_request[scope]));
  const [scope, setScope] = useState<string>(allowed[0] ?? "Both");
  const [reason, setReason] = useState("");
  const labels: Record<string, string> = { Both: t("extBoth"), Recording: t("recordings"), Material: t("tabFiles") };
  const mutation = useApiMutation((body: { enrolment_id: number; scope: string; reason: string }) => contentApi.requestExtension(body), {
    success: t("extSent"),
    next: t("extSentNext"),
    invalidate: [["me", "access"]],
    onSuccess: onClose,
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("extTitle")}</DialogTitle>
          <DialogDescription>{t("extBody", { course: row.enrolment.course.title, date: formatDate(row.second_expiry) })}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Field label={t("extWhat")} htmlFor="ext-scope">
            <NativeSelect
              id="ext-scope"
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              options={allowed.map((s) => ({ value: s, label: labels[s] ?? s }))}
            />
          </Field>
          <Field label={t("extReason")} htmlFor="ext-reason">
            <Textarea id="ext-reason" value={reason} onChange={(e) => setReason(e.target.value)} rows={3} placeholder={t("extReasonHint")} />
          </Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t("cancel")}
          </Button>
          <Button
            disabled={!reason.trim() || mutation.isPending}
            onClick={() => mutation.mutate({ enrolment_id: row.enrolment.enrolment_id, scope, reason: reason.trim() })}
          >
            {t("sendRequest")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
