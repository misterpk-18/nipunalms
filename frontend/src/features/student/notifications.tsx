import { useT } from "@/lib/i18n";
import { NotificationCentre } from "@/features/shared/notification-centre";

export function Notifications() {
  const t = useT();
  return <NotificationCentre title={t("notifications")} />;
}
