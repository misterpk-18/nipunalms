/** The Update action on an exception row: a reason dialog that logs a recovery step, plus small shared cells. */
import { Link } from "@tanstack/react-router";
import { exceptionKeys, exceptionsApi, type ExceptionItem } from "@/api/exceptions";
import { StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { ReasonDialog } from "@/features/shared/reason-dialog";
import { useApiMutation } from "@/lib/mutation";

export function RecoveryStepButton({ item }: { item: ExceptionItem }) {
  const log = useApiMutation((reason: string) => exceptionsApi.logStep(item, reason), {
    success: "Recovery step logged.",
    invalidate: [exceptionKeys.all, ["dashboard"]],
  });
  return (
    <ReasonDialog
      trigger={
        <Button size="sm" variant="outline" aria-label={`Update ${item.reference}`}>
          Update
        </Button>
      }
      title={`Log a recovery step — ${item.reference}`}
      description={`${item.title}. The step is audited, and you become the named owner if it has none.`}
      label="What was done, or will be done"
      confirmLabel="Log recovery step"
      busy={log.isPending}
      onSubmit={(reason) => log.mutateAsync(reason)}
    />
  );
}

export function OwnerCell({ item }: { item: ExceptionItem }) {
  if (item.owner) return <span>{item.owner.full_name}</span>;
  return (
    <div>
      <StatusBadge tone="warning">Awaiting named owner</StatusBadge>
      {item.owner_label && <p className="mt-1 text-xs text-muted-foreground">Recovery owner: {item.owner_label}</p>}
    </div>
  );
}

export function ItemCell({ item }: { item: ExceptionItem }) {
  return (
    <div>
      <Link to={item.link} className="font-medium underline-offset-2 hover:underline">
        {item.title}
      </Link>
      {item.detail && <p className="text-xs text-muted-foreground">{item.detail}</p>}
      {item.step_count > 0 && (
        <p className="text-xs text-muted-foreground">
          {item.step_count} recovery step{item.step_count === 1 ? "" : "s"} logged
        </p>
      )}
    </div>
  );
}
