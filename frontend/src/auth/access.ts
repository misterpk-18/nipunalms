/**
 * Workspace access and navigation. The path decides which workspace a screen belongs to (same rule as the
 * prototype); the session's workspace (one per account, from the API) decides who may open it; this is only a guard.
 */
import {
  Activity,
  Award,
  BadgeCheck,
  BookOpen,
  Briefcase,
  CalendarCheck,
  CalendarDays,
  CalendarOff,
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
  PlayCircle,
  LifeBuoy,
  RefreshCw,
  ScrollText,
  Sparkles,
  TrendingUp,
  TriangleAlert,
  User,
  UserCog,
  Users,
  Video,
  Wallet,
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
export type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  tkey?: TranslationKey;
  group?: string;
  badgeKey?: string;
  /** One short line saying what the page is for; shown under the label where two pages could be mistaken for each other. */
  hint?: string;
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
  { to: "/trainer", label: "Today", icon: House, group: "Teach", badgeKey: "class_logs", hint: "Classes to run today: start, attendance, class log" },
  { to: "/trainer/sessions", label: "Class schedule", icon: CalendarDays, group: "Teach", hint: "All your classes, and asks to move one" },
  { to: "/trainer/attendance", label: "Attendance", icon: CalendarCheck, group: "Teach", badgeKey: "attendance", hint: "Registers still to mark, and corrections" },
  { to: "/trainer/calendar", label: "Holidays & closures", icon: CalendarOff, group: "Teach", hint: "Days with no classes, for planning" },
  { to: "/trainer/requests", label: "My requests", icon: FileClock, group: "Teach", hint: "What you asked the Branch Manager, and the answers" },
  { to: "/trainer/content", label: "My uploads", icon: FolderOpen, group: "Teach", hint: "Content you sent for review" },
  { to: "/trainer/to-grade", label: "To grade", icon: ClipboardCheck, group: "Grade", badgeKey: "to_grade" },
  { to: "/trainer/assignments", label: "Assignments", icon: ClipboardList, group: "Grade" },
  { to: "/trainer/assessments", label: "Assessments", icon: FileQuestion, group: "Grade", hint: "Questions, tests and mock interviews" },
  { to: "/trainer/batches", label: "Batches", icon: Users, group: "People" },
  { to: "/trainer/students", label: "Students", icon: GraduationCap, group: "People" },
  { to: "/trainer/completion", label: "Course completion", icon: BadgeCheck, group: "People", hint: "Recommend who has finished the course" },
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
  { to: "/branch/attendance", label: "Attendance & progress", icon: TrendingUp, group: "Batches & students", badgeKey: "attendance" },
  { to: "/branch/courses", label: "Courses", icon: Library, group: "Teaching" },
  { to: "/branch/content", label: "Content review", icon: FolderOpen, group: "Teaching", badgeKey: "content_review", hint: "What trainers uploaded" },
  { to: "/branch/questions", label: "Question approvals", icon: FileQuestion, group: "Teaching", badgeKey: "questions", hint: "Test questions trainers wrote" },
  { to: "/branch/results", label: "Marks & results", icon: ClipboardCheck, group: "Teaching", badgeKey: "marks" },
  { to: "/branch/recordings", label: "Recordings", icon: PlayCircle, group: "Teaching", hint: "Release a class recording" },
  { to: "/branch/completion", label: "Completion & certificates", icon: Award, group: "Completion", badgeKey: "completion" },
  { to: "/branch/certificate-requests", label: "Certificate requests", icon: FileClock, group: "Completion", badgeKey: "certificate_requests", hint: "Corrections, revocations, fee releases" },
  { to: "/branch/support", label: "Student support", icon: LifeBuoy, group: "Help", badgeKey: "support" },
  { to: "/branch/extensions", label: "Access extensions", icon: Hourglass, group: "Help", badgeKey: "extensions", hint: "More time on recordings and materials" },
  { to: "/branch/issues", label: "Issues", icon: TriangleAlert, group: "Help", badgeKey: "issues" },
  { to: "/branch/reports", label: "Reports", icon: ChartColumn, group: "Branch" },
  { to: "/branch/payments", label: "Payment instructions", icon: Wallet, group: "Branch", hint: "How students pay at this branch" },
];

const ADMIN_NAV: NavItem[] = [
  { to: "/admin", label: "Home", icon: House, badgeKey: "home" },
  { to: "/admin/approvals", label: "Approvals", icon: CircleCheck, group: "Approvals", badgeKey: "approvals" },
  { to: "/admin/users", label: "Staff accounts", icon: UserCog, group: "People", badgeKey: "users", hint: "Staff logins, roles and branches" },
  { to: "/admin/students", label: "Student accounts", icon: GraduationCap, group: "People", badgeKey: "student_accounts", hint: "Student logins and what needs fixing" },
  { to: "/admin/batches", label: "Batches", icon: Users, group: "Operations" },
  { to: "/admin/waiting", label: "Waiting for a batch", icon: Hourglass, group: "Operations", badgeKey: "waiting", hint: "Give a student a batch" },
  { to: "/admin/attendance", label: "Attendance", icon: CalendarCheck, group: "Operations" },
  { to: "/admin/support", label: "Support", icon: LifeBuoy, group: "Operations" },
  { to: "/admin/reports", label: "Reports", icon: ChartColumn, group: "Operations" },
  { to: "/admin/issues", label: "Issues", icon: TriangleAlert, group: "Operations", badgeKey: "issues" },
  { to: "/admin/calendar", label: "Academic calendar", icon: CalendarDays, group: "Operations", badgeKey: "calendar" },
  { to: "/admin/courses", label: "Courses", icon: Library, group: "Academic" },
  { to: "/admin/crm-sync", label: "CRM sync", icon: RefreshCw, group: "System", badgeKey: "crm_sync" },
  { to: "/admin/setup", label: "Setup & health", icon: Activity, group: "System", badgeKey: "setup" },
  { to: "/admin/ai-controls", label: "AI controls", icon: Sparkles, group: "System" },
  { to: "/admin/audit", label: "Audit log", icon: ScrollText, group: "System" },
];

const FOUNDER_NAV: NavItem[] = [
  { to: "/founder", label: "Home", icon: House },
  { to: "/founder/approvals", label: "Approvals", icon: CircleCheck, group: "Approvals", badgeKey: "inbox" },
  { to: "/founder/courses", label: "Courses", icon: Library, group: "Company" },
  { to: "/founder/users", label: "Staff accounts", icon: UserCog, group: "People", badgeKey: "users", hint: "Staff logins, roles and branches" },
  { to: "/founder/students", label: "Student accounts", icon: GraduationCap, group: "People", badgeKey: "student_accounts", hint: "Student logins and what needs fixing" },
  { to: "/founder/batches", label: "Batches", icon: Users, group: "Operations" },
  { to: "/founder/waiting", label: "Waiting for a batch", icon: Hourglass, group: "Operations", badgeKey: "waiting", hint: "Give a student a batch" },
  { to: "/founder/attendance", label: "Attendance", icon: CalendarCheck, group: "Operations" },
  { to: "/founder/issues", label: "Issues", icon: TriangleAlert, group: "Operations", badgeKey: "issues" },
  { to: "/founder/reports", label: "Reports", icon: ChartColumn, group: "Operations" },
  { to: "/founder/calendar", label: "Academic calendar", icon: CalendarDays, group: "Operations", badgeKey: "calendar" },
  { to: "/founder/support", label: "Support", icon: LifeBuoy, group: "Operations" },
  { to: "/founder/crm-sync", label: "CRM sync", icon: RefreshCw, group: "System", badgeKey: "crm_sync" },
  { to: "/founder/setup", label: "Setup & health", icon: Activity, group: "System", badgeKey: "setup" },
  { to: "/founder/ai-controls", label: "AI controls", icon: Sparkles, group: "System" },
  { to: "/founder/audit", label: "Audit log", icon: ScrollText, group: "System" },
];

export const NAV: Record<Workspace, NavItem[]> = {
  student: STUDENT_NAV,
  trainer: TRAINER_NAV,
  branch: BRANCH_NAV,
  admin: ADMIN_NAV,
  founder: FOUNDER_NAV,
};

/** Destinations pinned to the phone bottom bar (4 slots + More): an explicit list for every role. */
const MOBILE_BAR: Record<Workspace, string[]> = {
  student: ["/dashboard", "/my-courses", "/schedule", "/tasks"],
  trainer: ["/trainer", "/trainer/sessions", "/trainer/to-grade", "/trainer/students"],
  branch: ["/branch", "/branch/class-day", "/branch/batches", "/branch/schedule"],
  admin: ["/admin", "/admin/approvals", "/admin/users", "/admin/issues"],
  founder: ["/founder", "/founder/approvals", "/founder/students", "/founder/issues"],
};

export function mobileBarItems(workspace: Workspace): NavItem[] {
  const items = NAV[workspace];
  return MOBILE_BAR[workspace].map((to) => items.find((i) => i.to === to)!);
}

const WORKSPACE_ROOTS = ["/trainer", "/branch", "/admin", "/founder"];

/** True for a workspace's index link (`/trainer`, `/branch`, …): the router must match it exactly, or it would be "current" on every page below it. */
export const isWorkspaceRoot = (to: string) => WORKSPACE_ROOTS.includes(to);

/** Workspace index links match exactly; every other item is active for its own sub-paths too. */
export function isNavActive(path: string, to: string): boolean {
  return path === to || (!WORKSPACE_ROOTS.includes(to) && path.startsWith(`${to}/`));
}
