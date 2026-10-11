import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useMyRequests, type MyRequest } from "@/api/requests";
import { EmptyState } from "@/components/lms/empty-state";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, PillTabs, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { fmtDateTime } from "@/features/shared/format";

const TABS = ["Waiting", "Decided", "All"] as const;
type Tab = (typeof TABS)[number];

function RequestCard({ request }: { request: MyRequest }) {
  const waiting = request.status === "Pending";
  return (
    <li className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium">{request.title}</p>
          <p className="text-sm text-muted-foreground">
            {request.session.title} · {request.session.batch.batch_code} · asked {fmtDateTime(request.requested_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Tag tone="info">{request.kind === "reschedule" ? "Move a class" : "Attendance correction"}</Tag>
          <StatusBadge domain="approval" code={request.status} />
        </div>
      </div>
      <p className="mt-2 text-sm">{request.summary}</p>
      <p className="mt-1 text-sm text-muted-foreground">Your reason: {request.reason}</p>
      {waiting ? (
        <p className="mt-2 text-sm text-muted-foreground">Waiting for the {request.decides} to decide. You will be told here and by notification.</p>
      ) : (
        <div className="mt-2 rounded-lg bg-muted/60 p-3 text-sm">
          <p>
            <span className="font-medium">{request.status === "Approved" ? "Approved" : "Not approved"}</span> by{" "}
            {request.decided_by?.full_name ?? "the reviewer"} · {fmtDateTime(request.decided_at)}
          </p>
          {request.decision_note && <p className="mt-1">Their note: {request.decision_note}</p>}
        </div>
      )}
      <div className="mt-3">
        {request.kind === "reschedule" ? (
          <Button asChild size="sm" variant="outline">
            <Link to="/trainer/sessions">See your sessions</Link>
          </Button>
        ) : (
          <Button asChild size="sm" variant="outline">
            <Link to="/trainer/attendance" search={{ session: request.session.session_id }}>
              Open the register
            </Link>
          </Button>
        )}
      </div>
    </li>
  );
}

export function TrainerRequests() {
  const query = useMyRequests();
  const [tab, setTab] = useState<Tab | null>(null);
  return (
    <div className="mx-auto max-w-4xl">
      <PageHead title="My requests" description="What you asked your Branch Manager for, and what they decided." />
      <QueryView
        query={query}
        skeleton="cards"
        isEmpty={(data) => data.items.length === 0}
        empty="You have not asked for anything yet. To move a class, open it in Sessions. To fix an attendance entry, open its register in Attendance."
        emptyAction={
          <div className="flex flex-wrap justify-center gap-2">
            <Button asChild size="sm">
              <Link to="/trainer/sessions">Open Sessions</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to="/trainer/attendance">Open Attendance</Link>
            </Button>
          </div>
        }
      >
        {(data) => {
          // Opens on what is still waiting; when nothing is, on the answers
          const active: Tab = tab ?? (data.counts.waiting > 0 ? "Waiting" : "Decided");
          const rows = data.items.filter((r) => (active === "All" ? true : active === "Waiting" ? r.status === "Pending" : r.status !== "Pending"));
          return (
            <>
              <PillTabs
                label="Request status"
                tabs={TABS}
                value={active}
                onChange={setTab}
                counts={{ Waiting: data.counts.waiting, Decided: data.counts.decided }}
              />
              {rows.length === 0 ? (
                <EmptyState reason={active === "Waiting" ? "Nothing is waiting for a decision." : "No request has been decided yet."} />
              ) : (
                <ul className="space-y-3">
                  {rows.map((r) => (
                    <RequestCard key={`${r.kind}-${r.id}`} request={r} />
                  ))}
                </ul>
              )}
              <div className="mt-4">
                <HowThisWorks>
                  <p>Your Branch Manager decides every request. When they do, you get a notification and the answer shows here with their reason.</p>
                </HowThisWorks>
              </div>
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
