import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { assessmentsApi, type Assignment, type Submission } from "@/api/assessments";
import { errorMessage } from "@/api/client";
import { KeyValue, Note, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { formatIst } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";
import { useT } from "@/lib/i18n";

function VersionCard({ version }: { version: Submission }) {
  return (
    <li className="rounded-lg border p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <strong>v{version.version_no}</strong>
        <span className="text-muted-foreground">
          {formatIst(version.submitted_at)} · receipt {version.submission_code}
        </span>
        {version.is_late && <StatusBadge tone="warning">Late</StatusBadge>}
        {version.review?.outcome === "Resubmission Requested" && <StatusBadge>Resubmission Requested</StatusBadge>}
      </div>
      {version.body_text && <p className="mt-1 whitespace-pre-wrap">{version.body_text}</p>}
      {version.link_url && (
        <p className="mt-1">
          Link:{" "}
          <a href={version.link_url} target="_blank" rel="noreferrer" className="text-primary underline">
            {version.link_url}
          </a>
        </p>
      )}
      {version.file && <p className="mt-1">File: {version.file.filename}</p>}
      {version.review?.feedback && (
        <p className="mt-2 rounded bg-muted p-2">
          <strong>Feedback:</strong> {version.review.feedback}
          {version.review.resubmission_due_at && <> Resubmit by {formatIst(version.review.resubmission_due_at)}.</>}
          {version.review.marks && <> Marks: {version.review.marks}</>}
        </p>
      )}
    </li>
  );
}

function SubmissionForm({ assignment }: { assignment: Assignment }) {
  const my = assignment.my!;
  const [text, setText] = useState("");
  const [link, setLink] = useState("");
  const [disclosure, setDisclosure] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const submit = useApiMutation(() => assessmentsApi.submit(assignment.assignment_id, { body_text: text, link_url: link, ai_disclosure: disclosure }, file), {
    success: (s) => `Submitted as v${s.version_no}. Receipt ${s.submission_code}`,
    invalidate: [["assignments"]],
    onSuccess: () => {
      setText("");
      setLink("");
      setDisclosure("");
      setFile(null);
    },
  });
  if (!my.window.allowed) return <StatusNote state="Not Submitted">{my.window.reason ?? "Submissions are closed."}</StatusNote>;
  const label = my.window.mode === "resubmission" ? "Submit resubmission" : my.window.mode === "replacement" ? "Replace my submission" : "Submit";
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        submit.mutate(undefined);
      }}
    >
      {my.window.mode === "replacement" && <Note>You can replace your work until the due time; every version is kept.</Note>}
      {my.window.mode === "initial" && new Date() > new Date(assignment.due_at) && <Note>The due time has passed: your submission will be marked Late.</Note>}
      <div className="space-y-1.5">
        <Label htmlFor="sub-text">Notes</Label>
        <Textarea id="sub-text" rows={4} value={text} onChange={(e) => setText(e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="sub-link">Link to your work (repository, notebook)</Label>
        <Input id="sub-link" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://" />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="sub-file">File (up to 10 MB)</Label>
        <Input id="sub-file" type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </div>
      {assignment.ai_use_rule !== "Not permitted" && (
        <div className="space-y-1.5">
          <Label htmlFor="sub-ai">AI assistance used (tool, help received, what you checked yourself)</Label>
          <Textarea id="sub-ai" rows={2} value={disclosure} onChange={(e) => setDisclosure(e.target.value)} />
        </div>
      )}
      {submit.isError && <StatusNote state="Failed">{errorMessage(submit.error)}</StatusNote>}
      <Button type="submit" disabled={submit.isPending || (!text && !link && !file)}>
        {submit.isPending ? "Submitting…" : label}
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
      <QueryView query={query}>
        {(a) => {
          const my = a.my!;
          const result = my.result;
          return (
            <>
              <nav className="mb-2 text-sm">
                <Link to="/assignments" className="text-primary underline">
                  {t("assignments")}
                </Link>{" "}
                / {a.title}
              </nav>
              <PageHead
                title={a.title}
                actions={
                  <>
                    <StatusBadge tone={a.is_required ? "info" : "neutral"}>{a.is_required ? "Required" : "Optional"}</StatusBadge>
                    <StatusBadge>{my.state}</StatusBadge>
                  </>
                }
              />
              <div className="space-y-4">
                <Section>
                  <KeyValue
                    items={[
                      ["Module → Topic", `${a.module?.title ?? "—"} → ${a.topic?.title ?? "—"}`],
                      ["Released", formatIst(a.release_at)],
                      ["Due", formatIst(a.due_at)],
                      [
                        "Submission version",
                        my.versions.length ? `v${my.versions.length} (${formatIst(my.versions[my.versions.length - 1]?.submitted_at)})` : "—",
                      ],
                      ["Feedback", [...my.versions].reverse().find((v) => v.review?.feedback)?.review?.feedback ?? "—"],
                      [
                        "Marks / result",
                        result.marks ? `${result.marks} / ${result.max_marks}` : result.status === "Pending" ? "Withheld until publication" : "—",
                      ],
                      ["AI use", a.ai_use_rule],
                      ["Late policy", a.late_policy],
                    ]}
                  />
                  <p className="mt-4 whitespace-pre-wrap text-sm">
                    <strong>Brief:</strong> {a.brief}
                  </p>
                  {a.attachments.length > 0 && (
                    <ul className="mt-2 list-disc pl-5 text-sm">
                      {a.attachments.map((f) => (
                        <li key={f.url}>
                          <a href={f.url} target="_blank" rel="noreferrer" className="text-primary underline">
                            {f.name}
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                </Section>
                {my.versions.length > 0 && (
                  <Section title="Your submissions">
                    <ul className="space-y-2">
                      {my.versions.map((v) => (
                        <VersionCard key={v.submission_id} version={v} />
                      ))}
                    </ul>
                  </Section>
                )}
                <Section title="Your submission">
                  <SubmissionForm assignment={a} />
                </Section>
                <Note>Marks stay provisional until your Academic Coordinator publishes the result.</Note>
              </div>
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
