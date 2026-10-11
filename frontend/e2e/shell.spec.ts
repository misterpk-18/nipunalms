import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/** Shell, per-role navigation and workspace guard (Phase 1b). Needs the API on :5060 with the staging users. */

const ROLES = [
  { name: "student", user: USERS.student, home: "/dashboard", nav: ["Home", "My Learning", "Schedule", "Tasks & Tests", "Class Materials", "My Progress", "Certificates", "Career", "Ask Nipuna", "Support"], other: "/trainer" },
  { name: "trainer", user: USERS.trainerG1, home: "/trainer", nav: ["Today", "Sessions", "Reviews", "Batches", "Students", "Ask Nipuna"], other: "/branch" },
  {
    name: "branch manager",
    user: USERS.bmGnt,
    home: "/branch",
    nav: ["Dashboard", "Batches", "Batches, Schedule & People", "Curriculum", "Recording Exceptions", "Certificates & Reports"],
    other: "/admin",
  },
  {
    name: "super admin",
    user: USERS.admin,
    home: "/admin",
    nav: ["Super Admin", "Users & Access", "Integration Readiness", "Security Readiness"],
    other: "/founder",
  },
  { name: "founder", user: USERS.founder, home: "/founder", nav: ["Founder Dashboard", "Curriculum Approvals", "Certificate Decisions"], other: "/trainer" },
];

for (const role of ROLES) {
  test(`${role.name} lands on ${role.home}, sees its navigation and cannot open another workspace`, async ({ page }, info) => {
    test.skip(info.project.name === "mobile", "sidebar is desktop only");
    await login(page, role.user);
    await expect(page).toHaveURL(new RegExp(`${role.home}$`));
    const nav = page.getByRole("navigation", { name: "Main" });
    for (const item of role.nav) await expect(nav.getByRole("link", { name: item, exact: true }).first()).toBeVisible();

    await page.goto(role.other);
    await expect(page.getByText(/cannot open this workspace/)).toBeVisible();
    await page.getByRole("link", { name: "Go to your home" }).click();
    await expect(page).toHaveURL(new RegExp(`${role.home}$`));
  });
}

test("only users with several workspaces get the Acting as switcher", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "header layout is checked on desktop");
  await login(page, USERS.trainerG1);
  await expect(page.getByRole("button", { name: "Acting as" })).toHaveCount(0);
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);

  await login(page, USERS.admin);
  const switcher = page.getByRole("button", { name: "Acting as" });
  await expect(switcher).toBeVisible();
  await switcher.click();
  await expect(page.getByRole("menuitem", { name: /Branch Manager/ })).toContainText("Run a branch");
  await page.getByRole("menuitem", { name: /Branch Manager/ }).click();
  await expect(page).toHaveURL(/\/branch$/);
  await expect(page.getByRole("button", { name: "Acting as" })).toContainText("Branch Manager");

  // a person who may see several branches picks one; the pill says which
  await page.getByRole("button", { name: "Acting as" }).click();
  await page.getByRole("menuitem", { name: "Guntur" }).click();
  await expect(page.getByRole("button", { name: "Acting as" })).toContainText("Guntur");
  await page.getByRole("button", { name: "Acting as" }).click();
  await page.getByRole("menuitem", { name: "All branches" }).click();
  await expect(page.getByRole("button", { name: "Acting as" })).not.toContainText("Guntur");
});

test("navigation items show how many things wait there, without changing the link name", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "sidebar is desktop only");
  await login(page, USERS.bmGnt);
  const link = page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Exceptions", exact: true });
  await expect(link.getByTestId("nav-badge")).toBeVisible();
  await expect(link).toHaveAccessibleDescription(/\d+ waiting/);
});

test("Ctrl+K finds pages and records the person may open", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "keyboard shortcut is a desktop feature");
  await login(page, USERS.bmGnt);
  await page.keyboard.press("Control+k");
  const search = page.getByRole("dialog").getByLabel("Search");
  await expect(search).toBeFocused();
  await search.fill("curric");
  await page
    .getByRole("option", { name: /Curriculum/ })
    .first()
    .click();
  await expect(page).toHaveURL(/\/branch\/curriculum$/);

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
  await expect(page).toHaveURL(/\/branch\/curriculum$/);
  await page.goto("/academic/reports");
  await expect(page).toHaveURL(/\/branch\/academic-reports$/);
  await page.goto("/academic");
  await expect(page).toHaveURL(/\/branch$/);
  await expect(page.getByRole("heading", { name: "Branch dashboard" })).toBeVisible();
});
