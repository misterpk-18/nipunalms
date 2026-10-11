import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi } from "@/api/delivery";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, PillTabs, QueryView, Section } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { RequestsPanel, SessionsTable } from "@/features/shared/sessions";

const TABS = ["Coming up", "Past"] as const;

/** The trainer's schedule and reschedule requests. A class is run from Today's flow ("Run class" opens it there). */
export function TrainerSessions() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Coming up");
  const query = useQuery({
    queryKey: ["delivery", "sessions", "trainer", tab],
    // Coming up also shows a class that was cancelled or moved, so you see why it is not on. Past: everything that has ended, newest first, including a class that never got its log (it shows "Add class log")
    queryFn: () => deliveryApi.sessions({ window: tab === "Coming up" ? "coming" : "past" }),
  });
  return (
    <div className="mx-auto max-w-6xl">
      <PageHead title="Sessions" description="Your class schedule. Open a class to run it, or ask your Branch Manager to move one." />
      <PillTabs label="Sessions" tabs={TABS} value={tab} onChange={setTab} />
      <QueryView
        query={query}
        isEmpty={(page) => page.data.length === 0}
        empty={tab === "Coming up" ? "No class is scheduled for you. Your Branch Manager adds classes to your batches." : "No class has ended yet."}
      >
        {(page) => <SessionsTable caption="Class sessions" rows={page.data} actions={{ manager: false, trainer: true }} />}
      </QueryView>
      <Section
        className="mt-6"
        title="Reschedule requests waiting"
        actions={
          <Button asChild size="sm" variant="outline">
            <Link to="/trainer/requests">All my requests</Link>
          </Button>
        }
      >
        <RequestsPanel manager={false} />
      </Section>
      <div className="mt-4">
        <HowThisWorks>
          <p>
            Run class opens the class on Today, where you start it, mark attendance and save the class log. A class counts as taught once you save its log. A
            class that is cancelled or moved is never counted as an absence for the students.
          </p>
          <p>To move a class, ask for a reschedule; your Branch Manager decides. The answer appears under My requests.</p>
        </HowThisWorks>
      </div>
    </div>
  );
}
