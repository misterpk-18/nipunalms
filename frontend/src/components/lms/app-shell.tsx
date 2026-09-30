import { useState, type ReactNode } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { Bell, ChevronDown, Ellipsis, KeyRound, LogOut, ShieldCheck, User } from "lucide-react";
import type { Workspace } from "@/api/types";
import { useAuth } from "@/auth/auth";
import { NAV, WORKSPACE_HOME, WORKSPACE_LABELS, isNavActive, mobileBarItems, workspaceForPath, type NavItem } from "@/auth/access";
import { LanguageToggle } from "@/components/lms/language-toggle";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useNotificationOverview } from "@/api/notifications";
import { useDocumentLanguage, useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/** Notification centre per workspace (only these two have one). */
const NOTIFICATIONS: Partial<Record<Workspace, string>> = { student: "/notifications", trainer: "/trainer/notifications" };

/** Header + workspace sidebar + phone bottom bar around every signed-in screen. */
export function AppShell({ children }: { children: ReactNode }) {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const navigate = useNavigate();
  const { profile, workspaces, signOut } = useAuth();
  const t = useT();
  const [moreOpen, setMoreOpen] = useState(false);
  const workspace = workspaceForPath(path) ?? "student";
  const translated = workspace === "student";
  useDocumentLanguage(translated);

  const items = NAV[workspace];
  const barItems = mobileBarItems(workspace);
  const label = (item: NavItem) => (translated && item.tkey ? t(item.tkey) : item.label);
  const scopes = profile?.scopes ?? [];
  const roleLabel = [...new Set(scopes.map((s) => s.role_name))].join(" · ");
  const branchLabel = scopes.some((s) => s.is_company_wide) ? "All authorised branches" : [...new Set(scopes.map((s) => s.branch_name))].join(", ");
  const fullName = profile?.user.full_name ?? "";
  const bell = NOTIFICATIONS[workspace];
  const unread = useNotificationOverview({ enabled: Boolean(bell) }).data?.unread ?? 0;

  const exit = async () => {
    await signOut();
    void navigate({ to: "/login" });
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b bg-navy text-navy-foreground">
        <div className="flex h-14 items-center gap-2 px-3 sm:px-5">
          <Link to={profile?.home_route ?? "/"} className="flex shrink-0 items-center gap-2 font-semibold">
            <span className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck className="size-5" aria-hidden />
            </span>
            <span className="hidden sm:inline">Nipuna LMS</span>
          </Link>
          <span className="hidden truncate rounded bg-navy-muted px-2 py-0.5 text-xs lg:inline">
            {roleLabel} · {branchLabel}
          </span>
          <div className="ml-auto flex min-w-0 items-center gap-2">
            {translated && <LanguageToggle />}
            {workspaces.length > 1 && (
              <label className="flex min-w-0 items-center gap-1.5 rounded-lg border border-navy-muted px-2 text-xs">
                <span className="hidden sm:inline">Workspace</span>
                <select
                  aria-label="Workspace"
                  value={workspace}
                  onChange={(e) => void navigate({ to: WORKSPACE_HOME[e.target.value as Workspace] })}
                  className="tap min-w-0 max-w-[10rem] rounded bg-navy px-1 text-xs font-medium text-navy-foreground sm:max-w-none"
                >
                  {workspaces.map((w) => (
                    <option key={w} value={w}>
                      {WORKSPACE_LABELS[w]}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {bell && (
              <Link
                to={bell}
                aria-label={translated ? t("notifications") : "Notifications"}
                className="tap relative grid place-items-center rounded-lg hover:bg-navy-muted"
              >
                <Bell className="size-5" aria-hidden />
                {unread > 0 && (
                  <span
                    data-testid="unread-count"
                    className="absolute right-0.5 top-0.5 grid min-w-4 place-items-center rounded-full bg-danger px-1 text-[10px] font-semibold leading-4 text-white"
                  >
                    {unread > 99 ? "99+" : unread}
                  </span>
                )}
              </Link>
            )}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="tap flex items-center gap-1 rounded-lg px-1 hover:bg-navy-muted"
                  aria-label="Account menu"
                  title={`${fullName} · ${roleLabel}`}
                >
                  <span className="grid size-8 place-items-center rounded-full bg-navy-muted text-xs font-semibold" aria-hidden>
                    {fullName.slice(0, 1).toUpperCase()}
                  </span>
                  <ChevronDown className="size-4" aria-hidden />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-60">
                <DropdownMenuLabel>
                  <div className="text-sm">{fullName}</div>
                  <div className="text-xs font-normal text-muted-foreground">{profile?.student?.student_code ?? profile?.user.email}</div>
                  <div className="mt-0.5 text-xs font-normal text-muted-foreground">{roleLabel}</div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {profile?.student && (
                  <DropdownMenuItem asChild>
                    <Link to="/profile">
                      <User />
                      {t("profile")}
                    </Link>
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem asChild>
                  <Link to="/change-password">
                    <KeyRound />
                    Change password
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => void exit()}>
                  <LogOut />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      <div className="flex">
        <nav aria-label="Main" className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-60 shrink-0 overflow-y-auto border-r bg-card p-3 md:block">
          <ul className="space-y-0.5">
            {items.map((item) => (
              <li key={item.to}>
                <Link
                  to={item.to}
                  aria-current={isNavActive(path, item.to) ? "page" : undefined}
                  className={cn(
                    "tap flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm",
                    isNavActive(path, item.to) ? "bg-accent font-semibold text-accent-foreground" : "text-foreground hover:bg-muted",
                  )}
                >
                  <item.icon className="size-4 shrink-0" aria-hidden />
                  {label(item)}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <main id="main" className="min-w-0 flex-1 px-3 pb-28 pt-4 sm:px-6 md:pb-10">
          {children}
        </main>
      </div>

      <nav aria-label="Bottom" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t bg-card md:hidden">
        {barItems.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            aria-current={isNavActive(path, item.to) ? "page" : undefined}
            className={cn(
              "tap flex flex-col items-center justify-center gap-0.5 px-1 py-1.5 text-[11px] leading-tight",
              isNavActive(path, item.to) ? "font-semibold text-primary" : "text-muted-foreground",
            )}
          >
            <item.icon className="size-5" aria-hidden />
            <span className="text-center">{label(item)}</span>
          </Link>
        ))}
        <button
          onClick={() => setMoreOpen(true)}
          aria-expanded={moreOpen}
          className="tap flex flex-col items-center justify-center gap-0.5 py-1.5 text-[11px] text-muted-foreground"
        >
          <Ellipsis className="size-5" aria-hidden />
          {translated ? t("more") : "More"}
        </button>
      </nav>

      <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
        <SheetContent side="bottom" aria-describedby={undefined} className="max-h-[75vh] overflow-y-auto rounded-t-2xl p-4 md:hidden">
          <SheetHeader className="p-0">
            <SheetTitle>{translated ? t("more") : "More"}</SheetTitle>
          </SheetHeader>
          <ul className="mt-2 grid grid-cols-2 gap-2">
            {items
              .filter((item) => !barItems.includes(item))
              .map((item) => (
                <li key={item.to}>
                  <Link to={item.to} onClick={() => setMoreOpen(false)} className="tap flex items-center gap-2 rounded-lg border px-3 py-2 text-sm">
                    <item.icon className="size-4" aria-hidden />
                    {label(item)}
                  </Link>
                </li>
              ))}
          </ul>
        </SheetContent>
      </Sheet>
    </div>
  );
}
