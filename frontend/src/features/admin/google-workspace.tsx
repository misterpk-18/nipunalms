/** Google Workspace on Setup & health: which Google features are on, the calls and emails that need a person, and each branch's Google settings. */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RotateCw } from "lucide-react";
import { adminApi, adminKeys, type GoogleBranch, type GoogleJob } from "@/api/admin";
import { Field, NativeSelect } from "@/components/lms/forms";
import { DataTable, QueryView, Section, StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApiMutation } from "@/lib/mutation";
import { istDateTime } from "./format";

/** The register's own words, in the words Setup & health uses everywhere else. */
const SETUP_WORD: Record<string, string> = { Verified: "Working", "Pending Verification": "Set up" };

function RetryButton({ job }: { job: GoogleJob }) {
  const retry = useApiMutation(() => adminApi.retryGoogleJob(job.job_id), {
    success: "Queued to try again",
    next: "It runs the next time the Google job runs, within a few minutes",
    invalidate: [[...adminKeys.google]],
  });
  return (
    <Button size="sm" variant="outline" disabled={retry.isPending} onClick={() => retry.mutate(undefined)} aria-label={`Try again: ${job.target}`}>
      <RotateCw className="size-3.5" aria-hidden /> Try again
    </Button>
  );
}

function Problems({ jobs }: { jobs: GoogleJob[] }) {
  return (
    <DataTable
      caption="Google calls that need attention"
      rows={jobs}
      getKey={(j) => j.job_id}
      empty="No Google call is stuck."
      cols={[
        { h: "What", c: (j) => j.what },
        { h: "For", c: (j) => j.target },
        { h: "State", c: (j) => <Tag tone={j.state === "Dead" ? "danger" : "warning"}>{j.state === "Dead" ? "Gave up" : "Will retry"}</Tag> },
        { h: "What went wrong", c: (j) => <span className="text-xs text-muted-foreground">{j.last_error ?? "—"}</span> },
        { h: "Next try", c: (j) => (j.state === "Dead" ? "—" : istDateTime(j.next_attempt_at)) },
        { h: "", c: (j) => <RetryButton job={j} /> },
      ]}
    />
  );
}

function FailedEmails() {
  const query = useQuery({ queryKey: [...adminKeys.googleEmails, "Failed"], queryFn: () => adminApi.googleEmails("Failed") });
  return (
    <QueryView query={query}>
      {(rows) => (
        <DataTable
          caption="Emails that could not be sent"
          rows={rows}
          getKey={(e) => e.outbox_id}
          empty="No email has failed."
          cols={[
            { h: "To", c: (e) => e.to_email ?? "—" },
            { h: "Kind", c: (e) => e.template.replace(/_/g, " ") },
            { h: "When", c: (e) => istDateTime(e.created_at) },
            { h: "What went wrong", c: (e) => <span className="text-xs text-muted-foreground">{e.status_note ?? "—"}</span> },
          ]}
        />
      )}
    </QueryView>
  );
}

type BranchForm = { calendar_mailbox: string; gmail_sender: string; drive_root_folder_id: string };

function toForm(b: GoogleBranch): BranchForm {
  return { calendar_mailbox: b.calendar_mailbox ?? "", gmail_sender: b.gmail_sender ?? "", drive_root_folder_id: b.drive_root_folder_id ?? "" };
}

function BranchSettings({ branches }: { branches: GoogleBranch[] }) {
  const [picked, setPicked] = useState<number | null>(null);
  const branch = branches.find((b) => b.branch_id === (picked ?? branches[0]?.branch_id));
  const [form, setForm] = useState<BranchForm>({ calendar_mailbox: "", gmail_sender: "", drive_root_folder_id: "" });
  useEffect(() => {
    if (branch) setForm(toForm(branch));
  }, [branch]);
  const save = useApiMutation(
    (body: BranchForm) =>
      adminApi.updateGoogleBranch(branch!.branch_id, {
        calendar_mailbox: body.calendar_mailbox.trim() || null,
        gmail_sender: body.gmail_sender.trim() || null,
        drive_root_folder_id: body.drive_root_folder_id.trim() || null,
      }),
    { success: "Google settings saved", invalidate: [[...adminKeys.googleBranches]] },
  );
  if (!branch) return <p className="text-sm text-muted-foreground">No branch yet.</p>;
  const unchanged = JSON.stringify(form) === JSON.stringify(toForm(branch));
  const set = (key: keyof BranchForm) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [key]: e.target.value }));
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Leave a field empty to use the branch mailbox ({branch.branch_mailbox}). Class events and Drive folders are made in the calendar mailbox; emails are
        sent from the sender.
      </p>
      {branches.length > 1 && (
        <div className="max-w-xs">
          <NativeSelect
            aria-label="Branch for the Google settings"
            options={branches.map((b) => ({ value: b.branch_id, label: b.branch_name }))}
            value={branch.branch_id}
            onChange={(e) => setPicked(Number(e.target.value))}
          />
        </div>
      )}
      <div className="grid gap-3 md:grid-cols-3">
        <Field label="Calendar and Drive mailbox" htmlFor="gb-calendar" hint={`Now: ${branch.effective_calendar_mailbox}`}>
          <Input id="gb-calendar" type="email" value={form.calendar_mailbox} onChange={set("calendar_mailbox")} placeholder={branch.branch_mailbox} />
        </Field>
        <Field label="Email sender" htmlFor="gb-sender" hint={`Now: ${branch.effective_gmail_sender}`}>
          <Input id="gb-sender" type="email" value={form.gmail_sender} onChange={set("gmail_sender")} placeholder={branch.branch_mailbox} />
        </Field>
        <Field
          label="Drive folder id"
          htmlFor="gb-folder"
          hint="Optional. The last part of the folder's Drive link. It cannot change once the LMS has made folders in it."
        >
          <Input id="gb-folder" value={form.drive_root_folder_id} onChange={set("drive_root_folder_id")} placeholder="Made for you when empty" />
        </Field>
      </div>
      <Button size="sm" disabled={save.isPending || unchanged} onClick={() => save.mutate(form)}>
        Save
      </Button>
    </div>
  );
}

/** Super Admin and Founder only (the route is theirs and so is the API). */
export function GoogleWorkspace() {
  const overview = useQuery({ queryKey: adminKeys.googleOverview, queryFn: adminApi.googleOverview });
  const branches = useQuery({ queryKey: adminKeys.googleBranches, queryFn: adminApi.googleBranches });
  return (
    <>
      <Section title="Google Workspace">
        <QueryView query={overview}>
          {(data) => (
            <div className="space-y-4">
              {!data.configured && (
                <StatusNote tone="warning" title="Google is not connected yet">
                  The Google service-account key is not set on the server, so nothing below calls Google. Class Meet links stay a manual entry and emails are
                  not sent.
                </StatusNote>
              )}
              <ul className="divide-y rounded-xl border bg-card">
                {data.features.map((f) => (
                  <li key={f.integration_code} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5" data-google={f.integration_code}>
                    <span className="text-sm font-medium">{f.feature}</span>
                    <span className="flex items-center gap-2 text-xs text-muted-foreground">
                      Checklist:
                      <StatusBadge domain="setup" code={SETUP_WORD[f.state] ?? "Not set up"} />
                      <Tag tone={f.live ? "success" : "neutral"}>{f.live ? "On" : "Off"}</Tag>
                    </span>
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted-foreground">
                A feature turns on when its item in the checklist above is marked Working and the server has the Google key. Waiting: {data.jobs.Queued ?? 0} ·
                Retrying: {data.jobs.Failed ?? 0} · Gave up: {data.jobs.Dead ?? 0} · Emails sent: {data.emails.Sent ?? 0}, failed: {data.emails.Failed ?? 0},
                held back: {data.emails.Skipped ?? 0}
              </p>
              <h3 className="text-sm font-semibold">Google calls that need attention</h3>
              <Problems jobs={data.problems} />
              <h3 className="text-sm font-semibold">Emails that could not be sent</h3>
              <FailedEmails />
            </div>
          )}
        </QueryView>
      </Section>
      <Section title="Google settings for each branch">
        <QueryView query={branches} skeleton="cards">
          {(rows) => <BranchSettings branches={rows} />}
        </QueryView>
      </Section>
    </>
  );
}
