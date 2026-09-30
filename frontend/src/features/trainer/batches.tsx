import { useQuery } from "@tanstack/react-query";
import { deliveryApi } from "@/api/delivery";
import { DataTable, PageHead, QueryView, StatusBadge } from "@/components/lms/ui";
import { fmtDay, mono } from "@/features/shared/delivery-ui";
import { RosterDialog } from "@/features/shared/sessions";

export function TrainerBatches() {
  const query = useQuery({ queryKey: ["delivery", "batches", "mine"], queryFn: () => deliveryApi.batches({}) });
  return (
    <>
      <PageHead title="My assigned batches" description="Batches you teach, with their curriculum, seats and state." />
      <QueryView query={query}>
        {(page) => (
          <DataTable
            caption="Assigned batches"
            rows={page.data}
            getKey={(b) => b.batch_id}
            empty="No batches are assigned to you yet."
            cols={[
              { h: "Batch", c: (b) => mono(b.batch_code) },
              { h: "Course", c: (b) => `${b.course.course_code} — ${b.course.title}` },
              { h: "Curriculum", c: (b) => b.curriculum_version?.version_label ?? "Curriculum Mapping Pending" },
              { h: "Mode", c: (b) => b.mode },
              { h: "Dates", c: (b) => `${fmtDay(b.planned_start)} → ${fmtDay(b.planned_end)}` },
              { h: "Students", c: (b) => <RosterDialog batch={b} /> },
              { h: "State", c: (b) => <StatusBadge>{b.state}</StatusBadge> },
              { h: "Readiness", c: (b) => <StatusBadge>{b.readiness}</StatusBadge> },
            ]}
          />
        )}
      </QueryView>
    </>
  );
}
