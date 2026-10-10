import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { notificationsApi, useNotificationOverview } from "@/api/notifications";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { NotificationRow } from "@/features/shared/notification-centre";

/** The header bell: a count of what is new or needs you, and a preview of the latest five with a link to the whole inbox. */
export function NotificationBell({ inbox, label }: { inbox: string; label: string }) {
  const [open, setOpen] = useState(false);
  const overview = useNotificationOverview().data;
  const count = (overview?.new ?? 0) + (overview?.needs_action ?? 0);
  const latest = useQuery({ queryKey: ["notifications", "list", "preview"], queryFn: () => notificationsApi.list({ view: "my" }), enabled: open });
  const items = (latest.data?.data ?? []).slice(0, 5);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button aria-label={label} className="tap relative grid place-items-center rounded-lg hover:bg-navy-muted">
          <Bell className="size-5" aria-hidden />
          {count > 0 && (
            <span
              data-testid="unread-count"
              className="absolute right-0.5 top-0.5 grid min-w-4 place-items-center rounded-full bg-danger px-1 text-[10px] font-semibold leading-4 text-white"
            >
              {count > 99 ? "99+" : count}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[22rem] max-w-[calc(100vw-1.5rem)] p-0 text-foreground">
        <div className="flex items-center justify-between border-b px-4 py-2.5">
          <h2 className="text-sm font-semibold">{label}</h2>
          {(overview?.needs_action ?? 0) > 0 && <span className="text-xs text-muted-foreground">{overview?.needs_action} need action</span>}
        </div>
        {latest.isLoading ? (
          <p className="px-4 py-6 text-center text-sm text-muted-foreground">Loading…</p>
        ) : items.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-muted-foreground">Nothing yet. Updates about your work will appear here.</p>
        ) : (
          <ul className="max-h-[26rem] divide-y overflow-y-auto px-4">
            {items.map((n) => (
              <NotificationRow key={n.notification_id} n={n} onOpen={() => setOpen(false)} compact />
            ))}
          </ul>
        )}
        <div className="border-t p-2">
          <Button asChild variant="ghost" size="sm" className="w-full">
            <Link to={inbox} onClick={() => setOpen(false)}>
              Open inbox
            </Link>
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
