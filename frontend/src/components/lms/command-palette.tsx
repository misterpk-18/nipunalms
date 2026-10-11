import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Award, GraduationCap, Search, Users, type LucideIcon } from "lucide-react";
import type { SearchRecord } from "@/api/nav";
import { useRecordSearch } from "@/api/nav";
import type { Workspace } from "@/api/types";
import { NAV, STUDENT_ACCOUNT, WORKSPACE_LABELS, type NavItem } from "@/auth/access";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

const RECORD_ICONS: Record<SearchRecord["kind"], LucideIcon> = { student: GraduationCap, batch: Users, certificate: Award };
const RECORD_GROUPS: Record<SearchRecord["kind"], string> = { student: "Students", batch: "Batches", certificate: "Certificates" };

/** The screen a found record opens: the list that holds it in the workspace the person is in (record pages arrive with their screens). */
function recordTarget(kind: SearchRecord["kind"], workspace: Workspace, id: number): string {
  // The trainer's student and batch pages are record pages (U13); the other workspaces open the list until their phases build them
  if (kind === "student") return workspace === "trainer" ? `/trainer/students/${id}` : workspace === "branch" ? "/branch/progress" : "/admin/students";
  if (kind === "batch") return workspace === "trainer" ? `/trainer/batches/${id}` : `/branch/batches/${id}`;
  return workspace === "founder" ? "/founder/certificates" : "/branch/certificates";
}

/** Ctrl/Cmd+K: jump to a page of any workspace the person holds, or find a student, batch or certificate they may open. */
export function CommandPalette({
  open,
  onOpenChange,
  workspace,
  workspaces,
  label,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspace: Workspace;
  workspaces: Workspace[];
  /** The label of a navigation item (translated for a student). */
  label: (item: NavItem) => string;
}) {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const records = useRecordSearch(open ? text : "").data ?? [];
  const needle = text.trim().toLowerCase();

  useEffect(() => {
    if (!open) setText("");
  }, [open]);

  const pages = useMemo(
    () => workspaces.flatMap((w) => (w === "student" ? [...NAV[w], STUDENT_ACCOUNT] : NAV[w]).map((item) => ({ ...item, workspace: w, title: label(item) }))),
    [workspaces, label],
  );
  const shownPages = pages
    .filter((p) => !needle || `${p.title} ${p.group ?? ""} ${WORKSPACE_LABELS[p.workspace]}`.toLowerCase().includes(needle))
    .slice(0, needle ? 12 : 8);

  const go = (to: string) => {
    onOpenChange(false);
    void navigate({ to });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden p-0">
        <DialogTitle className="sr-only">Search</DialogTitle>
        <DialogDescription className="sr-only">Find a page, student, batch or certificate</DialogDescription>
        <Command
          label="Search"
          shouldFilter={false}
          className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:text-muted-foreground [&_[cmdk-group]]:px-2 [&_[cmdk-item]]:px-2 [&_[cmdk-item]]:py-2.5"
        >
          <CommandInput value={text} onValueChange={setText} placeholder="Search pages, students, batches…" aria-label="Search" />
          <CommandList>
            <CommandEmpty>Nothing found. Try a name, a Student ID or a batch code.</CommandEmpty>
            {shownPages.length > 0 && (
              <CommandGroup heading="Pages">
                {shownPages.map((p) => (
                  <CommandItem key={`${p.workspace}:${p.to}`} value={`${p.workspace}:${p.to}`} onSelect={() => go(p.to)}>
                    <p.icon className="mr-2 size-4 shrink-0" aria-hidden />
                    <span className="truncate">{p.title}</span>
                    {workspaces.length > 1 && <span className="ml-auto pl-3 text-xs text-muted-foreground">{WORKSPACE_LABELS[p.workspace]}</span>}
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {(["student", "batch", "certificate"] as const).map((kind) => {
              const rows = records.filter((r) => r.kind === kind);
              const Icon = RECORD_ICONS[kind];
              return (
                rows.length > 0 && (
                  <CommandGroup key={kind} heading={RECORD_GROUPS[kind]}>
                    {rows.map((r) => (
                      <CommandItem key={`${kind}:${r.id}`} value={`${kind}:${r.id}`} onSelect={() => go(recordTarget(kind, workspace, r.id))}>
                        <Icon className="mr-2 size-4 shrink-0" aria-hidden />
                        <span className="min-w-0">
                          <span className="block truncate text-sm">{r.title}</span>
                          <span className="block truncate text-xs text-muted-foreground">{r.subtitle}</span>
                        </span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )
              );
            })}
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}

/** The header's search button: the shortcut hint on desktop, an icon on a phone. */
export function SearchButton({ onClick }: { onClick: () => void }) {
  const mac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
  return (
    <button onClick={onClick} aria-label="Search" className="tap flex items-center gap-2 rounded-lg border border-navy-muted px-2 text-xs hover:bg-navy-muted">
      <Search className="size-4" aria-hidden />
      <span className="hidden lg:inline">Search</span>
      <kbd className="hidden rounded bg-navy-muted px-1.5 py-0.5 font-sans text-[10px] lg:inline">{mac ? "⌘K" : "Ctrl K"}</kbd>
    </button>
  );
}
