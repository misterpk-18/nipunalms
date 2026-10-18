/** Opens the side panel for one inbox item, whatever kind it is. `canDecide` false (the person raised it) shows the record without the decision buttons. */
import type { InboxItem } from "@/api/founder";
import { AccessPanel } from "./panel-access";
import { CertificateRequestPanel, FeeExceptionPanel } from "./panel-certificate";
import { AiBudgetPanel, BranchManagerRequestPanel } from "./panel-other";

export function InboxPanel({ item, onClose }: { item: InboxItem; onClose: () => void }) {
  switch (item.kind) {
    case "certificate":
      return (
        <CertificateRequestPanel
          key={item.key}
          request={item.detail}
          fromBranchManager={item.from_branch_manager}
          canDecide={item.can_decide}
          onClose={onClose}
        />
      );
    case "fee_exception":
      return (
        <FeeExceptionPanel key={item.key} exception={item.detail} fromBranchManager={item.from_branch_manager} canDecide={item.can_decide} onClose={onClose} />
      );
    case "access_extension":
      return <AccessPanel key={item.key} request={item.detail} onClose={onClose} />;
    case "ai_budget":
      return <AiBudgetPanel key={item.key} detail={item.detail} onClose={onClose} />;
    case "bm_reschedule":
    case "bm_correction":
      return <BranchManagerRequestPanel key={item.key} item={item} onClose={onClose} />;
  }
}
