/**
 * Workspace access and navigation. The path decides which workspace a screen belongs to (same rule as the
 * prototype); the profile's `workspaces` (from the API, already expanded per role) decides who may open it.
 */
import {
  Activity,
  Award,
  BookOpen,
  Briefcase,
  CalendarCheck,
  CalendarDays,
  CircleCheck,
  ClipboardCheck,
  ClipboardList,
  FileClock,
  FileQuestion,
  FolderOpen,
  GraduationCap,
  Hourglass,
  House,
  Library,
  LifeBuoy,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  TriangleAlert,
  User,
  UserCog,
  Users,
  Video,
  ChartColumn,
  type LucideIcon,
} from "lucide-react";
import type { Workspace } from "@/api/types";
import type { TranslationKey } from "@/lib/i18n";

export const PUBLIC_PATHS = ["/login", "/activate", "/forgot-password"];

/** Public screens that stay open after sign-in: activation signs the person in and then shows its own success step. */
export const STAY_WHEN_SIGNED_IN = ["/activate"];

/** Open to everyone, signed in or not, without the app shell: public certificate verification (Module 22 §9). */
export const OPEN_PATH_ROOTS = ["/verify"];
export const isOpenPath = (path: string) => OPEN_PATH_ROOTS.some((root) => path === root || path.startsWith(`${root}/`));

/** Screens outside every workspace (no shell). */
const UNSCOPED_PATHS = [...PUBLIC_PATHS, ...OPEN_PATH_ROOTS, "/change-password"];

const isUnder = (path: string, root: string) => path === root || path.startsWith(`${root}/`);

/** Which workspace a path belongs to; null for the entry route, the sign-in / activation / password screens and the shared /account screens. */
export function workspaceForPath(path: string): Workspace | null {
  if (path === "/" || UNSCOPED_PATHS.some((p) => isUnder(path, p)) || isUnder(path, "/account")) return null;
  if (isUnder(path, "/trainer")) return "trainer";
  if (isUnder(path, "/branch")) return "branch";
  if (isUnder(path, "/admin")) return "admin";
  if (isUnder(path, "/founder")) return "founder";
  return "student";
}

/** The workspace whose navigation frames a shared screen (/account/*): the one the user lands in. */
export function homeWorkspace(homeRoute: string | undefined): Workspace {
  return workspaceForPath(homeRoute ?? "/dashboard") ?? "student";
}

export function canOpen(workspaces: Workspace[], workspace: Workspace | null): boolean {
  return workspace === null || workspaces.includes(workspace);
}

export const WORKSPACE_LABELS: Record<Workspace, string> = {
  student: "Student",
  trainer: "Trainer",
  branch: "Branch Manager",
  admin: "Super Admin",
  founder: "Founder / CEO",
};

export const WORKSPACE_HOME: Record<Workspace, string> = {
  student: "/dashboard",
  trainer: "/trainer",
  branch: "/branch",
  admin: "/admin",
  founder: "/founder",
};

/** `group` is the heading the item sits under; `badgeKey` names its count in `GET /me/nav-counts` (see api/nav.ts). */
export type NavItem = { to: string; label: string; icon: LucideIcon; tkey?: TranslationKey; group?: string; badgeKey?: string };

/** One line per workspace for the "Acting as" switcher: what you do in it. */
export const WORKSPACE_DESCRIPTIONS: Record<Workspace, string> = {
  student: "Your classes, tasks, results and certificates",
  trainer: "Run classes, mark attendance and grade work",
  branch: "Run a branch: batches, schedule, results and certificates",
  admin: "People and access, integrations and system health",
  founder: "Decisions waiting for you and company-wide figures",
};

const STUDENT_NAV: NavItem[] = [
  { to: "/dashboard", label: "Home", tkey: "home", icon: House },
  { to: "/my-courses", label: "My Learning", tkey: "myLearning", icon: BookOpen },
  { to: "/schedule", label: "Schedule", tkey: "schedule", icon: CalendarDays },
  { to: "/tasks", label: "Tasks & Tests", tkey: "tasksAndTests", icon: ClipboardList, badgeKey: "tasks" },
  { to: "/materials", label: "Class Materials", tkey: "classMaterials", icon: Video },
  { to: "/progress", label: "My Progress", tkey: "myProgress", icon: TrendingUp },
  { to: "/certificates", label: "Certificates", tkey: "certificates", icon: Award },
  { to: "/career", label: "Career", tkey: "career", icon: Briefcase },
  { to: "/ask-nipuna", label: "Ask Nipuna", tkey: "askNipuna", icon: Sparkles },
  { to: "/support", label: "Support", tkey: "support", icon: LifeBuoy, badgeKey: "support" },
];

/** My Account is opened from the avatar menu, not the sidebar; the phone "More" sheet and the search palette list it too. */
export const STUDENT_ACCOUNT: NavItem = { to: "/my-account", label: "My Account", tkey: "myAccount", icon: User };

const TRAINER_NAV: NavItem[] = [
  { to: "/trainer", label: "Today", icon: House, group: "Teach", badgeKey: "class_logs" },
  { to: "/trainer/sessions", label: "Sessions", icon: CalendarDays, group: "Teach" },
  { to: "/trainer/attendance", label: "Attendance", icon: CalendarCheck, group: "Teach", badgeKey: "attendance" },
  { to: "/trainer/requests", label: "My requests", icon: FileClock, group: "Teach" },
  { to: "/trainer/to-grade", label: "To grade", icon: ClipboardCheck, group: "Grade", badgeKey: "to_grade" },
  { to: "/trainer/assignments", label: "Assignments", icon: ClipboardList, group: "Grade" },
  { to: "/trainer/assessments", label: "Assessments", icon: FileQuestion, group: "Grade" },
  { to: "/trainer/content", label: "Content", icon: FolderOpen, group: "Grade" },
  { to: "/trainer/batches", label: "Batches", icon: Users, group: "People" },
  { to: "/trainer/students", label: "Students", icon: GraduationCap, group: "People" },
  { to: "/trainer/support", label: "Support", icon: LifeBuoy, group: "People", badgeKey: "support" },
  { to: "/trainer/reports", label: "Reports", icon: ChartColumn, group: "Insights" },
  { to: "/trainer/ask-nipuna", label: "Ask Nipuna", icon: Sparkles, group: "Insights" },
];

const BRANCH_NAV: NavItem[] = [
  { to: "/branch", label: "My work", icon: House, group: "Today", badgeKey: "my_work" },
  { to: "/branch/class-day", label: "Class day", icon: Video, group: "Today", badgeKey: "class_day" },
  { to: "/branch/batches", label: "Batches", icon: Users, group: "Batches & students" },
  { to: "/branch/waiting", label: "Waiting for a batch", icon: Hourglass, group: "Batches & students", badgeKey: "waiting" },
  { to: "/branch/schedule", label: "Schedule & calendar", icon: CalendarDays, group: "Batches & students", badgeKey: "schedule" },
  { to: "/branch/progress", label: "Attendance & progress", icon: TrendingUp, group: "Batches & students", badgeKey: "attendance" },
  { to: "/branch/curriculum", label: "Curriculum", icon: Library, group: "Teaching" },
  { to: "/branch/content", label: "Content & questions", icon: FolderOpen, group: "Teaching", badgeKey: "content_review" },
  { to: "/branch/results", label: "Marks & results", icon: ClipboardCheck, group: "Teaching", badgeKey: "marks" },
  { to: "/branch/completion", label: "Completion & certificates", icon: Award, group: "Completion", badgeKey: "completion" },
  { to: "/branch/support", label: "Student support", icon: LifeBuoy, group: "Help", badgeKey: "support" },
  { to: "/branch/issues", label: "Issues", icon: TriangleAlert, group: "Help", badgeKey: "issues" },
  { to: "/branch/reports", label: "Reports", icon: ChartColumn, group: "Reports" },
];

const ADMIN_NAV: NavItem[] = [
  { to: "/admin", label: "Home", icon: House, badgeKey: "home" },
  { to: "/admin/users", label: "Users & access", icon: UserCog, group: "People", badgeKey: "users" },
  { to: "/admin/students", label: "Student accounts", icon: GraduationCap, group: "People", badgeKey: "student_accounts" },
  { to: "/admin/issues", label: "Issues", icon: TriangleAlert, group: "Operations", badgeKey: "issues" },
  { to: "/admin/calendar", label: "Academic calendar", icon: CalendarDays, group: "Operations", badgeKey: "calendar" },
  { to: "/admin/crm-sync", label: "CRM sync", icon: RefreshCw, group: "Operations", badgeKey: "crm_sync" },
  { to: "/admin/setup", label: "Setup & health", icon: Activity, group: "System", badgeKey: "setup" },
  { to: "/admin/ai-controls", label: "AI controls", icon: Sparkles, group: "System" },
  { to: "/admin/audit", label: "Audit log", icon: ScrollText, group: "System" },
];

const FOUNDER_NAV: NavItem[] = [
  { to: "/founder", label: "Home", icon: ShieldCheck, badgeKey: "inbox" },
  { to: "/founder/curriculum", label: "Curriculum approvals", icon: Library, group: "Approvals", badgeKey: "curriculum" },
  { to: "/founder/certificates", label: "Certificate decisions", icon: Award, group: "Approvals", badgeKey: "certificates" },
  { to: "/founder/access", label: "Access extensions", icon: Hourglass, group: "Approvals", badgeKey: "access" },
  { to: "/founder/ai-controls", label: "AI controls", icon: Sparkles, group: "Safety" },
];

export const NAV: Record<Workspace, NavItem[]> = {
  student: STUDENT_NAV,
  trainer: TRAINER_NAV,
  branch: BRANCH_NAV,
  admin: ADMIN_NAV,
  founder: FOUNDER_NAV,
};

/** Destinations pinned to the phone bottom bar (4 slots + More); workspaces without a list use their first four items. */
const MOBILE_BAR: Partial<Record<Workspace, string[]>> = {
  student: ["/dashboard", "/my-courses", "/schedule", "/tasks"],
  trainer: ["/trainer", "/trainer/sessions", "/trainer/to-grade", "/trainer/students"],
  branch: ["/branch", "/branch/class-day", "/branch/batches", "/branch/schedule"],
};

export function mobileBarItems(workspace: Workspace): NavItem[] {
  const items = NAV[workspace];
  const pinned = MOBILE_BAR[workspace];
  return pinned ? pinned.map((to) => items.find((i) => i.to === to)!) : items.slice(0, 4);
}

const WORKSPACE_ROOTS = ["/trainer", "/branch", "/admin", "/founder"];

/** Workspace index links match exactly; every other item is active for its own sub-paths too. */
export function isNavActive(path: string, to: string): boolean {
  return path === to || (!WORKSPACE_ROOTS.includes(to) && path.startsWith(`${to}/`));
}
