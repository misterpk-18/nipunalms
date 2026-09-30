import { useQuery } from "@tanstack/react-query";
import { supportApi } from "@/api/support";
import { DataTable, Note, PageHead, QueryView, StatusBadge } from "@/components/lms/ui";

export function TrainerStudents() {
  const query = useQuery({ queryKey: ["support", "assigned-students"], queryFn: supportApi.assignedStudents });
  return (
    <>
      <PageHead title="Assigned students" description="Students allocated to your batches, with their support flags." />
      <div className="space-y-4">
        <QueryView query={query} isEmpty={(rows) => rows.length === 0} empty="No students are allocated to your batches yet.">
          {(rows) => (
            <DataTable
              caption="Students"
              rows={rows}
              getKey={(r) => `${r.student.student_id}-${r.enrolment.enrolment_id}`}
              cols={[
                { h: "Student", c: (r) => r.student.full_name },
                { h: "Batch", c: (r) => <span className="font-mono text-xs">{r.batch.batch_code}</span> },
                { h: "Support flag", c: (r) => <StatusBadge tone={r.open_requests.length ? "warning" : "neutral"}>{r.flag}</StatusBadge> },
              ]}
            />
          )}
        </QueryView>
        <Note>Attendance figures come from the Attendance module. Contact details and finance are not visible to trainers.</Note>
      </div>
    </>
  );
}
