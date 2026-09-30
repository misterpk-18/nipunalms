/** The in-app notification centre: delivery, read, acknowledged and action states shown and changed separately. Used by the student and trainer screens. */
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { notificationsApi, type NotificationItem, type NotificationView } from "@/api/notifications";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, Note, PageHead, PillTabs, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useApiMutation } from "@/lib/mutation";
import { formatIst } from "./ist";

const TABS = ["My Notifications", "Action Required", "Unread", "Completed", "System Issues"] as const;
type Tab = (typeof TABS)[number];
const VIEW_OF: Record<Tab, NotificationView> = {
  "My Notifications": "my",
  "Action Required": "action",
  Unread: "unread",
  Completed: "completed",
  "System Issues": "system",
};

function actionLabel(n: NotificationItem) {
  if (n.action_status === "Open") return "Not completed";
  if (n.action_status === "Completed") return "Action Completed";
  return "—";
}

export function NotificationCentre({ title }: { title: string }) {
  const [tab, setTab] = useState<Tab>("My Notifications");
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const filters = { view: VIEW_OF[tab], category, q, page };
  const query = useQuery({ queryKey: ["notifications", "list", filters], queryFn: () => notificationsApi.list(filters) });
  const overview = useQuery({ queryKey: ["notifications", "overview"], queryFn: notificationsApi.overview });
  const refresh = { invalidate: [["notifications"]] };
  const read = useApiMutation((id: number) => notificationsApi.read(id), refresh);
  const acknowledge = useApiMutation((id: number) => notificationsApi.acknowledge(id), { ...refresh, success: "Acknowledged" });
  const done = useApiMutation((id: number) => notificationsApi.actionDone(id), { ...refresh, success: "Action marked done" });
  const readAll = useApiMutation(() => notificationsApi.readAll(), { ...refresh, success: (r) => `${r.marked} marked as read` });

  return (
    <div className="mx-auto max-w-6xl">
      <PageHead
        title={title}
        description="In-app notification centre"
        actions={
          <Button variant="outline" onClick={() => readAll.mutate()} disabled={readAll.isPending || !overview.data?.unread}>
            Mark all as read
          </Button>
        }
      />
      <PillTabs tabs={TABS} value={tab} onChange={(next) => (setTab(next), setPage(1))} label="Notification views" />
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <div className="w-full sm:w-48">
          <Label htmlFor="notification-category">Category</Label>
          <NativeSelect
            id="notification-category"
            placeholder="All categories"
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
      <QueryView query={query} isEmpty={(r) => r.data.length === 0} empty="No notifications in this view.">
        {(result) => (
          <>
            <DataTable
              caption="Notifications"
              rows={result.data}
              getKey={(n) => n.notification_id}
              cols={[
                {
                  h: "Notification",
                  c: (n) => (
                    <div>
                      <div className={n.read_at || n.delivery_status === "Failed" ? "" : "font-semibold"}>
                        {n.link ? (
                          <Link
                            to={n.link}
                            onClick={() => !n.read_at && n.delivery_status === "Delivered" && read.mutate(n.notification_id)}
                            className="underline-offset-2 hover:underline"
                          >
                            {n.title}
                          </Link>
                        ) : (
                          n.title
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {n.category} · {formatIst(n.created_at)}
                      </div>
                    </div>
                  ),
                },
                { h: "Delivery", c: (n) => <StatusBadge tone={n.delivery_status === "Failed" ? "neutral" : "success"}>{n.delivery_label}</StatusBadge> },
                {
                  h: "Read",
                  c: (n) =>
                    n.delivery_status === "Failed" ? "—" : <StatusBadge tone={n.read_at ? "success" : "warning"}>{n.read_at ? "Read" : "Unread"}</StatusBadge>,
                },
                {
                  h: "Acknowledged",
                  c: (n) =>
                    n.delivery_status === "Failed" ? (
                      "—"
                    ) : n.acknowledged_at ? (
                      <StatusBadge tone="success">Acknowledged</StatusBadge>
                    ) : (
                      <Button size="sm" variant="outline" onClick={() => acknowledge.mutate(n.notification_id)} aria-label={`Acknowledge ${n.title}`}>
                        Acknowledge
                      </Button>
                    ),
                },
                {
                  h: "Action",
                  c: (n) =>
                    n.action_status === "Open" ? (
                      <Button size="sm" onClick={() => done.mutate(n.notification_id)} aria-label={`Mark action done for ${n.title}`}>
                        Mark action done
                      </Button>
                    ) : (
                      <StatusBadge tone={n.action_status === "Completed" ? "success" : "neutral"}>{actionLabel(n)}</StatusBadge>
                    ),
                },
              ]}
            />
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
        <Note>
          Delivery, Read, Acknowledged and Action Completed are tracked separately. WhatsApp and email are not delivering until their integrations are verified.
        </Note>
      </div>
      <div className="mt-4">
        <Preferences />
      </div>
    </div>
  );
}

function Preferences() {
  const query = useQuery({ queryKey: ["notifications", "preferences"], queryFn: notificationsApi.preferences });
  const save = useApiMutation((change: { group: string; channel: string; enabled: boolean }) => notificationsApi.setPreferences([change]), {
    invalidate: [["notifications", "preferences"]],
    success: "Preference saved",
  });
  return (
    <Section title="Notification preferences">
      <QueryView query={query}>
        {(prefs) => (
          <div className="space-y-3">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Notification preferences by group and channel</caption>
                <thead>
                  <tr className="text-xs uppercase tracking-wide text-muted-foreground">
                    <th scope="col" className="py-2 pr-3">
                      Group
                    </th>
                    {prefs.channels.map((c) => (
                      <th key={c.channel} scope="col" className="px-3 py-2">
                        {c.channel}
                        {!c.always_on && (
                          <div className="text-[11px] font-normal normal-case">
                            {c.configuration_status} · {c.verification_status}
                          </div>
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {prefs.groups.map((g) => (
                    <tr key={g.group} className="border-t">
                      <th scope="row" className="py-2 pr-3 font-medium">
                        {g.group}
                      </th>
                      {prefs.channels.map((c) => (
                        <td key={c.channel} className="px-3 py-2">
                          <Switch
                            checked={g.settings[c.channel] ?? false}
                            disabled={c.always_on || save.isPending}
                            aria-label={`${g.group} by ${c.channel}`}
                            onCheckedChange={(enabled) => save.mutate({ group: g.group, channel: c.channel, enabled })}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Note>In-app is always on. Choices for WhatsApp and email take effect only after those channels are configured and verified.</Note>
          </div>
        )}
      </QueryView>
    </Section>
  );
}
