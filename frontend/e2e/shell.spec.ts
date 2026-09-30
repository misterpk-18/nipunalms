import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/** Shell, per-role navigation and workspace guard (Phase 1b). Needs the API on :5060 with the staging users. */

const ROLES = [
  { name: "student", user: USERS.student, home: "/dashboard", nav: ["Home", "My Learning", "Schedule", "Fees & Receipts", "Profile"], other: "/trainer" },
  { name: "trainer", user: USERS.trainerG1, home: "/trainer", nav: ["Today", "Batches", "Students", "Reviews", "Ask Nipuna"], other: "/academic" },
  {
    name: "academic coordinator",
    user: USERS.coordGnt,
    home: "/academic",
    nav: ["Dashboard", "Batches", "Curriculum", "Recording Exceptions", "Reports"],
    other: "/trainer",
  },
  {
    name: "branch manager",
    user: USERS.bmGnt,
    home: "/branch",
    nav: ["Branch Dashboard", "Batches, Schedule & People", "Certificates & Reports"],
    other: "/admin",
  },
  {
    name: "super admin",
    user: USERS.admin,
    home: "/admin",
    nav: ["Super Admin", "Integration Readiness", "Security Readiness", "Academic (all branches)"],
    other: "/founder",
  },
  { name: "founder", user: USERS.founder, home: "/founder", nav: ["Founder Dashboard", "Super Admin view", "Branch views"], other: "/academic" },
];

for (const role of ROLES) {
  test(`${role.name} lands on ${role.home}, sees its navigation and cannot open another workspace`, async ({ page }, info) => {
    test.skip(info.project.name === "mobile", "sidebar is desktop only");
    await login(page, role.user);
    await expect(page).toHaveURL(new RegExp(`${role.home}$`));
    const nav = page.getByRole("navigation", { name: "Main" });
    for (const item of role.nav) await expect(nav.getByRole("link", { name: item, exact: true }).first()).toBeVisible();

    await page.goto(role.other);
    await expect(page.getByText("Permission Restricted")).toBeVisible();
    await page.getByRole("link", { name: "Go to your home" }).click();
    await expect(page).toHaveURL(new RegExp(`${role.home}$`));
  });
}

test("only users with several workspaces get the workspace switcher", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "header layout is checked on desktop");
  await login(page, USERS.trainerG1);
  await expect(page.getByLabel("Workspace", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);

  await login(page, USERS.admin);
  const switcher = page.getByLabel("Workspace", { exact: true });
  await expect(switcher).toBeVisible();
  await switcher.selectOption({ label: "Branch Manager" });
  await expect(page).toHaveURL(/\/branch$/);
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
    for (const item of ["Home", "My Learning", "Schedule", "Tasks"]) await expect(bar.getByRole("link", { name: item, exact: true })).toBeVisible();

    await bar.getByRole("button", { name: "More" }).click();
    const sheet = page.getByRole("dialog", { name: "More" });
    await expect(sheet.getByRole("link", { name: "Fees & Receipts" })).toBeVisible();
    await sheet.getByRole("link", { name: "Profile" }).click();
    await expect(page).toHaveURL(/\/profile/);
    await expect(sheet).toHaveCount(0);

    for (const path of ["/dashboard", "/my-courses", "/attendance", "/finance"]) {
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
