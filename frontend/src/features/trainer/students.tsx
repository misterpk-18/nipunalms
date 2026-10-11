import { useState } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { trainerApi, trainerKeys } from "@/api/trainer";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, PageHead, QueryView, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FlagStudentDialog, type FlagTarget } from "./flag-student";
import { ReasonTags, pct } from "./risk";

export function TrainerStudents() {
  const { batch } = useSearch({ from: "/trainer/students/" });
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [onlyAttention, setOnlyAttention] = useState(false);
  const [flagging, setFlagging] = useState<FlagTarget | null>(null);
  const batches = useQuery({ queryKey: trainerKeys.batches, queryFn: trainerApi.batches });
  const query = useQuery({
    queryKey: trainerKeys.students(q.trim(), batch ?? null),
    queryFn: () => trainerApi.students({ q: q.trim(), ...(batch ? { batch_id: batch } : {}) }),
  });
  const filtered = Boolean(batch) || q.trim() !== "" || onlyAttention;

  return (
    <div className="mx-auto max-w-6xl">
      <PageHead title="Students" description="The students in your batches. Open one to see their attendance, work and results, or flag a problem." />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="w-full sm:w-64">
          <Label htmlFor="students-q">Search</Label>
          <Input id="students-q" placeholder="Name or Student ID" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="w-full sm:w-56">
          <Label htmlFor="students-batch">Batch</Label>
          <NativeSelect
            id="students-batch"
            placeholder="All my batches"
            value={batch ?? ""}
            onChange={(e) => void navigate({ to: "/trainer/students", search: e.target.value ? { batch: Number(e.target.value) } : {} })}
            options={(batches.data ?? []).map((b) => ({ value: b.batch.batch_id, label: b.batch.batch_code }))}
          />
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" checked={onlyAttention} onChange={(e) => setOnlyAttention(e.target.checked)} /> Only students who need attention
        </label>
      </div>
      <QueryView
        query={query}
        isEmpty={(rows) => rows.filter((r) => !onlyAttention || r.reasons.length > 0).length === 0}
        empty={
          filtered ? "No student matches these filters." : "No students are in your batches yet. They appear here once the Branch Manager gives them a seat."
        }
        emptyAction={
          filtered ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setQ("");
                setOnlyAttention(false);
                void navigate({ to: "/trainer/students", search: {} });
              }}
            >
              Clear filters
            </Button>
          ) : undefined
        }
      >
        {(rows) => (
          <DataTable
            caption="Students"
            rows={[...rows]
              .filter((r) => !onlyAttention || r.reasons.length > 0)
              .sort((a, b) => b.reasons.length - a.reasons.length || a.student.full_name.localeCompare(b.student.full_name))}
            getKey={(r) => `${r.student.student_id}-${r.enrolment.enrolment_id}`}
            cols={[
              {
                h: "Student",
                c: (r) => (
                  <>
                    <Link
                      to="/trainer/students/$id"
                      params={{ id: String(r.student.student_id) }}
                      className="font-medium text-primary underline-offset-2 hover:underline"
                    >
                      {r.student.full_name}
                    </Link>
                    <div className="font-mono text-xs text-muted-foreground">{r.student.student_code}</div>
                  </>
                ),
              },
              {
                h: "Batch",
                c: (r) => (
                  <Link
                    to="/trainer/batches/$id"
                    params={{ id: String(r.batch.batch_id) }}
                    className="font-mono text-xs text-primary underline-offset-2 hover:underline"
                  >
                    {r.batch.batch_code}
                  </Link>
                ),
              },
              { h: "Attendance", c: (r) => pct(r.attendance_pct) },
              { h: "Needs attention", c: (r) => <ReasonTags reasons={r.reasons} /> },
              {
                h: "Support",
                c: (r) =>
                  r.open_requests.length > 0 ? (
                    <Tag tone="warning">{r.flag.replace("Open — ", "Open: ")}</Tag>
                  ) : (
                    <span className="text-sm text-muted-foreground">None</span>
                  ),
              },
              {
                h: "",
                c: (r) => (
                  <div className="flex flex-wrap gap-2">
                    <Button asChild size="sm" variant="outline">
                      <Link to="/trainer/students/$id" params={{ id: String(r.student.student_id) }}>
                        Open
                      </Link>
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setFlagging(r.student)} aria-label={`Flag ${r.student.full_name}`}>
                      Flag
                    </Button>
                  </div>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <div className="mt-4">
        <HowThisWorks>
          <p>
            You see only the students in your own batches, and only what you need to teach them: attendance, work, results and support requests. Contact details
            and fees stay with the branch. A student needs attention when attendance is low, work is missing or late, classes are not marked or your review is
            overdue.
          </p>
        </HowThisWorks>
      </div>
      {flagging && <FlagStudentDialog key={flagging.student_id} open student={flagging} onOpenChange={(open) => !open && setFlagging(null)} />}
    </div>
  );
}
