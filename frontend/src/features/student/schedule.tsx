import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { deliveryApi } from "@/api/delivery";
import { NativeSelect } from "@/components/lms/forms";
import { PageHead, QueryView, StatusBadge } from "@/components/lms/ui";
import { useT } from "@/lib/i18n";
import { MeetBadge, fmtDate, fmtTime, mono } from "@/features/shared/delivery-ui";
import { JoinButton } from "./session-detail";

export function Schedule() {
  const t = useT();
  const [course, setCourse] = useState("");
  const courses = useQuery({ queryKey: ["delivery", "my-enrolments"], queryFn: deliveryApi.myEnrolments });
  const query = useQuery({ queryKey: ["delivery", "my-schedule", course], queryFn: () => deliveryApi.mySchedule({ course_id: course || undefined }) });
  const options = [...new Map((courses.data ?? []).map((e) => [e.course.course_id, e.course])).values()].map((c) => ({
    value: c.course_id,
    label: `${c.course_code} — ${c.title}`,
  }));

  return (
    <div className="mx-auto max-w-4xl">
      <PageHead title={t("schedule")} description="All times in IST (Asia/Kolkata)" />
      {options.length > 1 && (
        <div className="mb-4 max-w-md">
          <NativeSelect aria-label="Filter by course" placeholder="All courses" options={options} value={course} onChange={(e) => setCourse(e.target.value)} />
        </div>
      )}
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No upcoming class sessions for your allocated batches.">
        {(page) => (
          <ul className="space-y-3">
            {page.data.map((s) => (
              <li key={s.session_id} className="rounded-xl border bg-card p-4 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-primary">
                      {fmtDate(s.starts_at)} · {fmtTime(s.starts_at)}–{fmtTime(s.ends_at)} IST
                    </p>
                    <Link to="/sessions/$sessionId" params={{ sessionId: String(s.session_id) }} className="font-semibold underline">
                      {s.title}
                    </Link>
                    <p className="text-sm text-muted-foreground">
                      {s.mode} · {s.trainer.full_name} · {s.branch.branch_name} · {mono(s.batch.batch_code)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <StatusBadge>{s.state}</StatusBadge>
                    {s.mode !== "Classroom" && <MeetBadge session={s} />}
                  </div>
                </div>
                <div className="mt-3">
                  <JoinButton session={s} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </QueryView>
    </div>
  );
}
