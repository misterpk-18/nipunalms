/** Meet connection and the last background checks. They used to sit on the Branch Manager's Meet Operations screen; they are for the Super Admin. */
import { useQuery } from "@tanstack/react-query";
import { deliveryApi } from "@/api/delivery";
import { DataTable, QueryView, Section, StatusBadge, Tag } from "@/components/lms/ui";
import { fmtDate } from "@/features/shared/delivery-ui";

const JOB_LABELS: Record<string, string> = {
  "session-delay-check": "Delayed or failed starts",
  "class-log-check": "Missing class logs",
  "attendance-unconfirmed": "Attendance not confirmed",
  "recording-check": "Recordings",
};

const clock = (iso: string) =>
  `${fmtDate(iso)} ${new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" })} IST`;

export function MeetHealth() {
  const query = useQuery({ queryKey: ["delivery", "meet-operations", "health"], queryFn: () => deliveryApi.meetOperations({}) });
  return (
    <Section title="Meet and class checks">
      <QueryView query={query}>
        {(ops) => (
          <div className="space-y-4">
            <div>
              <p className="mb-1">
                <StatusBadge domain="integration" code={ops.integration.verified ? "Verified" : "Not Verified"} />
              </p>
              <p className="text-sm">{ops.integration.note}</p>
            </div>
            <DataTable
              caption="Last background checks"
              rows={ops.last_runs}
              getKey={(j) => j.job_name}
              cols={[
                { h: "Check", c: (j) => JOB_LABELS[j.job_name] ?? j.job_name },
                { h: "Last succeeded", c: (j) => (j.last_ok_at ? clock(j.last_ok_at) : <Tag tone="warning">Not yet</Tag>) },
              ]}
            />
          </div>
        )}
      </QueryView>
    </Section>
  );
}
