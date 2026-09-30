import { useQuery } from "@tanstack/react-query";
import { get, list, post, put, type Page } from "./client";
import type { DateTime } from "./types";

export const NOTIFICATION_VIEWS = ["my", "action", "unread", "completed", "system"] as const;
export type NotificationView = (typeof NOTIFICATION_VIEWS)[number];

export type NotificationItem = {
  notification_id: number;
  category: string;
  title: string;
  body: string | null;
  link: string | null;
  delivery_status: "Delivered" | "Failed";
  delivery_label: string;
  channel: "In-app" | "WhatsApp" | "Email";
  delivery_note: string | null;
  action_status: "None" | "Open" | "Completed";
  read_at: DateTime | null;
  acknowledged_at: DateTime | null;
  created_at: DateTime;
};

export type NotificationOverview = { unread: number; action_required: number; categories: string[] };

export type PreferenceGroup = "Service" | "Learning reminders" | "Placement" | "Promotions & alumni";
export type Preferences = {
  channels: { channel: string; always_on: boolean; configuration_status: string | null; verification_status: string | null }[];
  groups: { group: PreferenceGroup; settings: Record<string, boolean> }[];
};

export const notificationsApi = {
  list: (query: { view?: NotificationView; category?: string; q?: string; page?: number }): Promise<Page<NotificationItem>> =>
    list<NotificationItem>("/notifications", query),
  overview: () => get<NotificationOverview>("/notifications/overview"),
  read: (id: number) => post<NotificationItem>(`/notifications/${id}/read`),
  readAll: () => post<{ marked: number }>("/notifications/read-all"),
  acknowledge: (id: number) => post<NotificationItem>(`/notifications/${id}/acknowledge`),
  actionDone: (id: number) => post<NotificationItem>(`/notifications/${id}/action-done`),
  preferences: () => get<Preferences>("/notifications/preferences"),
  setPreferences: (preferences: { group: string; channel: string; enabled: boolean }[]) => put<Preferences>("/notifications/preferences", { preferences }),
};

/** Unread and action-required counts for the header bell; refreshed every minute. */
export function useNotificationOverview(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ["notifications", "overview"],
    queryFn: notificationsApi.overview,
    refetchInterval: 60_000,
    staleTime: 30_000,
    enabled: options.enabled ?? true,
  });
}
