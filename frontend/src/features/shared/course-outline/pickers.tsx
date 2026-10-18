/** A searchable topic picker (names, never ids). */
import { useId, useState } from "react";
import { Plus, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import type { TopicChoice } from "./mutation";

/**
 * Choose several topics by name: type to search, press a result to add it, press a chip to remove it.
 * `choices` should already leave out the topic itself.
 */
export function TopicMultiPicker({
  choices,
  value,
  onChange,
  label,
  emptyText = "There are no other topics in this course.",
}: {
  choices: TopicChoice[];
  value: number[];
  onChange: (next: number[]) => void;
  label: string;
  emptyText?: string;
}) {
  const [search, setSearch] = useState("");
  const id = useId();
  const chosen = value.map((v) => choices.find((c) => c.topic_id === v)).filter((c): c is TopicChoice => !!c);
  const q = search.trim().toLowerCase();
  const matches = choices.filter((c) => !value.includes(c.topic_id) && (!q || c.label.toLowerCase().includes(q)));
  return (
    <div className="space-y-2">
      {chosen.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label={`${label}: chosen`}>
          {chosen.map((c) => (
            <li key={c.topic_id}>
              <button
                type="button"
                aria-label={`Remove ${c.label}`}
                onClick={() => onChange(value.filter((v) => v !== c.topic_id))}
                className="inline-flex max-w-full items-center gap-1 rounded-full border bg-info-soft px-2.5 py-0.5 text-xs font-medium text-info"
              >
                <span className="break-words text-left">{c.label}</span>
                <X className="size-3.5 shrink-0" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      {choices.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyText}</p>
      ) : (
        <>
          <Input
            id={id}
            type="search"
            value={search}
            placeholder="Search topics by name"
            aria-label={`Search ${label.toLowerCase()}`}
            onChange={(e) => setSearch(e.target.value)}
          />
          <ul className="max-h-44 divide-y overflow-y-auto rounded-md border text-sm" aria-label={`${label}: results`}>
            {matches.length === 0 && (
              <li className="px-2 py-2 text-muted-foreground">{q ? "No topic matches that search." : "Every topic is already chosen."}</li>
            )}
            {matches.map((c) => (
              <li key={c.topic_id}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-2 px-2 py-1.5 text-left hover:bg-accent"
                  onClick={() => onChange([...value, c.topic_id])}
                >
                  <span className="break-words">{c.label}</span>
                  <Plus className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
