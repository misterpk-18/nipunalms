import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi } from "@/api/delivery";
import { useAuth } from "@/auth/auth";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, PageHead, QueryView, StatusBadge } from "@/components/lms/ui";
import { ActionDialog, mono, useCanManage } from "@/features/shared/delivery-ui";
import { useDelivery } from "@/features/shared/sessions";
import { AllocationQueue } from "./allocation-queue";
import { BatchPanel } from "./batch-panel";

function NewBatchDialog() {
  const { profile } = useAuth();
  const courses = useQuery({ queryKey: ["delivery", "courses"], queryFn: deliveryApi.courses });
  const create = useDelivery((body: Record<string, unknown>) => deliveryApi.createBatch(body), "Batch created");
  return (
    <ActionDialog
      trigger={<Button>New batch</Button>}
      title="Create a batch"
      description="The Active curriculum version of the course is used. A batch starts in Forming; add a lead trainer, then start it."
      submitLabel="Create batch"
      fields={[
        {
          name: "course_id",
          label: "Course",
          type: "select",
          required: true,
          options: (courses.data ?? []).map((c) => ({ value: c.course_id, label: `${c.course_code} — ${c.title}` })),
        },
        {
          name: "branch_id",
          label: "Branch",
          type: "select",
          required: true,
          options: (profile?.allowed_branches ?? []).map((b) => ({ value: b.branch_id, label: b.branch_name })),
        },
        { name: "capacity", label: "Capacity", type: "number", min: 1, required: true, value: "25" },
        { name: "mode", label: "Mode", type: "select", options: ["Classroom", "Live Online", "Hybrid"].map((m) => ({ value: m, label: m })) },
        { name: "planned_start", label: "Planned start", type: "date" },
        { name: "planned_end", label: "Planned end", type: "date" },
      ]}
      onSubmit={(v) =>
        create.mutateAsync({
          course_id: Number(v["course_id"]),
          branch_id: Number(v["branch_id"]),
          capacity: Number(v["capacity"]),
          mode: v["mode"],
          planned_start: v["planned_start"] || undefined,
          planned_end: v["planned_end"] || undefined,
        })
      }
    />
  );
}

export function AcademicBatches() {
  const manager = useCanManage();
  const { profile } = useAuth();
  const [selected, setSelected] = useState<number | null>(null);
  const [state, setState] = useState("");
  const [branch, setBranch] = useState("");
  const branches = profile?.allowed_branches ?? [];
  const query = useQuery({
    queryKey: ["delivery", "batches", "academic", state, branch],
    queryFn: () => deliveryApi.batches({ state: state || undefined, branch_id: branch || undefined }),
  });
  return (
    <>
      <PageHead
        title="Batch Management"
        description="Batches, trainer assignment, readiness and batch allocation review checks."
        actions={manager ? <NewBatchDialog /> : undefined}
      />
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {branches.length > 1 && (
          <NativeSelect
            aria-label="Filter by branch"
            placeholder="All branches"
            options={branches.map((b) => ({ value: b.branch_id, label: b.branch_name }))}
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
          />
        )}
        <NativeSelect
          aria-label="Filter by state"
          placeholder="All states"
          options={["Forming", "Starting", "Running", "Full", "Completed", "Cancelled"].map((s) => ({ value: s, label: s }))}
          value={state}
          onChange={(e) => setState(e.target.value)}
        />
      </div>
      <QueryView query={query}>
        {(page) => (
          <DataTable
            caption="Batches"
            rows={page.data}
            getKey={(b) => b.batch_id}
            cols={[
              { h: "Batch ID", c: (b) => mono(b.batch_code) },
              { h: "Course", c: (b) => `${b.course.course_code} — ${b.course.title}` },
              ...(branches.length > 1 ? [{ h: "Branch", c: (b: (typeof page.data)[number]) => b.branch.branch_name }] : []),
              { h: "Curriculum", c: (b) => b.curriculum_version?.version_label ?? "Curriculum Mapping Pending" },
              { h: "Capacity", c: (b) => `${b.allocated_count} / ${b.capacity}` },
              { h: "Trainer", c: (b) => b.trainers.map((t) => t.full_name).join(", ") || "Unassigned" },
              { h: "State", c: (b) => <StatusBadge>{b.state}</StatusBadge> },
              { h: "Readiness", c: (b) => <StatusBadge>{b.readiness}</StatusBadge> },
              {
                h: "",
                c: (b) => (
                  <Button size="sm" variant={selected === b.batch_id ? "default" : "outline"} onClick={() => setSelected(b.batch_id)}>
                    Manage
                  </Button>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      {selected && (
        <div className="mt-6">
          <BatchPanel key={selected} batchId={selected} />
        </div>
      )}
      <div className="mt-6">
        <AllocationQueue branchId={branch} />
      </div>
    </>
  );
}
