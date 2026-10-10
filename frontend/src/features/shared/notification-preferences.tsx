/** Which channels carry which kinds of message. Lives on the account screen (Profile); only channels that are live are offered. */
import { useQuery } from "@tanstack/react-query";
import { notificationsApi } from "@/api/notifications";
import { Note, QueryView, Section } from "@/components/lms/ui";
import { Switch } from "@/components/ui/switch";
import { useApiMutation } from "@/lib/mutation";

export function NotificationPreferences() {
  const query = useQuery({ queryKey: ["notifications", "preferences"], queryFn: notificationsApi.preferences });
  const save = useApiMutation((change: { group: string; channel: string; enabled: boolean }) => notificationsApi.setPreferences([change]), {
    invalidate: [["notifications", "preferences"]],
    success: "Preference saved",
  });
  return (
    <Section title="Notification preferences">
      <QueryView query={query}>
        {(prefs) => {
          // In-app is always on; WhatsApp and email appear once they are set up and checked
          const channels = prefs.channels.filter((c) => c.always_on || (c.configuration_status === "Configured" && c.verification_status === "Verified"));
          return (
            <div className="space-y-3">
              {channels.length === 1 ? (
                <Note>Messages arrive in the app. WhatsApp and email will be offered here when they are switched on.</Note>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <caption className="sr-only">Notification preferences by kind of message and channel</caption>
                    <thead>
                      <tr className="text-xs uppercase tracking-wide text-muted-foreground">
                        <th scope="col" className="py-2 pr-3">
                          Kind of message
                        </th>
                        {channels.map((c) => (
                          <th key={c.channel} scope="col" className="px-3 py-2">
                            {c.channel}
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
                          {channels.map((c) => (
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
              )}
            </div>
          );
        }}
      </QueryView>
    </Section>
  );
}
