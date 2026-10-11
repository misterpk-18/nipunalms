import { expect, test } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * Slice S4: attendance, progress and certificates across roles. Run against a freshly seeded dev database
 * (`flask --app app create-dev-db --yes && flask --app app seed-dev`); the certificate steps change the data, so re-seed before a re-run.
 */

test.describe.configure({ mode: "serial" });

test("trainer marks a class: everyone Present, one exception, saved", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  // a class for today in trainer.g3's batch, created relative to now so no seed date is needed
  const login3 = async (who: string) => {
    const response = await request.post("/api/v1/auth/login", { data: { login: who, password: PASSWORD } });
    const { data } = await response.json();
    return { token: data.token as string, userId: data.user.user_id as number };
  };
  const bm = await login3(USERS.bmGnt);
  const trainer = await login3("trainer.g3@nipuna.test");
  const headers = (token: string) => ({ Authorization: `Bearer ${token}` });
  const batches = await (await request.get("/api/v1/batches", { headers: headers(trainer.token) })).json();
  const start = new Date(Date.now() + 5 * 60_000);
  const created = await request.post("/api/v1/class-sessions", {
    headers: headers(bm.token),
    data: {
      batch_id: batches.data[0].batch_id,
      title: "E2E register class",
      starts_at: start.toISOString(),
      ends_at: new Date(start.getTime() + 40 * 60_000).toISOString(),
      mode: "Classroom",
      trainer_user_id: trainer.userId,
    },
  });
  expect(created.status(), await created.text()).toBe(201);
  const sessionId = (await created.json()).data[0].session_id as number;
  expect((await request.post(`/api/v1/class-sessions/${sessionId}/start`, { headers: headers(trainer.token) })).ok()).toBeTruthy();

  await login(page, "trainer.g3@nipuna.test");
  await page.goto("/trainer/attendance");
  await expect(page.getByRole("heading", { level: 1, name: "Unmarked & corrections" })).toBeVisible();
  await page.getByRole("tab", { name: "Classes to mark" }).click();
  await page
    .getByRole("row", { name: /E2E register class/ })
    .getByRole("link", { name: "Mark attendance" })
    .click();

  await expect(page.getByRole("heading", { name: /E2E register class/ })).toBeVisible();
  await page.getByRole("button", { name: "Mark everyone else Present" }).click();
  await page.getByRole("radiogroup").first().getByText("Absent", { exact: true }).click();
  await page.getByRole("button", { name: "Save attendance" }).click();
  await expect(page.getByText("Attendance saved.")).toBeVisible();
  await expect(page.getByText("Everyone is marked")).toBeVisible();
});

test("student sees attendance with approved recovery, four separate progress measures and certificate status", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);

  // the old address still works and lands on the Attendance tab of My Progress
  await page.goto("/attendance");
  await expect(page).toHaveURL(/\/progress\?tab=attendance/);
  const approved = page.getByRole("row", { name: /Linear regression intuition/ });
  await expect(approved).toContainText("Absent");
  await expect(approved).toContainText("Approved");
  await expect(approved).toContainText("Decided by your Branch Manager");
  await expect(page.getByText("Joining Date: 12 Jan 2026")).toBeVisible();

  await page.goto("/progress");
  for (const title of ["1 · Classes taught", "2 · Attendance", "3 · Required topics covered", "4 · Activity on the LMS"]) {
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
  }
  await expect(page.getByText("12 attended out of 14 marked classes")).toBeVisible();
  await expect(page.getByText("86%").first()).toBeVisible();

  await page.goto("/certificates");
  await expect(page.getByText("Not yet eligible").first()).toBeVisible();
  await expect(page.getByText(/the completion rule for your complimentary course is not set up/)).toBeVisible();
});

test("coordinator sees alerts and partial data, then recommends a certificate; the branch manager approves and issues it", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.goto("/branch/progress");
  const learnerG = page.getByRole("row", { name: /Sample Learner G\./ });
  await expect(learnerG).toContainText("71%");
  await expect(learnerG).toContainText("Alert");
  await expect(page.getByRole("row", { name: /Sample Learner I\./ })).toContainText("Incomplete data");

  await page.goto("/branch/certificates");
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

test("register shows the reissue history and public verification shows the presented version", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.goto("/branch/certificates");
  await expect(page.getByRole("row", { name: /NIT-CERT-2026-000001.*Superseded/ })).toBeVisible();
  await expect(page.getByRole("row", { name: /NIT-CERT-2026-000001.*Issued/ })).toContainText("v2 (reissue) — Name correction");
  await expect(page.getByRole("row", { name: /Sample Learner F\./ })).toContainText("Revoked");

  const response = await request.get("/api/v1/certificates/verify/NIT-CERT-2026-000001");
  expect(response.ok()).toBeTruthy();
  const { data } = await response.json();
  expect(Object.keys(data).sort()).toEqual([
    "branch",
    "certificate_number",
    "certificate_type",
    "course",
    "current_version",
    "holder_name",
    "issue_date",
    "original_issue_date",
    "state",
    "version",
  ]);
  expect(data.state).toBe("Valid — Current Version");
  expect(data.version).toBe(2);

  // The public page needs no sign-in and shows the older copy as Superseded
  await page.goto("/verify/NIT-CERT-2026-000001?version=1");
  await expect(page.getByText(/Superseded — the current copy is version 2/)).toBeVisible();
});

test("attendance, progress and certificate screens fit a phone without horizontal scroll @mobile", async ({ page }) => {
  await login(page, USERS.student);
  for (const path of ["/progress?tab=attendance", "/progress", "/certificates"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  }
});
