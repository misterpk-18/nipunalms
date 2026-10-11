/** Which channels carry which kinds of message. Lives on the account screen (Profile); only channels that are live are offered. */
import { useQuery } from "@tanstack/react-query";
import { notificationsApi } from "@/api/notifications";
import { Note, QueryView, Section } from "@/components/lms/ui";
import { Switch } from "@/components/ui/switch";
import { useApiMutation } from "@/lib/mutation";
import { useT, type TranslationKey } from "@/lib/i18n";

const GROUP_KEY: Record<string, TranslationKey> = {
  Service: "np_group_service",
  "Learning reminders": "np_group_learning",
  Placement: "np_group_placement",
  "Promotions & alumni": "np_group_promotions",
};
const CHANNEL_KEY: Record<string, TranslationKey> = { "In-app": "np_channel_app", WhatsApp: "np_channel_whatsapp", Email: "np_channel_email" };

/** `translated` is the student's version (words through t()); staff keep English. */
export function NotificationPreferences({ translated = false }: { translated?: boolean }) {
  const t = useT();
  const say = (english: string, key: TranslationKey) => (translated ? t(key) : english);
  const groupName = (group: string) => (translated && GROUP_KEY[group] ? t(GROUP_KEY[group]!) : group);
  const channelName = (channel: string) => (translated && CHANNEL_KEY[channel] ? t(CHANNEL_KEY[channel]!) : channel);
  const query = useQuery({ queryKey: ["notifications", "preferences"], queryFn: notificationsApi.preferences });
  const save = useApiMutation((change: { group: string; channel: string; enabled: boolean }) => notificationsApi.setPreferences([change]), {
    invalidate: [["notifications", "preferences"]],
    success: say("Preference saved", "np_saved"),
  });
  return (
    <Section title={say("Notification preferences", "np_title")}>
      <QueryView query={query}>
        {(prefs) => {
          // In-app is always on; WhatsApp and email appear only once they are really switched on
          const channels = prefs.channels.filter((c) => c.live);
          return (
            <div className="space-y-3">
              {channels.length === 1 ? (
                <Note>{say("Messages arrive in the app. WhatsApp and email will be offered here when they are switched on.", "np_app_only")}</Note>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <caption className="sr-only">{say("Notification preferences by kind of message and channel", "np_caption")}</caption>
                    <thead>
                      <tr className="text-xs uppercase tracking-wide text-muted-foreground">
                        <th scope="col" className="py-2 pr-3">
                          {say("Kind of message", "np_kind")}
                        </th>
                        {channels.map((c) => (
                          <th key={c.channel} scope="col" className="px-3 py-2">
                            {channelName(c.channel)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {prefs.groups.map((g) => (
                        <tr key={g.group} className="border-t">
                          <th scope="row" className="py-2 pr-3 font-medium">
                            {groupName(g.group)}
                          </th>
                          {channels.map((c) => (
                            <td key={c.channel} className="px-3 py-2">
                              <Switch
                                checked={g.settings[c.channel] ?? false}
                                disabled={c.always_on || save.isPending}
                                aria-label={`${groupName(g.group)}: ${channelName(c.channel)}`}
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
