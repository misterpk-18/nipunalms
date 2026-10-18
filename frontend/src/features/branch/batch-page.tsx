/** What the route lets this role do on the batch page: Branch Manager `manage` and `approve`, read-only (both false) for Super Admin and Founder. */
export type BatchAccess = { manage: boolean; approve: boolean };

/** One batch: a step bar (Created, Trainer, Ready, Confirmed, Students, Classes), the one next action as the main button, and everything about the batch below. */
import { useState, type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { branchApi, type BatchProblem, type BatchProgress } from "@/api/branch";
import { deliveryApi, type BatchDetail } from "@/api/delivery";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { StepBar } from "@/components/lms/step-bar";
import { DataTable, PageHead, PillTabs, QueryView, Section, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Overview, ReadinessTab, StudentsTab, TrainersTab } from "@/features/academic/batch-panel";
import { EditBatchDialog, RequestsTab } from "@/features/academic/batch-operations";
import { StateBadge, fmtDate, fmtDay, fmtRange } from "@/features/shared/delivery-ui";
import { ClassActions } from "./class-actions";
import { AddStudentsDialog, AssignTrainerDialog, ConfirmBatchDialog, CreateClassesDialog, FINISHABLE, FinishSetupDialog } from "./batch-dialogs";
import { NewClassDialog } from "./new-class";

const TABS = ["Overview", "Students", "Classes", "Trainers", "Checks", "Requests", "History"] as const;
type Tab = (typeof TABS)[number];

/** The button for a step: opens the dialog that does it. */
function NextButton({ batch, progress, approve }: { batch: BatchDetail; progress: BatchProgress; approve: boolean }) {
  const next = progress.next;
  if (!next) return null;
  const button = <Button>{next.label}</Button>;
  switch (next.key) {
    case "assign_trainer":
      return <AssignTrainerDialog batch={batch} trigger={button} />;
    case "finish_setup":
      return progress.problems.some((p) => FINISHABLE.includes(p.key)) ? (
        <FinishSetupDialog batch={batch} progress={progress} trigger={button} />
      ) : (
        <EditBatchDialog batch={batch} trigger={button} />
      );
    case "confirm":
      return <ConfirmBatchDialog batch={batch} progress={progress} trigger={button} approve={approve} />;
    case "add_students":
      return <AddStudentsDialog batch={batch} trigger={button} />;
    case "create_classes":
      return <CreateClassesDialog batch={batch} trigger={button} />;
  }
}

function Problems({ batch, progress, manage }: { batch: BatchDetail; progress: BatchProgress; manage: boolean }) {
  const problems: BatchProblem[] = progress.problems;
  if (problems.length === 0) return null;
  return (
    <section aria-label="Before you can confirm" className="rounded-xl border border-warning/40 bg-warning-soft p-4">
      <h2 className="mb-2 text-base font-semibold">Before it can be confirmed</h2>
      <ul className="space-y-2">
        {problems.map((p) => (
          <li key={p.key} className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span>
              <strong>{p.label}.</strong> {p.detail}
            </span>
            {!manage ? null : p.fix === "trainer" ? (
              <AssignTrainerDialog
                batch={batch}
                trigger={
                  <Button size="sm" variant="outline">
                    Assign a trainer
                  </Button>
                }
              />
            ) : (
              <EditBatchDialog
                batch={batch}
                trigger={
                  <Button size="sm" variant="outline">
                    Edit the batch
                  </Button>
                }
              />
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Warnings({ progress }: { progress: BatchProgress }) {
  if (progress.warnings.length === 0 || progress.problems.length > 0) return null;
  return (
    <StatusNote tone="warning" title="Worth a look before it is confirmed">
      <ul className="list-disc pl-5">
        {progress.warnings.map((w) => (
          <li key={w.key}>
            {w.label}: {w.detail}
          </li>
        ))}
      </ul>
      <p className="mt-1">The Branch Manager can still confirm, and writes down why it is acceptable.</p>
    </StatusNote>
  );
}

function ClassesTab({ batch, progress, manage, approve }: { batch: BatchDetail; progress: BatchProgress } & BatchAccess) {
  const query = useQuery({
    queryKey: ["delivery", "sessions", "batch-page", batch.batch_id],
    queryFn: () => deliveryApi.sessions({ batch_id: batch.batch_id }),
  });
  const closed = ["Completed", "Cancelled", "Archived", "On Hold"].includes(batch.state);
  return (
    <>
      {manage && !closed && (
        <div className="mb-3 flex flex-wrap gap-2">
          <CreateClassesDialog
            batch={batch}
            trigger={
              <Button size="sm" variant={progress.current === "classes" ? "default" : "outline"}>
                Create classes
              </Button>
            }
          />
          <NewClassDialog
            batches={[batch]}
            batchId={batch.batch_id}
            approve={approve}
            trigger={
              <Button size="sm" variant="outline">
                New class
              </Button>
            }
          />
        </div>
      )}
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No classes yet. Create them from the timetable, or add one at a time.">
        {(page) => (
          <DataTable
            caption="Classes of this batch"
            rows={page.data}
            getKey={(s) => s.session_id}
            cols={[
              { h: "When (IST)", c: (s) => fmtRange(s.starts_at, s.ends_at) },
              {
                h: "Class",
                c: (s) => (
                  <>
                    <div className="font-medium">{s.title}</div>
                    <div className="text-xs text-muted-foreground">
                      {s.trainer.full_name}
                      {s.room ? ` · ${s.room}` : ""}
                    </div>
                  </>
                ),
              },
              { h: "State", c: (s) => <StateBadge label={s.state_label} /> },
              ...(manage ? [{ h: "", c: (s: (typeof page.data)[number]) => <ClassActions session={s} manage={manage} approve={approve} /> }] : []),
            ]}
          />
        )}
      </QueryView>
    </>
  );
}

function Body({ batch, progress, manage, approve }: { batch: BatchDetail; progress: BatchProgress } & BatchAccess) {
  const [tab, setTab] = useState<Tab>("Overview");
  return (
    <>
      <PillTabs
        label="Batch sections"
        tabs={TABS}
        value={tab}
        onChange={setTab}
        counts={{ Students: progress.counts.students, Classes: progress.counts.classes }}
      />
      {tab === "Overview" && <Overview batch={batch} manage={manage} approve={approve} />}
      {tab === "Students" && <StudentsTab batch={batch} manage={manage} />}
      {tab === "Classes" && <ClassesTab batch={batch} progress={progress} manage={manage} approve={approve} />}
      {tab === "Trainers" && <TrainersTab batch={batch} manage={manage} />}
      {tab === "Checks" && <ReadinessTab batch={batch} manage={manage} />}
      {tab === "Requests" && <RequestsTab batch={batch} manage={manage} approve={approve} />}
      {tab === "History" && (
        <ul className="space-y-1 text-sm">
          {batch.history.map((e) => (
            <li key={e.event_id}>
              {fmtDate(e.created_at)} · <strong>{e.event_type}</strong>
              {e.from_value || e.to_value ? ` (${e.from_value ?? "—"} → ${e.to_value ?? "—"})` : ""} by {e.actor?.full_name ?? "the system"}
              {e.reason ? ` — ${e.reason}` : ""}
            </li>
          ))}
          {batch.history.length === 0 && <li className="text-muted-foreground">No changes recorded.</li>}
        </ul>
      )}
    </>
  );
}

/** `basePath` is the role's batch list (`/branch/batches`, `/admin/batches`, `/founder/batches`); the route also passes `manage` and `approve`. */
export function BatchPage({ id, basePath, manage, approve }: { id: string; basePath: string } & BatchAccess) {
  const batchId = Number(id);
  const valid = Number.isInteger(batchId) && batchId > 0;
  const batchQuery = useQuery({ queryKey: ["delivery", "batch", batchId], queryFn: () => deliveryApi.batch(batchId), enabled: valid });
  const progressQuery = useQuery({ queryKey: ["branch", "progress", batchId], queryFn: () => branchApi.progress(batchId), enabled: valid });
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <QueryView query={batchQuery} skeleton="detail">
        {(batch) => (
          <>
            <Breadcrumbs items={[{ label: "Batches", to: basePath }, { label: batch.display_name ?? batch.batch_code }]} />
            <PageHead
              title={batch.display_name ?? batch.course.title}
              description={
                <>
                  <span className="font-mono">{batch.batch_code}</span> · {batch.course.title} · {batch.branch.branch_name} · {batch.mode} ·{" "}
                  {fmtDay(batch.planned_start)} to {fmtDay(batch.planned_end)}
                </>
              }
              actions={<StateBadge label={batch.state_label} />}
            />
            <QueryView query={progressQuery} skeleton="cards">
              {(progress) => (
                <div className="space-y-4">
                  <StepBar steps={progress.steps} next={manage ? <NextButton batch={batch} progress={progress} approve={approve} /> : undefined} />
                  {progress.note && <StatusNote tone="info">{progress.note}</StatusNote>}
                  {progress.current === null && !progress.note && (
                    <StatusNote tone="success">This batch is set up: confirmed, with students and classes.</StatusNote>
                  )}
                  <Problems batch={batch} progress={progress} manage={manage} />
                  <Warnings progress={progress} />
                  <Section>
                    <Body batch={batch} progress={progress} manage={manage} approve={approve} />
                  </Section>
                  {manage && <HelpLinks />}
                </div>
              )}
            </QueryView>
          </>
        )}
      </QueryView>
    </div>
  );
}

function HelpLinks(): ReactNode {
  return (
    <p className="text-xs text-muted-foreground">
      Students waiting for a batch are on{" "}
      <Link to="/branch/waiting" className="text-primary underline-offset-2 hover:underline">
        Waiting for a batch
      </Link>
      . Classes of all batches are on{" "}
      <Link to="/branch/schedule" className="text-primary underline-offset-2 hover:underline">
        Schedule & calendar
      </Link>
      .
    </p>
  );
}
