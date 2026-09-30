import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/** Notifications for the academic, branch and admin workspaces, and the shared staff profile (P3 cross-role finish). */

const STAFF = [
  {
    name: "academic coordinator",
    user: USERS.coordGnt,
    home: "/academic",
    path: "/academic/notifications",
    seeded: "Two completion reviews are waiting for a decision",
  },
  { name: "branch manager", user: USERS.bmGnt, home: "/branch", path: "/branch/notifications", seeded: "A certificate is waiting for your approval" },
  { name: "super admin", user: USERS.admin, home: "/admin", path: "/admin/notifications", seeded: "Review the security readiness checklist" },
];

for (const s of STAFF) {
  test(`${s.name} opens notifications from the header bell and the navigation`, async ({ page }, info) => {
    test.skip(info.project.name === "mobile", "desktop flow");
    await login(page, s.user);
    await expect(page).toHaveURL(new RegExp(`${s.home}$`));
    await expect(page.getByRole("banner").getByTestId("unread-count")).toBeVisible();
    await page.getByRole("banner").getByRole("link", { name: "Notifications" }).click();
    await expect(page).toHaveURL(new RegExp(`${s.path}$`));
    await expect(page.getByRole("heading", { level: 1, name: "Notifications" })).toBeVisible();
    await page.getByLabel("Search", { exact: true }).fill(s.seeded.slice(0, 20)); // other specs add notifications, so find the seeded one
    await expect(page.getByText(s.seeded).first()).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Notifications" })).toBeVisible();
    await page.getByRole("tab", { name: "Action Required" }).click();
    await expect(page.getByRole("tab", { name: "Action Required" })).toHaveAttribute("aria-selected", "true");
  });
}

test("a staff user opens their profile from the account menu and keeps their own navigation", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Profile" }).click();
  await expect(page).toHaveURL(/\/account\/profile$/);
  await expect(page.getByRole("heading", { level: 1, name: "Profile" })).toBeVisible();
  await expect(page.getByText(USERS.bmGnt).first()).toBeVisible();
  await expect(page.getByText("Branch Manager").first()).toBeVisible();
  await expect(page.getByText("Last sign-in")).toBeVisible();
  await expect(page.getByRole("link", { name: "Change password" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Branch Dashboard" })).toBeVisible();
});

test("staff notifications and profile fit a phone without sideways scroll @mobile", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile", "phone layout only");
  await login(page, USERS.coordGnt);
  for (const path of ["/academic/notifications", "/account/profile"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), path).toBeLessThanOrEqual(1);
  }
});
