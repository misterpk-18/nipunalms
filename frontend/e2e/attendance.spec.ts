import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Slice S4: attendance, progress and certificates across roles. Run against a freshly seeded dev database
 * (`flask --app app create-dev-db --yes && flask --app app seed-dev`); the certificate steps change the data, so re-seed before a re-run.
 */

test.describe.configure({ mode: "serial" });

test("trainer marks a class: everyone Present, one exception, confirmed", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, "trainer.g3@nipuna.test");
  await page.goto("/trainer/attendance");
  await page.getByRole("tab", { name: "All" }).click();
  await page
    .getByRole("row", { name: /Mini project kick-off/ })
    .getByRole("button", { name: /Mark attendance|Open register/ })
    .click();

  await expect(page.getByRole("heading", { name: /Mini project kick-off/ })).toBeVisible();
  const markAll = page.getByRole("button", { name: "Mark all Present" });
  if (await markAll.isEnabled()) await markAll.click();
  const firstStudent = page.getByRole("radiogroup").first();
  await firstStudent.getByText("Absent", { exact: true }).click();
  await page.getByRole("button", { name: "Confirm attendance" }).click();
  await expect(page.getByText("Attendance confirmed.")).toBeVisible();
  await expect(page.getByText("Every seat is marked.")).toBeVisible();
});

test("student sees attendance with approved recovery, four separate progress measures and certificate status", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);

  await page.goto("/attendance");
  await expect(page.getByText("Absent — recovery approved (REC-0041)").first()).toBeVisible();
  await expect(page.getByText("Present (trainer-confirmed)").first()).toBeVisible();
  await expect(page.getByText("Joining Date: 12 Jan 2026")).toBeVisible();

  await page.goto("/progress");
  for (const title of ["1 · Curriculum delivered", "2 · Attendance / approved recovery", "3 · Required learning completed", "4 · LMS engagement"]) {
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
  }
  await expect(page.getByText("12 attended of 14 marked classes")).toBeVisible();
  await expect(page.getByText("86%").first()).toBeVisible();

  await page.goto("/certificates");
  await expect(page.getByText("Not Yet Eligible").first()).toBeVisible();
  await expect(page.getByText(/Configuration Pending — completion rule not configured/)).toBeVisible();
});

test("coordinator sees alerts and partial data, then recommends a certificate; the branch manager approves and issues it", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.goto("/academic/progress");
  const learnerG = page.getByRole("row", { name: /Sample Learner G\./ });
  await expect(learnerG).toContainText("71%");
  await expect(learnerG).toContainText("Alert");
  await expect(page.getByRole("row", { name: /Sample Learner I\./ })).toContainText("Partial Data");

  await page.goto("/academic/certificates");
  const learnerC = page.getByRole("row", { name: /Sample Learner C\./ });
  await expect(learnerC).toContainText("Eligibility Review");
  await learnerC.getByRole("button", { name: "Recommend" }).click();
  await expect(page.getByText("Recommended for approval.")).toBeVisible();
  await expect(page.getByRole("row", { name: /Sample Learner C\./ })).toContainText("Awaiting Approval");

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();

  await login(page, USERS.bmGnt);
  await page.goto("/branch/reports");
  const row = page.getByRole("row", { name: /Sample Learner C\./ });
  await expect(row).toContainText("Awaiting Approval");
  await row.getByRole("button", { name: "Approve for issue" }).click();
  await expect(page.getByText("Approved for issue.")).toBeVisible();
  await page
    .getByRole("row", { name: /Sample Learner C\./ })
    .getByRole("button", { name: "Issue" })
    .click();
  await expect(page.getByText(/Issued as NIT-CERT-\d{4}-\d{6}/)).toBeVisible();
  await expect(page.getByRole("row", { name: /Sample Learner C\./ })).toContainText("Issued");
  await expect(page.getByRole("row", { name: /Sample Learner A\./ }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Attendance and progress by batch" })).toBeVisible();
});

test("register shows the reissue history and public verification returns only public facts", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.goto("/academic/certificates");
  await expect(page.getByRole("row", { name: /NIT-CERT-2026-000001.*Superseded/ })).toBeVisible();
  await expect(page.getByRole("row", { name: /NIT-CERT-2026-000001.*Issued/ })).toContainText("v2 (reissue) — Name correction");
  await expect(page.getByRole("row", { name: /Sample Learner F\./ })).toContainText("Revoked");

  const response = await request.get("/api/v1/certificates/verify/NIT-CERT-2026-000001");
  expect(response.ok()).toBeTruthy();
  const { data } = await response.json();
  expect(Object.keys(data).sort()).toEqual(["certificate_number", "certificate_type", "course", "holder_name", "issue_date", "status", "version"]);
  expect(data.status).toBe("Issued");
  expect(data.version).toBe(2);
});

test("attendance, progress and certificate screens fit a phone without horizontal scroll @mobile", async ({ page }) => {
  await login(page, USERS.student);
  for (const path of ["/attendance", "/progress", "/certificates"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  }
});
