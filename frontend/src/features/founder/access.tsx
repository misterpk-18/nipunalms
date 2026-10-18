/** Access extensions beyond the Branch Manager's limit: the Founder decides, with the Branch Manager's recommendation beside each request. */
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { contentApi, type StaffExtensionRequest } from "@/api/content";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, QueryView, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { useUrlParams } from "@/features/shared/url-state";
import { Pager } from "@/features/shared/pager";
import { fmtDate } from "@/features/shared/format";
import { AccessPanel } from "@/features/shared/approvals/panel-access";

const KIND = { Recording: "recordings", Material: "materials", Both: "recordings and materials" } as const;
const PER_PAGE = 15;

export function FounderAccess() {
  const [page, setPage] = useState(1);
  const [params, setParams] = useUrlParams();
  const query = useQuery({
    queryKey: ["access-extensions", "founder", page],
    queryFn: () => contentApi.staffRequests({ status: "Pending", needs_exception: true, page, per_page: PER_PAGE }),
    placeholderData: keepPreviousData,
  });
  const open = query.data?.data.find((r) => `access_extension-${r.request_id}` === params["item"]);
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHead
        title="Access extensions"
        description="Students who ask for more time on recordings or materials after their two years. The Branch Manager recommends, you decide."
      />
      <QueryView
        query={query}
        skeleton="cards"
        isEmpty={(r) => r.data.length === 0}
        empty="No request is waiting. When a student asks for access beyond two years, it appears here."
      >
        {(result) => (
          <div className="space-y-3">
            <ul className="space-y-3" aria-label="Access extension requests">
              {result.data.map((r) => (
                <RequestRow key={r.request_id} request={r} onOpen={() => setParams({ item: `access_extension-${r.request_id}` })} />
              ))}
            </ul>
            <Pager meta={result.meta} onPage={setPage} noun="requests" />
          </div>
        )}
      </QueryView>
      <HowThisWorks>
        <p>
          Within two years of the joining date a Branch Manager decides. After that it is your call: the Branch Manager adds a recommendation first, and you
          choose the new end date. The student is told either way.
        </p>
      </HowThisWorks>
      {open && <AccessPanel key={open.request_id} request={open} onClose={() => setParams({ item: undefined })} />}
    </div>
  );
}

function RequestRow({ request, onOpen }: { request: StaffExtensionRequest; onOpen: () => void }) {
  const rec = request.recommendation;
  return (
    <li className="space-y-2 rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium">{request.student.full_name}</p>
          <p className="text-sm text-muted-foreground">
            {request.enrolment.course.title} · asks for {KIND[request.scope]} · {request.branch.branch_name}
          </p>
        </div>
        {rec ? (
          <Tag tone={rec.decision === "approve" ? "success" : "warning"}>
            {rec.decision === "approve" ? "Branch Manager recommends approving" : "Branch Manager recommends rejecting"}
          </Tag>
        ) : (
          <Tag tone="neutral">Waiting for the Branch Manager's recommendation</Tag>
        )}
      </div>
      <p className="text-sm">“{request.reason}”</p>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">Access now ends on {fmtDate(request.current_end_date)}.</p>
        <Button size="sm" onClick={onOpen}>
          Review
        </Button>
      </div>
    </li>
  );
}
