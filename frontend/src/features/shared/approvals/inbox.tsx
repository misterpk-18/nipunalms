/**
 * The one approvals inbox (role separation 7.8): a "Needs you" list with one row and one button per item; the button opens the item in a
 * side panel on the same page. The Founder's Home and Certificate decisions, the Super Admin's Approvals page and the Branch Manager's
 * section in Completion all render this component; the route says which `kinds` to show. An item the person raised themselves is
 * listed without a decision (the API says `can_decide: false`): nobody decides their own request.
 */
import { useFounderInbox, type InboxGroup, type InboxItem, type InboxKind } from "@/api/founder";
import { NeedsYouList, type NeedsYouItem } from "@/components/lms/needs-you-list";
import { QueryView } from "@/components/lms/ui";
import { useUrlParams } from "@/features/shared/url-state";
import { ageText } from "@/features/shared/format";
import { InboxPanel } from "./panel";

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
    where:
      [
        item.where,
        item.from_branch_manager ? "A Branch Manager's own request" : null,
        item.can_decide ? null : "You asked for this: an independent approver decides it",
      ]
        .filter(Boolean)
        .join(" · ") || undefined,
    age: waited(item),
    to: page,
    search: { item: item.key },
    action: item.can_decide ? item.action : "View",
  }));

export function ApprovalsInbox({
  page,
  group,
  kinds,
  title = "Needs you",
  empty = "Nothing is waiting for you. New items appear here as they come in.",
}: {
  /** The path of the page this list is on, so a button opens the panel there. */
  page: string;
  group?: InboxGroup;
  /** Show only these kinds (the Branch Manager's section: certificate requests). All kinds when left out. */
  kinds?: InboxKind[];
  title?: string;
  empty?: string;
}) {
  const query = useFounderInbox(group);
  const [params, setParams] = useUrlParams();
  return (
    <QueryView query={query} skeleton="cards">
      {(inbox) => {
        const items = kinds ? inbox.items.filter((i) => kinds.includes(i.kind)) : inbox.items;
        const open = items.find((i) => i.key === params["item"]);
        return (
          <>
            <NeedsYouList title={title} items={needsYou(items, page)} empty={empty} />
            {open && <InboxPanel item={open} onClose={() => setParams({ item: undefined })} />}
          </>
        );
      }}
    </QueryView>
  );
}
