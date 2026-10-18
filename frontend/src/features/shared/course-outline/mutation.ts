/** The mutation helper and the topic helpers the course outline screens share. */
import { ApiError } from "@/api/client";
import type { ModuleContent } from "@/api/delivery";
import { useApiMutation } from "@/lib/mutation";

type MutationExtras<R> = {
  /** One line under the message: what happens next. */
  next?: string | ((result: R) => string);
  onSuccess?: (result: R) => void;
  /** Leave server field errors to the form (it shows them itself). */
  silentValidation?: boolean;
};

/** A course outline change: refreshes every course, delivery, branch and nav query and toasts what happened. */
export function useCourseMutation<V, R>(fn: (vars: V) => Promise<R>, success: string | ((result: R) => string), extras: MutationExtras<R> = {}) {
  return useApiMutation<V, R>(fn, {
    success,
    invalidate: [["courses"], ["delivery"], ["branch"], ["nav"]],
    ...(extras.next ? { next: extras.next } : {}),
    ...(extras.onSuccess ? { onSuccess: (result: R) => extras.onSuccess?.(result) } : {}),
    ...(extras.silentValidation ? { silentValidation: true } : {}),
  });
}

/** The messages a 422 carries per field, or the plain message. */
export function serverMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const found = Object.values(error.details ?? {}).flatMap((m) => (Array.isArray(m) ? m.map(String) : [String(m)]));
    return found.length ? found.join(" ") : error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong";
}

export type TopicChoice = { topic_id: number; label: string };

/** "Core Java > Variables" for every topic of the outline, in order. */
export function topicChoices(modules: ModuleContent[]): TopicChoice[] {
  return modules.flatMap((m) => m.topics.map((t) => ({ topic_id: t.topic_id, label: `${m.title} > ${t.title}` })));
}

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
export const hoursText = (minutes: number) => `${(minutes / 60).toFixed(1)} h`;
