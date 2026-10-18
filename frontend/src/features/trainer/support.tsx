import { useState } from "react";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { SupportDesk } from "@/features/shared/support-desk";
import { FlagStudentDialog } from "./flag-student";

/**
 * Trainer support, kept simple: raise a request about a student, reply, and see its status and who owns it. Passing a request
 * up (escalate) sits under "More". To flag a student you are looking at, use Flag on their row or page.
 */
export function TrainerSupport() {
  const [raising, setRaising] = useState(false);
  return (
    <div className="mx-auto max-w-6xl">
      <PageHead
        title="Support"
        description="Requests you raised about your students, or that are with you. Open one to reply or change its status."
        actions={<Button onClick={() => setRaising(true)}>Raise a request</Button>}
      />
      <SupportDesk
        simple
        canReassign={false}
        canEscalate
        caption="Support requests"
        empty="No support request is open for your students. To raise one, use Raise a request, or Flag on a student's row in Students."
        base={{ mine: true }}
      />
      <div className="mt-4">
        <HowThisWorks>
          <p>
            A request goes to the right owner for its kind of problem, usually your Branch Manager. The student is told when you raise one for them and when it
            is answered. Contact details and fees are not shown to trainers. If a request is stuck, open it, choose More and escalate it.
          </p>
        </HowThisWorks>
      </div>
      {raising && <FlagStudentDialog open onOpenChange={(open) => !open && setRaising(false)} />}
    </div>
  );
}
