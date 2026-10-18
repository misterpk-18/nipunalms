/** How and where students pay at a branch: the text the student's "Next payment" card shows. A Branch Manager sets it for the branch of the session; Super Admin and Founder pick any branch. */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { branchApi } from "@/api/branch";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect } from "@/components/lms/forms";
import { QueryView } from "@/components/lms/ui";
import { useApiMutation } from "@/lib/mutation";

type BranchChoice = { branch_id: number; branch_name: string };

/** `branches` are the branches this person may edit; with more than one a picker shows. */
export function PaymentInstructions({ branches, initialBranchId }: { branches: BranchChoice[]; initialBranchId?: number | null }) {
  const [picked, setPicked] = useState<number | null>(null);
  const target = picked ?? initialBranchId ?? branches[0]?.branch_id ?? null;
  const query = useQuery({
    queryKey: ["branch", "payment-instructions", target],
    queryFn: () => branchApi.paymentInstructions(target!),
    enabled: target !== null,
  });
  const [text, setText] = useState("");
  useEffect(() => setText(query.data?.payment_instructions ?? ""), [query.data]);
  const save = useApiMutation((value: string | null) => branchApi.setPaymentInstructions(target!, value), {
    success: "Saved",
    next: "Students see this under Next payment in My Account",
    invalidate: [["branch", "payment-instructions"]],
  });
  if (target === null) return <p className="text-sm text-muted-foreground">No branch to set payment instructions for yet.</p>;
  const unchanged = text.trim() === (query.data?.payment_instructions ?? "").trim();
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Tell students where and how to pay at this branch. It shows on their Next payment card. Leave it empty to say "pay at the branch office".
      </p>
      {branches.length > 1 && (
        <div className="max-w-xs">
          <NativeSelect
            aria-label="Branch for the payment instructions"
            options={branches.map((b) => ({ value: b.branch_id, label: b.branch_name }))}
            value={target}
            onChange={(e) => setPicked(Number(e.target.value))}
          />
        </div>
      )}
      <QueryView query={query} skeleton="cards">
        {() => (
          <>
            <Textarea
              aria-label="Payment instructions"
              rows={4}
              maxLength={1500}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="For example: UPI to nipuna@bank, or cash at the front desk 10:00 to 18:00"
            />
            <Button size="sm" disabled={save.isPending || unchanged} onClick={() => save.mutate(text.trim() || null)}>
              Save
            </Button>
          </>
        )}
      </QueryView>
    </div>
  );
}
