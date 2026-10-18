import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Award, GraduationCap, Search, Users, type LucideIcon } from "lucide-react";
import type { SearchRecord } from "@/api/nav";
import { useRecordSearch } from "@/api/nav";
import type { Workspace } from "@/api/types";
import { NAV, STUDENT_ACCOUNT, type NavItem } from "@/auth/access";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

const RECORD_ICONS: Record<SearchRecord["kind"], LucideIcon> = { student: GraduationCap, batch: Users, certificate: Award };
const RECORD_GROUPS: Record<SearchRecord["kind"], string> = { student: "Students", batch: "Batches", certificate: "Certificates" };

/** Where a found record opens, per role: every role stays inside its own workspace (nothing sends the Super Admin or Founder to /branch/*). */
const RECORD_TARGETS: Record<Workspace, Record<SearchRecord["kind"], (id: number) => string>> = {
  student: { student: () => "/dashboard", batch: () => "/dashboard", certificate: () => "/certificates" },
  trainer: { student: (id) => `/trainer/students/${id}`, batch: (id) => `/trainer/batches/${id}`, certificate: () => "/trainer" },
  branch: { student: () => "/branch/progress", batch: (id) => `/branch/batches/${id}`, certificate: () => "/branch/completion" },
  admin: { student: (id) => `/admin/students/${id}`, batch: (id) => `/admin/batches/${id}`, certificate: () => "/admin/approvals" },
  founder: { student: (id) => `/founder/students/${id}`, batch: (id) => `/founder/batches/${id}`, certificate: () => "/founder/certificates" },
};

const recordTarget = (kind: SearchRecord["kind"], workspace: Workspace, id: number) => RECORD_TARGETS[workspace][kind](id);

/** Ctrl/Cmd+K: jump to a page of the signed-in role's workspace, or find a student, batch or certificate they may open. */
export function CommandPalette({
  open,
  onOpenChange,
  workspace,
  label,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspace: Workspace;
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
    () => (workspace === "student" ? [...NAV[workspace], STUDENT_ACCOUNT] : NAV[workspace]).map((item) => ({ ...item, title: label(item) })),
    [workspace, label],
  );
  const shownPages = pages.filter((p) => !needle || `${p.title} ${p.group ?? ""}`.toLowerCase().includes(needle)).slice(0, needle ? 12 : 8);

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
                  <CommandItem key={p.to} value={p.to} onSelect={() => go(p.to)}>
                    <p.icon className="mr-2 size-4 shrink-0" aria-hidden />
                    <span className="truncate">{p.title}</span>
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
