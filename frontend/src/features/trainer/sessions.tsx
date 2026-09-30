import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi } from "@/api/delivery";
import { Note, PageHead, PillTabs, QueryView, Section } from "@/components/lms/ui";
import { RequestsPanel, SessionsTable } from "@/features/shared/sessions";

const TABS = ["Upcoming", "Delivered / closed", "All"] as const;

export function TrainerSessions() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Upcoming");
  const query = useQuery({
    queryKey: ["delivery", "sessions", "trainer", tab],
    queryFn: () => deliveryApi.sessions(tab === "Upcoming" ? { upcoming: true } : {}),
    select: (page) =>
      tab === "Delivered / closed" ? { ...page, data: page.data.filter((s) => s.state === "Delivered" || s.state === "Cancelled").reverse() } : page,
  });
  return (
    <>
      <PageHead title="Class sessions" description="Scheduled vs actual Class Session — start a class, mark it delivered, or ask for a reschedule." />
      <PillTabs label="Sessions" tabs={TABS} value={tab} onChange={setTab} />
      <QueryView query={query}>{(page) => <SessionsTable caption="Class sessions" rows={page.data} actions={{ manager: false, trainer: true }} />}</QueryView>
      <Section className="mt-6" title="My reschedule requests">
        <RequestsPanel manager={false} />
      </Section>
      <div className="mt-4">
        <Note>
          Start opens up to 60 minutes before the class. A session only counts as taught once you mark it Delivered; a class that is cancelled or moved is never
          a student absence.
        </Note>
      </div>
    </>
  );
}
