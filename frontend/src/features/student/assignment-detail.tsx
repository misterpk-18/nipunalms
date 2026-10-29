import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { assessmentsApi, type Assignment, type Submission } from "@/api/assessments";
import { errorMessage } from "@/api/client";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { KeyValue, Note, PageHead, QueryView, Section, StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { fmtDateTime } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { useT } from "@/lib/i18n";

function VersionCard({ version }: { version: Submission }) {
  const t = useT();
  return (
    <li className="rounded-lg border p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <strong>{t("versionN", { n: version.version_no })}</strong>
        <span className="text-muted-foreground">
          {fmtDateTime(version.submitted_at)} · {t("receiptCode", { code: version.submission_code })}
        </span>
        {version.is_late && <Tag tone="warning">{t("lateTag")}</Tag>}
        {version.review?.outcome === "Resubmission Requested" && <StatusBadge domain="work" code="Resubmission Requested" />}
      </div>
      {version.body_text && <p className="mt-1 whitespace-pre-wrap">{version.body_text}</p>}
      {version.link_url && (
        <p className="mt-1">
          {t("linkPrefix")}{" "}
          <a href={version.link_url} target="_blank" rel="noreferrer" className="text-primary underline">
            {version.link_url}
          </a>
        </p>
      )}
      {version.file && (
        <p className="mt-1">
          {t("filePrefix")} {version.file.filename}
        </p>
      )}
      {version.review?.feedback && (
        <p className="mt-2 rounded bg-muted p-2">
          <strong>{t("feedbackLabel")}:</strong> {version.review.feedback}
          {version.review.resubmission_due_at && <> {t("resubmitBy", { when: fmtDateTime(version.review.resubmission_due_at) })}</>}
          {version.review.marks && (
            <>
              {" "}
              {t("marksLabel")}: {version.review.marks}
            </>
          )}
        </p>
      )}
    </li>
  );
}

function SubmissionForm({ assignment }: { assignment: Assignment }) {
  const t = useT();
  const my = assignment.my!;
  const [text, setText] = useState("");
  const [link, setLink] = useState("");
  const [disclosure, setDisclosure] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const submit = useApiMutation(() => assessmentsApi.submit(assignment.assignment_id, { body_text: text, link_url: link, ai_disclosure: disclosure }, file), {
    success: (s) => t("submittedToast", { n: s.version_no, code: s.submission_code }),
    next: t("submittedNext"),
    view: { to: "/tasks", label: t("backToTasks") },
    invalidate: [["assignments"], ["work"], ["nav"]],
    onSuccess: () => {
      setText("");
      setLink("");
      setDisclosure("");
      setFile(null);
    },
  });
  if (!my.window.allowed) return <StatusNote tone="info">{my.window.reason ?? t("submissionsClosed")}</StatusNote>;
  const label = my.window.mode === "resubmission" ? t("submitResubmission") : my.window.mode === "replacement" ? t("replaceMine") : t("submit");
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        submit.mutate(undefined);
      }}
    >
      {my.window.mode === "replacement" && <Note>{t("replaceNote")}</Note>}
      {my.window.mode === "initial" && new Date() > new Date(assignment.due_at) && <Note>{t("lateNote")}</Note>}
      <div className="space-y-1.5">
        <Label htmlFor="sub-text">{t("notesLabel")}</Label>
        <Textarea id="sub-text" rows={4} value={text} onChange={(e) => setText(e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="sub-link">{t("workLinkLabel")}</Label>
        <Input id="sub-link" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://" />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="sub-file">{t("fileLabel")}</Label>
        <Input id="sub-file" type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </div>
      {assignment.ai_use_rule !== "Not permitted" && (
        <div className="space-y-1.5">
          <Label htmlFor="sub-ai">{t("aiDisclosureLabel")}</Label>
          <Textarea id="sub-ai" rows={2} value={disclosure} onChange={(e) => setDisclosure(e.target.value)} />
        </div>
      )}
      {submit.isError && (
        <StatusNote tone="danger" title={t("couldNotSubmit")}>
          {errorMessage(submit.error)}
        </StatusNote>
      )}
      <Button type="submit" disabled={submit.isPending || (!text.trim() && !link.trim() && !file)}>
        {submit.isPending ? t("submitting") : label}
      </Button>
    </form>
  );
}

export function AssignmentDetail() {
  const t = useT();
  const { id } = useParams({ from: "/assignments/$id" });
  const query = useQuery({ queryKey: ["assignments", "detail", id], queryFn: () => assessmentsApi.assignment(Number(id)) });

  return (
    <div className="mx-auto max-w-4xl">
      <QueryView query={query} skeleton="detail">
        {(a) => {
          const my = a.my!;
          const result = my.result;
          const handedIn = my.state === "Submitted" || my.state === "Under Review";
          const feedback = [...my.versions].reverse().find((v) => v.review?.feedback)?.review?.feedback;
          return (
            <>
              <Breadcrumbs items={[{ label: t("tasksAndTests"), to: "/tasks" }, { label: a.title }]} />
              <PageHead
                title={a.title}
                description={t("dueAt", { when: fmtDateTime(a.due_at) })}
                actions={
                  <>
                    <Tag tone={a.is_required ? "info" : "neutral"}>{a.is_required ? t("required") : t("optional")}</Tag>
                    <StatusBadge domain="work" code={my.state} />
                  </>
                }
              />
              <div className="space-y-4">
                {handedIn && <StatusNote tone="info">{t("handedInNote")}</StatusNote>}
                <Section title={t("assignmentBrief")}>
                  <p className="whitespace-pre-wrap text-sm">{a.brief}</p>
                  {a.attachments.length > 0 && (
                    <>
                      <p className="mt-3 text-sm font-medium">{t("attachmentsLabel")}</p>
                      <ul className="mt-1 list-disc pl-5 text-sm">
                        {a.attachments.map((f) => (
                          <li key={f.url}>
                            <a href={f.url} target="_blank" rel="noreferrer" className="text-primary underline">
                              {f.name}
                            </a>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </Section>
                <Section title={t("yourSubmission")}>
                  <SubmissionForm assignment={a} />
                </Section>
                {my.versions.length > 0 && (
                  <Section title={t("earlierVersions")}>
                    <ul className="space-y-2">
                      {my.versions.map((v) => (
                        <VersionCard key={v.submission_id} version={v} />
                      ))}
                    </ul>
                  </Section>
                )}
                <Section title={t("detailsTitle")}>
                  <KeyValue
                    items={[
                      [t("moduleTopicLabel"), `${a.module?.title ?? "—"} → ${a.topic?.title ?? "—"}`],
                      [t("releasedLabel"), fmtDateTime(a.release_at)],
                      [t("dueLabel"), fmtDateTime(a.due_at)],
                      [t("feedbackLabel"), feedback ?? "—"],
                      [t("marksLabel"), result.marks ? `${result.marks} / ${result.max_marks}` : result.status === "Pending" ? t("marksWithheld") : "—"],
                      [t("aiUseLabel"), a.ai_use_rule],
                      [t("latePolicyLabel"), a.late_policy],
                    ]}
                  />
                </Section>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <Button asChild variant="outline">
                    <Link to="/tasks">{t("backToTasks")}</Link>
                  </Button>
                </div>
                <HowThisWorks title={t("howMarksWork")}>
                  <p>{t("howMarksText1")}</p>
                  <p>{t("howMarksText2")}</p>
                </HowThisWorks>
              </div>
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
