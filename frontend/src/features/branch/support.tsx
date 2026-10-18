/** Student support: the requests students raise (Needs action first, nearest reply deadline first). Access extensions have their own page. */
import { Navigate } from "@tanstack/react-router";
import { useAuth } from "@/auth/auth";
import { PageHead } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { SupportDesk } from "@/features/shared/support-desk";
import { useUrlParams } from "@/features/shared/url-state";

export function BranchSupport() {
  const { branchId } = useAuth();
  const [params, setParams] = useUrlParams();
  const request = Number(params["request"]) > 0 ? Number(params["request"]) : null;
  const student = Number(params["student"]) > 0 ? Number(params["student"]) : undefined;
  // The old "Access extensions" tab is its own page now
  if (params["tab"] === "extensions") return <Navigate to="/branch/extensions" replace />;
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead title="Student support" description="Questions and problems students have raised. Requests for more access time are under Access extensions." />
      {student && (
        <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          Showing the requests of one student.
          <Button size="sm" variant="outline" onClick={() => setParams({ student: undefined })}>
            Show everyone
          </Button>
        </p>
      )}
      <SupportDesk
        views
        canReassign
        canEscalate={false}
        caption="Support requests"
        empty="No support requests for your branch."
        branchId={branchId}
        {...(student ? { studentId: student } : {})}
        openId={request}
        onOpen={(id) => setParams({ request: id ?? undefined })}
      />
    </div>
  );
}
