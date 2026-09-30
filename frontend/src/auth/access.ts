/**
 * Workspace access and navigation. The path decides which workspace a screen belongs to (same rule as the
 * prototype); the profile's `workspaces` (from the API, already expanded per role) decides who may open it.
 */
import {
  Award,
  Bell,
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

export const PUBLIC_PATHS = ["/login", "/activate"];

/** Screens outside every workspace (no shell). */
const UNSCOPED_PATHS = [...PUBLIC_PATHS, "/change-password"];

const isUnder = (path: string, root: string) => path === root || path.startsWith(`${root}/`);

/** Which workspace a path belongs to; null for the entry route and the sign-in / activation / password screens. */
export function workspaceForPath(path: string): Workspace | null {
  if (path === "/" || UNSCOPED_PATHS.some((p) => isUnder(path, p))) return null;
  if (isUnder(path, "/trainer")) return "trainer";
  if (isUnder(path, "/academic")) return "academic";
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
  academic: "Academic Coordinator",
  branch: "Branch Manager",
  admin: "Super Admin",
  founder: "Founder / CEO",
};

export const WORKSPACE_HOME: Record<Workspace, string> = {
  student: "/dashboard",
  trainer: "/trainer",
  academic: "/academic",
  branch: "/branch",
  admin: "/admin",
  founder: "/founder",
};

export type NavItem = { to: string; label: string; icon: LucideIcon; tkey?: TranslationKey };

const STUDENT_NAV: NavItem[] = [
  { to: "/dashboard", label: "Home", tkey: "home", icon: House },
  { to: "/my-courses", label: "My Learning", tkey: "myLearning", icon: BookOpen },
  { to: "/schedule", label: "Schedule", tkey: "schedule", icon: CalendarDays },
  { to: "/assignments", label: "Tasks", tkey: "tasks", icon: ClipboardList },
  { to: "/recordings", label: "Recordings", tkey: "recordings", icon: Video },
  { to: "/resources", label: "Resources", tkey: "resources", icon: FolderOpen },
  { to: "/tests", label: "Tests", tkey: "tests", icon: FileQuestion },
  { to: "/attendance", label: "Attendance", tkey: "attendance", icon: CalendarCheck },
  { to: "/progress", label: "Progress", tkey: "progress", icon: TrendingUp },
  { to: "/results", label: "Results", tkey: "results", icon: ChartColumn },
  { to: "/certificates", label: "Certificates", tkey: "certificates", icon: Award },
  { to: "/career", label: "Career", tkey: "career", icon: Briefcase },
  { to: "/ask-nipuna", label: "Ask Nipuna", tkey: "askNipuna", icon: Sparkles },
  { to: "/support", label: "Support", tkey: "support", icon: LifeBuoy },
  { to: "/notifications", label: "Notifications", tkey: "notifications", icon: Bell },
  { to: "/finance", label: "Fees & Receipts", tkey: "finance", icon: Wallet },
  { to: "/profile", label: "Profile", tkey: "profile", icon: User },
];

const TRAINER_NAV: NavItem[] = [
  { to: "/trainer", label: "Today", icon: House },
  { to: "/trainer/batches", label: "Batches", icon: Users },
  { to: "/trainer/students", label: "Students", icon: GraduationCap },
  { to: "/trainer/reviews", label: "Reviews", icon: ClipboardCheck },
  { to: "/trainer/sessions", label: "Sessions", icon: CalendarDays },
  { to: "/trainer/attendance", label: "Attendance", icon: CalendarCheck },
  { to: "/trainer/content", label: "Content", icon: FolderOpen },
  { to: "/trainer/assignments", label: "Assignments", icon: ClipboardList },
  { to: "/trainer/assessments", label: "Assessments", icon: FileQuestion },
  { to: "/trainer/support", label: "Support", icon: LifeBuoy },
  { to: "/trainer/notifications", label: "Notifications", icon: Bell },
  { to: "/trainer/reports", label: "Reports", icon: ChartColumn },
  { to: "/trainer/ask-nipuna", label: "Ask Nipuna", icon: Sparkles },
];

const ACADEMIC_NAV: NavItem[] = [
  { to: "/academic", label: "Dashboard", icon: House },
  { to: "/academic/batches", label: "Batches", icon: Users },
  { to: "/academic/assessments", label: "Reviews", icon: ClipboardCheck },
  { to: "/academic/exceptions", label: "Exceptions", icon: TriangleAlert },
  { to: "/academic/curriculum", label: "Curriculum", icon: Library },
  { to: "/academic/schedule", label: "Schedule", icon: CalendarDays },
  { to: "/academic/content-review", label: "Content Review", icon: FolderOpen },
  { to: "/academic/recording-exceptions", label: "Recording Exceptions", icon: Video },
  { to: "/academic/progress", label: "Attendance & Progress", icon: TrendingUp },
  { to: "/academic/completion", label: "Completion Review", icon: CircleCheck },
  { to: "/academic/certificates", label: "Certificate Eligibility", icon: Award },
  { to: "/academic/support", label: "Academic Support", icon: LifeBuoy },
  { to: "/academic/reports", label: "Reports", icon: ChartColumn },
];

const BRANCH_NAV: NavItem[] = [
  { to: "/branch", label: "Branch Dashboard", icon: Building2 },
  { to: "/branch/operations", label: "Batches, Schedule & People", icon: Users },
  { to: "/branch/requests", label: "Escalations & Extensions", icon: LifeBuoy },
  { to: "/branch/reports", label: "Certificates & Reports", icon: Award },
];

const ADMIN_NAV: NavItem[] = [
  { to: "/admin", label: "Super Admin", icon: ShieldCheck },
  { to: "/admin/integrations", label: "Integration Readiness", icon: Plug },
  { to: "/admin/exceptions", label: "Exception Queues", icon: TriangleAlert },
  { to: "/admin/security", label: "Security Readiness", icon: Lock },
  { to: "/admin/users", label: "Users & Access", icon: UserCog },
  { to: "/admin/students", label: "Student Accounts", icon: GraduationCap },
  { to: "/admin/crm-sync", label: "CRM Sync", icon: RefreshCw },
  { to: "/admin/audit", label: "Audit Log", icon: ScrollText },
  { to: "/academic", label: "Academic (all branches)", icon: CircleCheck },
  { to: "/branch", label: "Branch views", icon: Building2 },
];

const FOUNDER_NAV: NavItem[] = [
  { to: "/founder", label: "Founder Dashboard", icon: ShieldCheck },
  { to: "/admin", label: "Super Admin view", icon: Lock },
  { to: "/branch", label: "Branch views", icon: Building2 },
];

export const NAV: Record<Workspace, NavItem[]> = {
  student: STUDENT_NAV,
  trainer: TRAINER_NAV,
  academic: ACADEMIC_NAV,
  branch: BRANCH_NAV,
  admin: ADMIN_NAV,
  founder: FOUNDER_NAV,
};

/** Destinations pinned to the phone bottom bar (4 slots + More); workspaces without a list use their first four items. */
const MOBILE_BAR: Partial<Record<Workspace, string[]>> = {
  student: ["/dashboard", "/my-courses", "/schedule", "/assignments"],
  trainer: ["/trainer", "/trainer/batches", "/trainer/students", "/trainer/reviews"],
  academic: ["/academic", "/academic/batches", "/academic/assessments", "/academic/exceptions"],
};

export function mobileBarItems(workspace: Workspace): NavItem[] {
  const items = NAV[workspace];
  const pinned = MOBILE_BAR[workspace];
  return pinned ? pinned.map((to) => items.find((i) => i.to === to)!) : items.slice(0, 4);
}

const WORKSPACE_ROOTS = ["/trainer", "/academic", "/branch", "/admin"];

/** Workspace index links match exactly; every other item is active for its own sub-paths too. */
export function isNavActive(path: string, to: string): boolean {
  return path === to || (!WORKSPACE_ROOTS.includes(to) && path.startsWith(`${to}/`));
}
