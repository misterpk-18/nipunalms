/** One batch: a step bar (Created, Trainer, Ready, Confirmed, Students, Classes), the one next action as the main button, and everything about the batch below. */
import { useState, type ReactNode } from "react";
import { Link, useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { branchApi, type BatchProblem, type BatchProgress } from "@/api/branch";
import { deliveryApi, type BatchDetail } from "@/api/delivery";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { StepBar } from "@/components/lms/step-bar";
import { DataTable, PageHead, PillTabs, QueryView, Section, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Overview, ReadinessTab, StudentsTab, TrainersTab } from "@/features/academic/batch-panel";
import { EditBatchDialog, RequestsTab } from "@/features/academic/batch-operations";
import { StateBadge, fmtDate, fmtDay, fmtRange, useCanManage } from "@/features/shared/delivery-ui";
import { ClassActions } from "./class-actions";
import { AddStudentsDialog, AssignTrainerDialog, ConfirmBatchDialog, CreateClassesDialog, FINISHABLE, FinishSetupDialog } from "./batch-dialogs";
import { NewClassDialog } from "./new-class";

const TABS = ["Overview", "Students", "Classes", "Trainers", "Checks", "Requests", "History"] as const;
type Tab = (typeof TABS)[number];

/** The button for a step: opens the dialog that does it. */
function NextButton({ batch, progress }: { batch: BatchDetail; progress: BatchProgress }) {
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
      return <ConfirmBatchDialog batch={batch} progress={progress} trigger={button} />;
    case "add_students":
      return <AddStudentsDialog batch={batch} trigger={button} />;
    case "create_classes":
      return <CreateClassesDialog batch={batch} trigger={button} />;
  }
}

function Problems({ batch, progress }: { batch: BatchDetail; progress: BatchProgress }) {
  const problems: BatchProblem[] = progress.problems;
  if (problems.length === 0) return null;
  return (
    <section aria-label="Before you can confirm" className="rounded-xl border border-warning/40 bg-warning-soft p-4">
      <h2 className="mb-2 text-base font-semibold">Before you can confirm</h2>
      <ul className="space-y-2">
        {problems.map((p) => (
          <li key={p.key} className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span>
              <strong>{p.label}.</strong> {p.detail}
            </span>
            {p.fix === "trainer" ? (
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
    <StatusNote tone="warning" title="Worth a look before you confirm">
      <ul className="list-disc pl-5">
        {progress.warnings.map((w) => (
          <li key={w.key}>
            {w.label}: {w.detail}
          </li>
        ))}
      </ul>
      <p className="mt-1">You can still confirm. You will be asked to write down why it is acceptable.</p>
    </StatusNote>
  );
}

function ClassesTab({ batch, progress }: { batch: BatchDetail; progress: BatchProgress }) {
  const manage = useCanManage();
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
              { h: "", c: (s) => <ClassActions session={s} /> },
            ]}
          />
        )}
      </QueryView>
    </>
  );
}

function Body({ batch, progress }: { batch: BatchDetail; progress: BatchProgress }) {
  const [tab, setTab] = useState<Tab>("Overview");
  const manage = useCanManage();
  return (
    <>
      <PillTabs
        label="Batch sections"
        tabs={TABS}
        value={tab}
        onChange={setTab}
        counts={{ Students: progress.counts.students, Classes: progress.counts.classes }}
      />
      {tab === "Overview" && <Overview batch={batch} manager={manage} />}
      {tab === "Students" && <StudentsTab batch={batch} manager={manage} />}
      {tab === "Classes" && <ClassesTab batch={batch} progress={progress} />}
      {tab === "Trainers" && <TrainersTab batch={batch} manager={manage} />}
      {tab === "Checks" && <ReadinessTab batch={batch} manager={manage} />}
      {tab === "Requests" && <RequestsTab batch={batch} />}
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

export function BranchBatchPage() {
  const { id } = useParams({ from: "/branch/batches/$id" });
  const batchId = Number(id);
  const valid = Number.isInteger(batchId) && batchId > 0;
  const batchQuery = useQuery({ queryKey: ["delivery", "batch", batchId], queryFn: () => deliveryApi.batch(batchId), enabled: valid });
  const progressQuery = useQuery({ queryKey: ["branch", "progress", batchId], queryFn: () => branchApi.progress(batchId), enabled: valid });
  const manage = useCanManage();
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <QueryView query={batchQuery} skeleton="detail">
        {(batch) => (
          <>
            <Breadcrumbs items={[{ label: "Batches", to: "/branch/batches" }, { label: batch.display_name ?? batch.batch_code }]} />
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
                  <StepBar steps={progress.steps} next={manage ? <NextButton batch={batch} progress={progress} /> : undefined} />
                  {progress.note && <StatusNote tone="info">{progress.note}</StatusNote>}
                  {progress.current === null && !progress.note && (
                    <StatusNote tone="success">This batch is set up: confirmed, with students and classes.</StatusNote>
                  )}
                  <Problems batch={batch} progress={progress} />
                  <Warnings progress={progress} />
                  <Section>
                    <Body batch={batch} progress={progress} />
                  </Section>
                  <HelpLinks />
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
