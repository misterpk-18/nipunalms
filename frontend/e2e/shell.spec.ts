import { expect, test, type Page } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/** Shell, per-role navigation and workspace guard (role separation). One account per role; needs the API with the staging users. */

const ROLES = [
  {
    name: "student",
    user: USERS.student,
    home: "/dashboard",
    nav: ["Home", "My Learning", "Schedule", "Tasks & Tests", "Class Materials", "My Progress", "Certificates", "Career", "Ask Nipuna", "Support"],
    other: "/trainer",
  },
  {
    name: "trainer",
    user: USERS.trainerG1,
    home: "/trainer",
    nav: [
      "Today",
      "Class schedule",
      "Attendance",
      "Holidays & closures",
      "My requests",
      "My uploads",
      "To grade",
      "Assignments",
      "Assessments",
      "Batches",
      "Students",
      "Course completion",
      "Support",
      "Reports",
      "Ask Nipuna",
    ],
    other: "/branch",
  },
  {
    name: "branch manager",
    user: USERS.bmGnt,
    home: "/branch",
    nav: [
      "My work",
      "Class day",
      "Batches",
      "Waiting for a batch",
      "Schedule & calendar",
      "Attendance & progress",
      "Courses",
      "Content review",
      "Question approvals",
      "Marks & results",
      "Recordings",
      "Completion & certificates",
      "Certificate requests",
      "Student support",
      "Access extensions",
      "Issues",
      "Reports",
      "Payment instructions",
    ],
    other: "/admin",
  },
  {
    name: "super admin",
    user: USERS.admin,
    home: "/admin",
    nav: [
      "Home",
      "Approvals",
      "Staff accounts",
      "Student accounts",
      "Batches",
      "Attendance",
      "Support",
      "Reports",
      "Issues",
      "Academic calendar",
      "Courses",
      "CRM sync",
      "Setup & health",
      "AI controls",
      "Audit log",
    ],
    other: "/founder",
  },
  {
    name: "founder",
    user: USERS.founder,
    home: "/founder",
    nav: [
      "Home",
      "Approvals",
      "Courses",
      "Staff accounts",
      "Student accounts",
      "Batches",
      "Attendance",
      "Issues",
      "Reports",
      "Academic calendar",
      "Support",
      "CRM sync",
      "Setup & health",
      "AI controls",
      "Audit log",
    ],
    other: "/trainer",
  },
];

for (const role of ROLES) {
  test(`${role.name} lands on ${role.home} and its sidebar is exactly its own navigation`, async ({ page }, info) => {
    test.skip(info.project.name === "mobile", "sidebar is desktop only");
    await login(page, role.user);
    await expect(page).toHaveURL(new RegExp(`${role.home}$`));
    const nav = page.getByRole("navigation", { name: "Main" });
    for (const item of role.nav) await expect(nav.getByRole("link", { name: item, exact: true }).first()).toBeVisible();
    // one nav per account: no link into any other role's workspace, and no switcher
    for (const other of ROLES.filter((r) => r.name !== role.name))
      await expect(nav.locator(`a[href="${other.home}"]`), `${role.name} has no link to ${other.home}`).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Acting as" })).toHaveCount(0);
  });

  test(`${role.name} is refused every other role's pages`, async ({ page }, info) => {
    test.skip(info.project.name === "mobile", "desktop flow");
    await login(page, role.user);
    for (const other of ROLES.filter((r) => r.name !== role.name)) {
      await page.goto(other.home);
      await expect(page.getByText(/cannot open this page/), `${role.name} opening ${other.home}`).toBeVisible();
    }
    await page.getByRole("link", { name: "Go to your home" }).click();
    await expect(page).toHaveURL(new RegExp(`${role.home}$`));
  });
}

/** Sign in without waiting to leave /login: a Branch Manager of several branches stays on it for the branch picker. */
async function signInOnly(page: Page, loginId: string) {
  if (!new URL(page.url()).pathname.startsWith("/login")) await page.goto("/login");
  await page.getByLabel("Student ID or email", { exact: true }).fill(loginId);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("a Branch Manager of two branches picks one at sign-in, works in it, and can change it", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "header layout is checked on desktop");
  // signing in stays on /login: the second step of sign-in is the branch picker
  await signInOnly(page, USERS.bmMulti);
  await expect(page.getByRole("heading", { name: "Choose a branch" })).toBeVisible();
  await expect(page.getByRole("link", { name: "My work", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: /Guntur/ }).click();
  await expect(page).toHaveURL(/\/branch$/);
  await expect(page.getByTestId("role-label")).toHaveText("Branch Manager · Guntur");

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Change branch" }).click();
  // the session ends; signing in again offers the picker
  await expect(page).toHaveURL(/\/login/);
  await signInOnly(page, USERS.bmMulti);
  await expect(page.getByRole("heading", { name: "Choose a branch" })).toBeVisible();
  await page.getByRole("button", { name: /Vijayawada/ }).click();
  await expect(page).toHaveURL(/\/branch$/);
  await expect(page.getByTestId("role-label")).toHaveText("Branch Manager · Vijayawada");

  // a Branch Manager of one branch has no picker and no Change branch
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await login(page, USERS.bmGnt);
  await expect(page).toHaveURL(/\/branch$/);
  await page.getByRole("button", { name: "Account menu" }).click();
  await expect(page.getByRole("menuitem", { name: "Change branch" })).toHaveCount(0);
});

test("the Founder's bell opens the Founder notifications page", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "header layout is checked on desktop");
  await login(page, USERS.founder);
  await page.getByRole("button", { name: /^Notifications/ }).click();
  await page.getByRole("link", { name: "Open inbox" }).click();
  await expect(page).toHaveURL(/\/founder\/notifications$/);
});

test("navigation items show how many things wait there, without changing the link name", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "sidebar is desktop only");
  await login(page, USERS.bmGnt);
  const link = page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Issues", exact: true });
  await expect(link.getByTestId("nav-badge")).toBeVisible();
  await expect(link).toHaveAccessibleDescription(/\d+ waiting/);
});

test("Ctrl+K finds pages and records the person may open", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "keyboard shortcut is a desktop feature");
  await login(page, USERS.bmGnt);
  await page.keyboard.press("Control+k");
  const search = page.getByRole("dialog").getByLabel("Search");
  await expect(search).toBeFocused();
  await search.fill("courses");
  await page
    .getByRole("option", { name: /Courses/ })
    .first()
    .click();
  await expect(page).toHaveURL(/\/branch\/courses$/);

  await page.getByRole("button", { name: "Search" }).click();
  await page.getByRole("dialog").getByLabel("Search").fill("Sample");
  await expect(page.getByRole("dialog").getByText("Students", { exact: true })).toBeVisible();
});

test("anonymous visitors are sent to sign in and back", async ({ page }) => {
  await page.goto("/schedule");
  await expect(page).toHaveURL(/\/login\?redirect=%2Fschedule/);
  await login(page, USERS.student);
  await expect(page).toHaveURL(/\/schedule/);
});

test("student can switch the labels to Telugu", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "sidebar is desktop only");
  await login(page, USERS.student);
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "My Learning" })).toBeVisible();
  await page.getByRole("button", { name: "తెలుగు" }).click();
  await expect(nav.getByRole("link", { name: "నా అభ్యాసం" })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "te");
  // the new screens are translated too, statuses included
  await nav.getByRole("link", { name: "పనులు & పరీక్షలు" }).click();
  await expect(page.getByRole("heading", { name: "పనులు & పరీక్షలు", level: 1 })).toBeVisible();
  await expect(page.getByRole("tab", { name: /చేయాల్సినవి/ })).toBeVisible();
  await nav.getByRole("link", { name: "షెడ్యూల్" }).click();
  await expect(page.getByRole("tab", { name: "రాబోయేవి" })).toBeVisible();
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(nav.getByRole("link", { name: "My Learning" })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
});

test.describe("phone layout @mobile", () => {
  test.use({ viewport: { width: 360, height: 740 } });

  test("bottom bar has four items plus More, and nothing scrolls sideways @mobile", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile", "phone layout only");
    await login(page, USERS.student);
    const bar = page.getByRole("navigation", { name: "Bottom" });
    await expect(bar.getByRole("link")).toHaveCount(4);
    for (const item of ["Home", "My Learning", "Schedule", "Tasks & Tests"]) await expect(bar.getByRole("link", { name: item, exact: true })).toBeVisible();

    await bar.getByRole("button", { name: "More" }).click();
    const sheet = page.getByRole("dialog", { name: "More" });
    await expect(sheet.getByRole("link", { name: "Support" })).toBeVisible();
    await sheet.getByRole("link", { name: "My Account" }).click();
    await expect(page).toHaveURL(/\/my-account/);
    await expect(sheet).toHaveCount(0);

    for (const path of ["/dashboard", "/my-courses", "/progress?tab=attendance", "/my-account?tab=fees"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
    }
  });

  test("sign-in screen fits the phone @mobile", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile", "phone layout only");
    await page.goto("/login");
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
  });
});

test("old /academic links land on the matching Branch Manager screen", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/academic/curriculum");
  await expect(page).toHaveURL(/\/branch\/courses$/);
  await page.goto("/academic/reports");
  await expect(page).toHaveURL(/\/branch\/reports$/);
  await page.goto("/academic");
  await expect(page).toHaveURL(/\/branch$/);
  await expect(page.getByRole("heading", { level: 1, name: "My work" })).toBeVisible();
});
