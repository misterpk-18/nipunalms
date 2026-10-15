import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Student services (S5): notifications and the staff side of support and Ask Nipuna. The student's Career, Ask Nipuna, Support and My Account
 * screens are in student-u11.spec.ts.
 * Needs the API on the dev DB seeded with `seed-dev` (mutating tests assume a freshly seeded database).
 */

test.describe.configure({ mode: "serial" });

test("the branch manager resolves the recording-access request and the student is told", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.goto("/branch/support");
  await page.getByRole("button", { name: "Open SR-1042" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("It is under review; we will release it once checked.")).toBeVisible();
  await dialog.getByLabel("Reply").fill("Internal check done");
  await dialog.getByLabel(/Internal remark/).check();
  await dialog.getByRole("button", { name: "Add internal remark" }).click();
  await expect(dialog.getByText(/internal remark, not shown to the student/)).toBeVisible();
  await dialog.getByRole("button", { name: "Resolve" }).click();
  await page.getByLabel("How was it resolved?").fill("Recording released after review");
  await page.getByRole("button", { name: "Resolve", exact: true }).last().click();
  await expect(dialog.getByText("Recording released after review").first()).toBeVisible();
});

test("student gets a bell preview and an inbox with one state and one button per item", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await expect(page.getByTestId("unread-count")).toBeVisible();
  await page.getByRole("button", { name: "Notifications" }).click();
  await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open inbox" })).toBeVisible();
  await page.getByRole("link", { name: "Open inbox" }).click();
  await expect(page).toHaveURL(/\/notifications$/);
  await expect(page.getByRole("heading", { level: 1, name: "Notifications" })).toBeVisible();

  // the inbox has three views and no delivery column or system tab for a student
  for (const tab of ["Needs action", "All", "Done"]) await expect(page.getByRole("tab", { name: tab })).toBeVisible();
  await expect(page.getByRole("tab", { name: "System issues" })).toHaveCount(0);
  await page.getByRole("tab", { name: "All" }).click();
  await expect(page.getByText("Support request SR-1042 resolved").first()).toBeVisible();
  await expect(page.getByText("not sent")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "View request" }).first()).toBeVisible();

  // preferences live on My Account, and only live channels are offered
  await page.goto("/my-account");
  await expect(page.getByText("Messages arrive in the app. WhatsApp and email will be offered here when they are switched on.")).toBeVisible();
  await expect(page.getByRole("switch", { name: /WhatsApp/ })).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Notifications" })).toHaveCount(0);
});

test("only the Super Admin sees system issues in the inbox", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.admin);
  await page.goto("/admin/notifications");
  await expect(page.getByRole("tab", { name: "System issues" })).toBeVisible();
});

test("trainer sees the support flags of their students and their own notifications", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/support");
  await expect(page.getByText(/SR-1051/).first()).toBeVisible();
  await page.goto("/trainer/students");
  await expect(page.getByRole("link", { name: "Sample Learner G.", exact: true }).first()).toBeVisible();
  await expect(page.getByText("Open: Academic").first()).toBeVisible();
  await page.goto("/trainer/notifications");
  await expect(page.getByText(/Attendance for the 24 Sep class/).first()).toBeVisible();
});

test("staff Ask Nipuna works on batch facts", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/ask-nipuna");
  await page.getByRole("button", { name: "Batch progress", exact: true }).click();
  await expect(page.getByLabel("Your question")).toHaveValue(/Summarise how my batch is doing/);
  await page.getByRole("button", { name: "Send" }).click();
  await expect(
    page
      .getByTestId("ai-answer")
      .getByText(/NIT-GNT-BAT-2026-000001/)
      .first(),
  ).toBeVisible();
});

test.describe("phone layout @mobile", () => {
  test.use({ viewport: { width: 360, height: 740 } });

  test("the service screens do not scroll sideways @mobile", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile", "phone layout only");
    await login(page, USERS.student);
    for (const path of ["/support", "/notifications"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), path).toBeLessThanOrEqual(1);
    }
  });
});

test("the branch manager sees escalations and access-extension requests on one page", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/requests"); // the old address opens Student support on the Access extensions tab
  await expect(page).toHaveURL(/\/branch\/support/);
  await expect(page.getByRole("heading", { level: 1, name: "Student support" })).toBeVisible();

  await page.getByRole("tab", { name: /^Requests/ }).click();
  await expect(page.getByRole("cell", { name: "SR-1051" }).first()).toBeVisible();

  await page.getByRole("tab", { name: /^Access extensions/ }).click();
  await expect(page.getByText("EXT-031").first()).toBeVisible();
  await expect(page.getByText("This is beyond what you can approve.")).toBeVisible();
});
