/** The Founder's "Needs you" list: one row and one button per item; the button opens the item in a side panel on the same page. */
import { useFounderInbox, type InboxGroup, type InboxItem } from "@/api/founder";
import { NeedsYouList, type NeedsYouItem } from "@/components/lms/needs-you-list";
import { QueryView } from "@/components/lms/ui";
import { useUrlParams } from "@/features/branch/attendance-url";
import { ageText } from "@/features/shared/format";
import { FounderPanel } from "./panel";

const DAY_MS = 86_400_000;

function waited(item: InboxItem): string | undefined {
  if (!item.since) return undefined;
  const days = Math.max(Math.floor((Date.now() - new Date(item.since).getTime()) / DAY_MS), 0);
  return days === 0 ? "Came in today" : `Waiting ${ageText(days)}`;
}

const needsYou = (items: InboxItem[], page: string): NeedsYouItem[] =>
  items.map((item) => ({
    id: item.key,
    what: item.title,
    where: [item.where, item.from_branch_manager ? "A Branch Manager's own request" : null].filter(Boolean).join(" · ") || undefined,
    age: waited(item),
    to: page,
    search: { item: item.key },
    action: item.action,
  }));

export function InboxList({
  page,
  group,
  title = "Needs you",
  empty = "Nothing is waiting for you. New items appear here as they come in.",
}: {
  /** The path of the page this list is on, so a button opens the panel there. */
  page: string;
  group?: InboxGroup;
  title?: string;
  empty?: string;
}) {
  const query = useFounderInbox(group);
  const [params, setParams] = useUrlParams();
  return (
    <QueryView query={query} skeleton="cards">
      {(inbox) => {
        const open = inbox.items.find((i) => i.key === params["item"]);
        return (
          <>
            <NeedsYouList title={title} items={needsYou(inbox.items, page)} empty={empty} />
            {open && <FounderPanel item={open} onClose={() => setParams({ item: undefined })} />}
          </>
        );
      }}
    </QueryView>
  );
}
