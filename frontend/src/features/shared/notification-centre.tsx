/** The notification inbox: every item has one state (New, Needs action, Done) and one button. Used by every workspace that has a bell. */
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { notificationsApi, type NotificationItem, type NotificationView } from "@/api/notifications";
import { NativeSelect } from "@/components/lms/forms";
import { Note, PageHead, PillTabs, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fmtDateTime } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";

const TABS = ["Needs action", "All", "Done", "System issues"] as const;
type Tab = (typeof TABS)[number];
const VIEW_OF: Record<Tab, NotificationView> = { "Needs action": "needs_action", All: "my", Done: "done", "System issues": "system" };

/** What the button says, by the kind of message (the notification's category). */
const ACTION_LABELS: Record<string, string> = {
  Session: "View schedule",
  Calendar: "View schedule",
  Batch: "View batch",
  Certificate: "View certificate",
  Attendance: "View attendance",
  Enrolment: "View enrolment",
  Courses: "Review",
  Recording: "Open recordings",
  Content: "Open",
  Career: "Open career",
  Support: "View request",
  Completion: "Review",
  Assessments: "Open",
  Access: "View request",
  Assignments: "Open task",
  Reviews: "Grade work",
  Results: "View result",
};
const actionLabel = (category: string) => ACTION_LABELS[category] ?? "Open";

/** One inbox row: the title, a line of detail, the state and the one button that goes to the item. */
export function NotificationRow({ n, onOpen, compact }: { n: NotificationItem; onOpen?: () => void; compact?: boolean }) {
  const refresh = { invalidate: [["notifications"], ["nav"]] };
  const read = useApiMutation((id: number) => notificationsApi.read(id), refresh);
  const done = useApiMutation((id: number) => notificationsApi.actionDone(id), { ...refresh, success: "Marked as done" });
  const open = () => {
    if (n.status === "New") read.mutate(n.notification_id);
    onOpen?.();
  };
  return (
    <li className={compact ? "flex flex-col gap-2 py-3" : "flex flex-wrap items-start justify-between gap-3 py-3"}>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge domain="notification" code={n.status} />
          <span className={n.status === "New" || n.status === "Needs action" ? "text-sm font-semibold" : "text-sm"}>{n.title}</span>
        </div>
        {n.body && <p className="mt-1 text-sm text-muted-foreground">{n.body}</p>}
        <p className="mt-1 text-xs text-muted-foreground">
          {n.category} · {fmtDateTime(n.created_at)}
          {n.status === "Failed" && ` · ${n.delivery_label}`}
        </p>
      </div>
      {n.status !== "Failed" && (
        <div className={compact ? "flex items-center gap-2" : "flex shrink-0 items-center gap-2"}>
          {n.status === "Needs action" && (
            <Button size="sm" variant="ghost" onClick={() => done.mutate(n.notification_id)} disabled={done.isPending} aria-label={`Mark as done: ${n.title}`}>
              Mark as done
            </Button>
          )}
          {n.link ? (
            <Button asChild size="sm" variant={n.status === "Done" ? "outline" : "default"}>
              <Link to={n.link} onClick={open}>
                {actionLabel(n.category)}
              </Link>
            </Button>
          ) : (
            n.status === "New" && (
              <Button size="sm" variant="outline" onClick={() => read.mutate(n.notification_id)}>
                Mark as read
              </Button>
            )
          )}
        </div>
      )}
    </li>
  );
}

/** `showSystemIssuesTab` is set by the route (Super Admin and Founder only). */
export function NotificationCentre({ title, showSystemIssuesTab = false }: { title: string; showSystemIssuesTab?: boolean }) {
  const tabs = showSystemIssuesTab ? TABS : TABS.filter((t) => t !== "System issues");
  const overview = useQuery({ queryKey: ["notifications", "overview"], queryFn: notificationsApi.overview });
  const [picked, setPicked] = useState<Tab | null>(null);
  // Opens on what needs the person when there is anything, else on everything
  const tab = picked ?? ((overview.data?.needs_action ?? 0) > 0 ? "Needs action" : "All");
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const filters = { view: VIEW_OF[tab], category, q, page };
  const query = useQuery({ queryKey: ["notifications", "list", filters], queryFn: () => notificationsApi.list(filters) });
  const readAll = useApiMutation(() => notificationsApi.readAll(), { invalidate: [["notifications"], ["nav"]], success: (r) => `${r.marked} marked as read` });
  const empty: Record<Tab, string> = {
    "Needs action": "Nothing is waiting for you. New things that need you appear here.",
    All: "No notifications yet. Updates about your classes, work and requests will appear here.",
    Done: "Nothing here yet. Items you have read or finished move here.",
    "System issues": "No messages failed to send.",
  };

  return (
    <div className="mx-auto max-w-4xl">
      <PageHead
        title={title}
        description="What needs you, and what has happened. Each item has one button that takes you there."
        actions={
          <Button variant="outline" onClick={() => readAll.mutate()} disabled={readAll.isPending || !overview.data?.unread}>
            Mark all as read
          </Button>
        }
      />
      <PillTabs
        tabs={tabs}
        value={tab}
        onChange={(next) => (setPicked(next), setPage(1))}
        label="Notification views"
        counts={{ "Needs action": overview.data?.needs_action }}
      />
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <div className="w-full sm:w-48">
          <Label htmlFor="notification-category">Kind</Label>
          <NativeSelect
            id="notification-category"
            placeholder="All kinds"
            value={category}
            onChange={(e) => (setCategory(e.target.value), setPage(1))}
            options={(overview.data?.categories ?? []).map((c) => ({ value: c, label: c }))}
          />
        </div>
        <div className="w-full sm:w-64">
          <Label htmlFor="notification-search">Search</Label>
          <Input id="notification-search" placeholder="Search notifications" value={q} onChange={(e) => (setQ(e.target.value), setPage(1))} />
        </div>
      </div>
      <QueryView query={query} isEmpty={(r) => r.data.length === 0} empty={empty[tab]}>
        {(result) => (
          <>
            <ul className="divide-y rounded-xl border bg-card px-4 shadow-sm" aria-label="Notifications">
              {result.data.map((n) => (
                <NotificationRow key={n.notification_id} n={n} />
              ))}
            </ul>
            {result.meta.pages > 1 && (
              <div className="mt-3 flex items-center justify-end gap-2 text-sm">
                <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                  Previous
                </Button>
                <span>
                  Page {result.meta.page} of {result.meta.pages}
                </span>
                <Button size="sm" variant="outline" disabled={page >= result.meta.pages} onClick={() => setPage(page + 1)}>
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </QueryView>
      <div className="mt-4">
        <Note>Notification channels are set on your account page.</Note>
      </div>
    </div>
  );
}
