import { Check, ChevronDown } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";
import type { Workspace } from "@/api/types";
import { useActing } from "@/auth/acting";
import { WORKSPACE_DESCRIPTIONS, WORKSPACE_HOME, WORKSPACE_LABELS } from "@/auth/access";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/**
 * The header's "Acting as: <role> ▾" switcher for people with more than one workspace, or more than one branch in the Branch
 * Manager workspace. One line says what each role is for; the branch picker narrows the counts and cards to one branch.
 */
export function ActingAs({ workspace, workspaces }: { workspace: Workspace; workspaces: Workspace[] }) {
  const navigate = useNavigate();
  const { branches, canPick, branchId, setBranchId } = useActing(workspace);
  const branchName = branchId === null ? "All branches" : (branches.find((b) => b.branch_id === branchId)?.branch_name ?? "All branches");

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          aria-label="Acting as"
          className="tap flex min-w-0 max-w-[11rem] items-center gap-1.5 rounded-lg border border-navy-muted px-2 text-xs hover:bg-navy-muted sm:max-w-none"
        >
          <span className="hidden text-navy-foreground/70 sm:inline">Acting as</span>
          <span className="truncate font-semibold">
            {WORKSPACE_LABELS[workspace]}
            {canPick && <span className="hidden font-normal md:inline"> · {branchName}</span>}
          </span>
          <ChevronDown className="size-4 shrink-0" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">Acting as</DropdownMenuLabel>
        {workspaces.map((w) => (
          <DropdownMenuItem key={w} onSelect={() => void navigate({ to: WORKSPACE_HOME[w] })} className="items-start gap-2">
            <Check className={w === workspace ? "mt-0.5 size-4 shrink-0" : "mt-0.5 size-4 shrink-0 opacity-0"} aria-hidden />
            <span>
              <span className="block text-sm font-medium">{WORKSPACE_LABELS[w]}</span>
              <span className="block text-xs text-muted-foreground">{WORKSPACE_DESCRIPTIONS[w]}</span>
            </span>
          </DropdownMenuItem>
        ))}
        {canPick && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">Branch</DropdownMenuLabel>
            {[{ id: null, name: "All branches" }, ...branches.map((b) => ({ id: b.branch_id, name: b.branch_name }))].map((b) => (
              <DropdownMenuItem key={b.id ?? "all"} onSelect={() => setBranchId(b.id)} className="gap-2">
                <Check className={b.id === branchId ? "size-4 shrink-0" : "size-4 shrink-0 opacity-0"} aria-hidden />
                {b.name}
              </DropdownMenuItem>
            ))}
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
