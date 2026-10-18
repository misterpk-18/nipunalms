/** Student support: the requests students raise (Needs action first, nearest reply deadline first) and the access-extension requests. */
import { useQuery } from "@tanstack/react-query";
import { contentApi } from "@/api/content";
import { supportApi } from "@/api/support";
import { useAuth } from "@/auth/auth";
import { PageHead, PillTabs } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { SupportDesk } from "@/features/shared/support-desk";
import { pickTab, useUrlParams } from "./attendance-url";
import { ExtensionsTab } from "./extensions-requests";

const TABS = ["requests", "extensions"] as const;
const LABELS = { requests: "Requests", extensions: "Access extensions" };

export function BranchSupport() {
  const { branchId } = useAuth();
  const [params, setParams] = useUrlParams();
  const tab = pickTab(TABS, params["tab"]);
  const request = Number(params["request"]) > 0 ? Number(params["request"]) : null;
  const student = Number(params["student"]) > 0 ? Number(params["student"]) : undefined;
  const needsAction = useQuery({
    queryKey: ["support", "counts", { ...(branchId ? { branch_id: branchId } : {}) }],
    queryFn: () => supportApi.counts(branchId ? { branch_id: branchId } : {}),
  });
  const waiting = useQuery({
    queryKey: ["access-extensions", "waiting-count", branchId],
    queryFn: () => contentApi.staffRequests({ status: "Pending", per_page: 1, branch_id: branchId }),
  });
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead
        title="Student support"
        description="Questions and problems students have raised, and requests to extend their access to recordings and materials."
      />
      <PillTabs
        label="Student support"
        tabs={TABS}
        labels={LABELS}
        value={tab}
        onChange={(next) => setParams({ tab: next === "requests" ? undefined : next, request: undefined })}
        counts={{ requests: needsAction.data?.needs_action ?? 0, extensions: waiting.data?.meta.total ?? 0 }}
      />
      {tab === "requests" ? (
        <>
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
            caption="Support requests"
            empty="No support requests for your branch."
            branchId={branchId}
            {...(student ? { studentId: student } : {})}
            openId={request}
            onOpen={(id) => setParams({ request: id ?? undefined })}
          />
        </>
      ) : (
        <ExtensionsTab branchId={branchId} />
      )}
    </div>
  );
}
