/** Certificates: one card per course with a three-step tracker, what the certificate is waiting for, and the PDF once it is issued. */
import { Link } from "@tanstack/react-router";
import { Check, Copy, Download } from "lucide-react";
import { toast } from "sonner";
import { certificatesApi, useMyCertificates, type CertificateCard, type CertificateStepState } from "@/api/certificates";
import { EmptyState } from "@/components/lms/empty-state";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, QueryView, StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { fmtDate } from "@/features/shared/format";
import { formatMoney } from "@/lib/format";
import { useT, type TranslationKey } from "@/lib/i18n";
import { useApiMutation } from "@/lib/mutation";
import { cn } from "@/lib/utils";

type T = ReturnType<typeof useT>;

const STEP_LABEL: Record<CertificateCard["steps"][number]["key"], TranslationKey> = { completed: "stepCompleted", review: "stepReview", issued: "stepIssued" };
const STATE_WORD: Record<CertificateStepState, TranslationKey> = { done: "stepDone", current: "stepCurrent", todo: "stepTodo" };

/** Course completed, Review, Issued: what is done, what is happening now, what is still to come. */
function Tracker({ steps }: { steps: CertificateCard["steps"] }) {
  const t = useT();
  return (
    <ol aria-label={t("certTracker")} className="flex items-start">
      {steps.map((step, index) => (
        <li key={step.key} className="relative flex flex-1 flex-col items-center gap-1 text-center">
          {index > 0 && <span aria-hidden className={cn("absolute right-1/2 top-3.5 h-0.5 w-full", step.state === "todo" ? "bg-border" : "bg-primary")} />}
          <span
            aria-hidden
            className={cn(
              "relative z-10 grid size-7 place-items-center rounded-full border-2 text-xs font-semibold",
              step.state === "done" && "border-primary bg-primary text-primary-foreground",
              step.state === "current" && "border-primary bg-background text-primary ring-4 ring-primary/20",
              step.state === "todo" && "border-border bg-background text-muted-foreground",
            )}
          >
            {step.state === "done" ? <Check className="size-4" /> : index + 1}
          </span>
          <span className={cn("text-xs", step.state === "todo" ? "text-muted-foreground" : "font-medium")}>
            {t(STEP_LABEL[step.key])}
            <span className="sr-only"> ({t(STATE_WORD[step.state])})</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

/** The blocker, in plain words. Returns null when there is nothing to wait for. */
function blockerText(card: CertificateCard, t: T): { text: string; tone: "info" | "warning" | "danger" } | null {
  const blocker = card.blocker;
  if (!blocker) return null;
  switch (blocker.code) {
    case "not_completed":
      return { text: t("certNotCompleted"), tone: "info" };
    case "in_review":
      return { text: t("certInReview"), tone: "info" };
    case "ready_to_issue":
      return { text: t("certReadyToIssue"), tone: "info" };
    case "fee_outstanding":
      return { text: t("certFeeOutstanding", { balance: formatMoney(blocker.params["balance"]) }), tone: "warning" };
    case "fee_unknown":
      return { text: t("certFeeUnknown"), tone: "warning" };
    case "revoked":
      return { text: blocker.params["reason"] ? t("certRevoked", { reason: blocker.params["reason"] }) : t("certRevokedNoReason"), tone: "danger" };
    case "internship_evidence":
      return { text: t("certInternship"), tone: "info" };
    case "config_pending":
      return { text: t("certConfigPending"), tone: "warning" };
  }
}

function IssuedActions({ card }: { card: CertificateCard }) {
  const t = useT();
  const certificate = card.certificate!;
  const filename = `${certificate.certificate_number}${certificate.version > 1 ? `-v${certificate.version}` : ""}.pdf`;
  const download = useApiMutation(() => certificatesApi.downloadPdf(certificate.certificate_id, filename), { success: t("pdfSaved") });

  async function copyLink() {
    const url = `${window.location.origin}${card.verify_path}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success(t("verifyLinkCopied"), { description: t("verifyLinkNext") });
    } catch {
      toast.message(url); // the browser refused the clipboard: show the link so it can be copied by hand
    }
  }

  return (
    <div className="space-y-3">
      <div className="space-y-0.5 text-sm">
        <p className="font-medium">{t("issuedOn", { date: fmtDate(certificate.issue_date) })}</p>
        <p className="text-muted-foreground">{t("certNumber", { number: certificate.certificate_number ?? "" })}</p>
        {certificate.version > 1 && <p className="text-muted-foreground">{t("certVersion", { n: certificate.version })}</p>}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button className="tap" disabled={download.isPending} onClick={() => download.mutate(undefined)}>
          <Download aria-hidden />
          {t("downloadPdf")}
        </Button>
        <Button variant="outline" className="tap" onClick={() => void copyLink()}>
          <Copy aria-hidden />
          {t("copyVerifyLink")}
        </Button>
      </div>
    </div>
  );
}

function Card({ card }: { card: CertificateCard }) {
  const t = useT();
  const blocker = blockerText(card, t);
  return (
    <li className="flex flex-col gap-4 rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="font-semibold leading-snug">{card.course.title}</h2>
          <p className="text-xs text-muted-foreground">
            {card.certificate_type === "Internship Certificate" ? t("certTypeInternship") : t("certTypeCompletion")}
          </p>
        </div>
        {card.certificate && card.certificate.status !== "Not Yet Eligible" ? (
          <StatusBadge domain="certificate" code={card.certificate.status} />
        ) : (
          <Tag>{t("st_cert_not_eligible")}</Tag>
        )}
      </div>
      <Tracker steps={card.steps} />
      {blocker && <StatusNote tone={blocker.tone}>{blocker.text}</StatusNote>}
      {card.can_download && card.certificate && <IssuedActions card={card} />}
    </li>
  );
}

export function Certificates() {
  const t = useT();
  const query = useMyCertificates();
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead title={t("certificates")} description={t("certsHelp")} />
      <QueryView query={query} skeleton="cards" isEmpty={(data) => data.cards.length === 0} empty={t("noCerts")}>
        {(data) => {
          const feeCard = data.cards.find((c) => c.blocker?.code === "fee_outstanding");
          return (
            <>
              {feeCard && (
                <StatusNote tone="warning" title={t("feeBannerTitle")}>
                  <div className="mt-1 flex flex-wrap items-center gap-3">
                    <span>{t("certFeeOutstanding", { balance: formatMoney(feeCard.blocker?.params["balance"]) })}</span>
                    <Button asChild size="sm" variant="outline" className="tap">
                      <Link to="/finance">{t("payFees")}</Link>
                    </Button>
                  </div>
                </StatusNote>
              )}
              <ul className="grid gap-4 md:grid-cols-2">
                {data.cards.map((card) => (
                  <Card key={card.key} card={card} />
                ))}
              </ul>
            </>
          );
        }}
      </QueryView>
      <HowThisWorks title={t("howCertsWork")}>
        <ul className="list-disc space-y-1 pl-5">
          {(["certRule1", "certRule2", "certRule3", "certRule4"] as const).map((key) => (
            <li key={key}>{t(key)}</li>
          ))}
        </ul>
      </HowThisWorks>
    </div>
  );
}
