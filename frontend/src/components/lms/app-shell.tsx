import { Fragment, useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { Bell, ChevronDown, Ellipsis, KeyRound, LogOut, ShieldCheck, User } from "lucide-react";
import { useNavCounts, type NavCounts } from "@/api/nav";
import type { Workspace } from "@/api/types";
import { useAuth } from "@/auth/auth";
import { useActing } from "@/auth/acting";
import { NAV, isNavActive, homeWorkspace, mobileBarItems, workspaceForPath, type NavItem } from "@/auth/access";
import { ActingAs } from "@/components/lms/acting-as";
import { NotificationBell } from "@/components/lms/notification-bell";
import { CommandPalette, SearchButton } from "@/components/lms/command-palette";
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
import { useDocumentLanguage, useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/** Notification centre per workspace (nothing is sent to the founder). */
const NOTIFICATIONS: Partial<Record<Workspace, string>> = {
  student: "/notifications",
  trainer: "/trainer/notifications",
  branch: "/branch/notifications",
  admin: "/admin/notifications",
};

/** The count on a navigation item: how many things wait for the person there. Nothing is shown for zero. */
function NavBadge({ count, className }: { count: number | undefined; className?: string }) {
  if (!count) return null;
  return (
    <span
      data-testid="nav-badge"
      aria-hidden
      className={cn("grid min-w-5 place-items-center rounded-full bg-primary px-1.5 text-[11px] font-semibold leading-5 text-primary-foreground", className)}
    >
      {count > 99 ? "99+" : count}
    </span>
  );
}

/** The count read out as the link's description, outside the link so the link's own name stays the page name. */
function NavCount({ count, id }: { count: number | undefined; id: string }) {
  return count ? (
    <span id={id} className="sr-only">
      {count} waiting
    </span>
  ) : null;
}

const badgeId = (area: string, item: NavItem) => `nav-count-${area}-${item.to.replace(/\W+/g, "-")}`;

/** Group heading above the first item of each group. */
function GroupHeading({ items, index }: { items: NavItem[]; index: number }) {
  const group = items[index].group;
  if (!group || group === items[index - 1]?.group) return null;
  return <p className="px-3 pb-1 pt-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{group}</p>;
}

/** Header + workspace sidebar + phone bottom bar around every signed-in screen. */
export function AppShell({ children }: { children: ReactNode }) {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const navigate = useNavigate();
  const { profile, workspaces, signOut } = useAuth();
  const t = useT();
  const [moreOpen, setMoreOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const workspace = workspaceForPath(path) ?? homeWorkspace(profile?.home_route);
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
  const { canPick, branchId } = useActing(workspace);
  const counts: NavCounts = useNavCounts(workspace, branchId).data ?? {};
  const countOf = (item: NavItem) => (item.badgeKey ? counts[item.badgeKey] : undefined);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

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
          {workspaces.length > 1 || canPick ? (
            <ActingAs workspace={workspace} workspaces={workspaces} />
          ) : (
            <span className="hidden truncate rounded bg-navy-muted px-2 py-0.5 text-xs lg:inline">
              {roleLabel} · {branchLabel}
            </span>
          )}
          <div className="ml-auto flex min-w-0 items-center gap-2">
            {translated && <LanguageToggle />}
            <SearchButton onClick={() => setSearchOpen(true)} />
            {bell && <NotificationBell inbox={bell} label={translated ? t("notifications") : "Notifications"} />}
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
                <DropdownMenuItem asChild>
                  <Link to={profile?.student ? "/profile" : "/account/profile"}>
                    <User />
                    {profile?.student ? t("profile") : "Profile"}
                  </Link>
                </DropdownMenuItem>
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
        <aside className="hidden w-60 shrink-0 border-r bg-card md:block">
          <nav aria-label="Main" className="sticky top-14 h-[calc(100vh-3.5rem)] overflow-y-auto p-3">
            <ul className="space-y-0.5">
              {items.map((item, index) => (
                <li key={item.to}>
                  <GroupHeading items={items} index={index} />
                  <Link
                    to={item.to}
                    aria-current={isNavActive(path, item.to) ? "page" : undefined}
                    aria-describedby={countOf(item) ? badgeId("side", item) : undefined}
                    className={cn(
                      "tap flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm",
                      isNavActive(path, item.to) ? "bg-accent font-semibold text-accent-foreground" : "text-foreground hover:bg-muted",
                    )}
                  >
                    <item.icon className="size-4 shrink-0" aria-hidden />
                    <span className="min-w-0 flex-1">{label(item)}</span>
                    <NavBadge count={countOf(item)} />
                  </Link>
                  <NavCount count={countOf(item)} id={badgeId("side", item)} />
                </li>
              ))}
            </ul>
          </nav>
        </aside>
        <main id="main" className="min-w-0 flex-1 px-3 pb-28 pt-4 sm:px-6 md:pb-10">
          {children}
        </main>
      </div>

      <nav aria-label="Bottom" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t bg-card md:hidden">
        {barItems.map((item) => (
          <Fragment key={item.to}>
            <Link
              to={item.to}
              aria-current={isNavActive(path, item.to) ? "page" : undefined}
              aria-describedby={countOf(item) ? badgeId("bar", item) : undefined}
              className={cn(
                "tap flex flex-col items-center justify-center gap-0.5 px-1 py-1.5 text-[11px] leading-tight",
                isNavActive(path, item.to) ? "font-semibold text-primary" : "text-muted-foreground",
              )}
            >
              <span className="relative">
                <item.icon className="size-5" aria-hidden />
                <NavBadge count={countOf(item)} className="absolute -right-3 -top-2 min-w-4 px-1 text-[10px] leading-4" />
              </span>
              <span className="text-center">{label(item)}</span>
            </Link>
            <NavCount count={countOf(item)} id={badgeId("bar", item)} />
          </Fragment>
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
          {(() => {
            const more = items.filter((item) => !barItems.includes(item));
            return (
              <ul className="mt-2 grid grid-cols-2 gap-2">
                {more.map((item, index) => (
                  <li key={item.to} className="contents">
                    {item.group && item.group !== more[index - 1]?.group && (
                      <p className="col-span-2 pt-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{item.group}</p>
                    )}
                    <Link
                      to={item.to}
                      onClick={() => setMoreOpen(false)}
                      aria-describedby={countOf(item) ? badgeId("more", item) : undefined}
                      className="tap flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"
                    >
                      <item.icon className="size-4 shrink-0" aria-hidden />
                      <span className="min-w-0 flex-1">{label(item)}</span>
                      <NavBadge count={countOf(item)} />
                    </Link>
                    <NavCount count={countOf(item)} id={badgeId("more", item)} />
                  </li>
                ))}
              </ul>
            );
          })()}
        </SheetContent>
      </Sheet>

      <CommandPalette open={searchOpen} onOpenChange={setSearchOpen} workspace={workspace} workspaces={workspaces} label={label} />
    </div>
  );
}
