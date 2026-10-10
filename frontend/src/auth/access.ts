/**
 * Workspace access and navigation. The path decides which workspace a screen belongs to (same rule as the
 * prototype); the profile's `workspaces` (from the API, already expanded per role) decides who may open it.
 */
import {
  Award,
  BookOpen,
  Briefcase,
  Building2,
  CalendarCheck,
  CalendarDays,
  CircleCheck,
  ClipboardCheck,
  ClipboardList,
  FileQuestion,
  FolderOpen,
  GraduationCap,
  House,
  Library,
  LifeBuoy,
  Lock,
  Plug,
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
  Wallet,
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
  { to: "/recordings", label: "Recordings", tkey: "recordings", icon: Video },
  { to: "/resources", label: "Resources", tkey: "resources", icon: FolderOpen },
  { to: "/attendance", label: "Attendance", tkey: "attendance", icon: CalendarCheck },
  { to: "/progress", label: "Progress", tkey: "progress", icon: TrendingUp },
  { to: "/results", label: "Results", tkey: "results", icon: ChartColumn },
  { to: "/certificates", label: "Certificates", tkey: "certificates", icon: Award },
  { to: "/career", label: "Career", tkey: "career", icon: Briefcase },
  { to: "/ask-nipuna", label: "Ask Nipuna", tkey: "askNipuna", icon: Sparkles },
  { to: "/support", label: "Support", tkey: "support", icon: LifeBuoy, badgeKey: "support" },
  { to: "/finance", label: "Fees & Receipts", tkey: "finance", icon: Wallet },
  { to: "/profile", label: "Profile", tkey: "profile", icon: User },
];

const TRAINER_NAV: NavItem[] = [
  { to: "/trainer", label: "Today", icon: House, group: "Teach" },
  { to: "/trainer/sessions", label: "Sessions", icon: CalendarDays, group: "Teach" },
  { to: "/trainer/attendance", label: "Attendance", icon: CalendarCheck, group: "Teach" },
  { to: "/trainer/reviews", label: "Reviews", icon: ClipboardCheck, group: "Grade", badgeKey: "to_grade" },
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
  { to: "/branch", label: "Dashboard", icon: House, group: "Today" },
  { to: "/branch/meet-operations", label: "Meet Operations", icon: Video, group: "Today" },
  { to: "/branch/batches", label: "Batches", icon: Users, group: "Batches & students" },
  { to: "/branch/operations", label: "Batches, Schedule & People", icon: Building2, group: "Batches & students", badgeKey: "waiting" },
  { to: "/branch/schedule", label: "Schedule", icon: CalendarDays, group: "Batches & students" },
  { to: "/branch/progress", label: "Attendance & Progress", icon: TrendingUp, group: "Batches & students", badgeKey: "attendance" },
  { to: "/branch/curriculum", label: "Curriculum", icon: Library, group: "Teaching" },
  { to: "/branch/content-review", label: "Content Review", icon: FolderOpen, group: "Teaching", badgeKey: "content_review" },
  { to: "/branch/assessments", label: "Reviews", icon: ClipboardCheck, group: "Teaching", badgeKey: "marks" },
  { to: "/branch/completion", label: "Completion Review", icon: CircleCheck, group: "Completion", badgeKey: "completion" },
  { to: "/branch/certificates", label: "Certificate Eligibility", icon: Award, group: "Completion", badgeKey: "certificates" },
  { to: "/branch/support", label: "Student Support", icon: LifeBuoy, group: "Help", badgeKey: "support" },
  { to: "/branch/exceptions", label: "Exceptions", icon: TriangleAlert, group: "Help", badgeKey: "issues" },
  { to: "/branch/recording-exceptions", label: "Recording Exceptions", icon: Video, group: "Help", badgeKey: "recording_issues" },
  { to: "/branch/requests", label: "Escalations & Extensions", icon: Briefcase, group: "Help", badgeKey: "requests" },
  { to: "/branch/academic-reports", label: "Academic Reports", icon: ChartColumn, group: "Reports" },
  { to: "/branch/reports", label: "Certificates & Reports", icon: ScrollText, group: "Reports" },
];

const ADMIN_NAV: NavItem[] = [
  { to: "/admin", label: "Super Admin", icon: ShieldCheck },
  { to: "/admin/users", label: "Users & Access", icon: UserCog, group: "People", badgeKey: "users" },
  { to: "/admin/students", label: "Student Accounts", icon: GraduationCap, group: "People" },
  { to: "/admin/exceptions", label: "Exception Queues", icon: TriangleAlert, group: "Operations", badgeKey: "issues" },
  { to: "/admin/calendar", label: "Academic Calendar", icon: CalendarDays, group: "Operations" },
  { to: "/admin/crm-sync", label: "CRM Sync", icon: RefreshCw, group: "Operations", badgeKey: "crm_sync" },
  { to: "/admin/integrations", label: "Integration Readiness", icon: Plug, group: "System" },
  { to: "/admin/security", label: "Security Readiness", icon: Lock, group: "System" },
  { to: "/admin/audit", label: "Audit Log", icon: ScrollText, group: "System" },
];

const FOUNDER_NAV: NavItem[] = [
  { to: "/founder", label: "Founder Dashboard", icon: ShieldCheck },
  { to: "/founder/curriculum", label: "Curriculum Approvals", icon: Library, group: "Approvals", badgeKey: "curriculum" },
  { to: "/founder/certificates", label: "Certificate Decisions", icon: Award, group: "Approvals", badgeKey: "certificates" },
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
  trainer: ["/trainer", "/trainer/sessions", "/trainer/reviews", "/trainer/students"],
  branch: ["/branch", "/branch/batches", "/branch/assessments", "/branch/exceptions"],
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
