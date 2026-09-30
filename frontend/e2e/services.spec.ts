import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Student services (S5): support, notifications, career, profile, fees and Ask Nipuna across roles.
 * Needs the API on the dev DB seeded with `seed-dev` (mutating tests assume a freshly seeded database).
 */

test.describe.configure({ mode: "serial" });

test("student raises a support request and follows it with the named owner", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.goto("/support");
  await expect(page.getByRole("heading", { level: 1, name: "Support" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "SR-1042" }).first()).toBeVisible();
  await expect(page.getByText("Academic Coordinator — Guntur").first()).toBeVisible();

  await page.getByLabel("Category", { exact: true }).first().selectOption("LMS");
  await page.getByLabel("Details").fill("The dashboard is slow on my phone");
  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByText(/Request SR-\d+ raised\. Owner: LMS Support — Guntur/)).toBeVisible();

  await page
    .getByRole("row", { name: /dashboard is slow/ })
    .getByRole("button", { name: /^Open SR-/ })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("LMS Support — Guntur (Super Admin)")).toBeVisible();
  await dialog.getByLabel("Reply").fill("Also happens on Wi-Fi");
  await dialog.getByRole("button", { name: "Send reply" }).click();
  await expect(dialog.getByText("Also happens on Wi-Fi")).toBeVisible();
});

test("the academic coordinator resolves the recording-access request and the student is told", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.goto("/academic/support");
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

test("student sees the resolution, an unread bell count and separate notification states", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await expect(page.getByTestId("unread-count")).toBeVisible();
  await page.goto("/notifications");
  await expect(page.getByRole("heading", { level: 1, name: "Notifications" })).toBeVisible();
  await expect(page.getByText("Support request SR-1042 resolved").first()).toBeVisible();

  await page.getByRole("tab", { name: "Action Required" }).click();
  await expect(page.getByText("Assignment 'Regression on housing dataset' due 29 Sep").first()).toBeVisible();
  await page
    .getByRole("button", { name: /Mark action done for Assignment/ })
    .first()
    .click();
  await expect(page.getByText("Action marked done")).toBeVisible();

  await page.getByRole("tab", { name: "System Issues" }).click();
  await expect(page.getByText("WhatsApp — Integration Pending Verification (not sent)").first()).toBeVisible();
  await page.getByRole("tab", { name: "My Notifications" }).click();
  await page.getByRole("button", { name: /Acknowledge Support request SR-1042 resolved/ }).click();
  await expect(page.getByText("Acknowledged").first()).toBeVisible();
  await expect(page.getByRole("switch", { name: "Placement by In-app" })).toBeDisabled();
});

test("trainer sees the support flags of their students and their own notifications", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/support");
  await expect(page.getByRole("cell", { name: "SR-1051", exact: true })).toBeVisible();
  await page.goto("/trainer/students");
  await expect(page.getByRole("cell", { name: "Sample Learner G.", exact: true })).toBeVisible();
  await expect(page.getByText("Open — Academic").first()).toBeVisible();
  await page.goto("/trainer/notifications");
  await expect(page.getByText(/Attendance for the 24 Sep class/).first()).toBeVisible();
});

test("student career screen: consent, opportunities, applying", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.goto("/career");
  await expect(page.getByText("Placement / career assistance only — no guaranteed placement.").first()).toBeVisible();
  await expect(page.getByText("Opted in — 14 Aug 2026").first()).toBeVisible();
  await expect(page.getByText("Until 12 Jul 2027").first()).toBeVisible();
  await expect(page.getByText("CV v3 — Data roles").first()).toBeVisible();
  await expect(page.getByRole("cell", { name: "Junior Data Analyst", exact: true })).toBeVisible();
  await expect(page.getByText("Interview Scheduled").first()).toBeVisible();
  await expect(page.getByText("Confirmation Pending").first()).toBeVisible();

  await page.getByRole("button", { name: "Apply for Data Engineer Trainee" }).click();
  await expect(page.getByText("Application recorded")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Data Engineer Trainee", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Withdraw consent" }).click();
  await page.getByRole("button", { name: "Withdraw consent" }).last().click();
  await expect(page.getByText("Employer sharing consent withdrawn")).toBeVisible();
  await expect(page.getByRole("button", { name: "Give consent to share with employers" })).toBeVisible();
});

test("profile masks the mobile, lists devices and stores the language", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.goto("/profile");
  await expect(page.getByText("NIT-STU-2026-004182").first()).toBeVisible();
  await expect(page.getByText(/●●●●●●0417/)).toBeVisible();
  await expect(page.getByText("Shared family mobile — not identity proof")).toBeVisible();
  await expect(page.getByText("Edge · Windows").first()).toBeVisible();
  await page
    .getByRole("button", { name: /Sign out Edge · Windows/ })
    .first()
    .click();
  await expect(page.getByText("Signed out")).toBeVisible();
});

test("fees & receipts is read-only and shows the CRM summary", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.goto("/finance");
  await expect(page.getByRole("heading", { level: 1, name: "Fees & Receipts" })).toBeVisible();
  await expect(page.getByText("NIT-GNT-2026-000214").first()).toBeVisible();
  await expect(page.getByText("₹ 45,000").first()).toBeVisible();
  await expect(page.getByText("GNT-R-2526-00148").first()).toBeVisible();
  await expect(page.getByText(/is not a receipt and is not counted as paid/)).toBeVisible();
  await expect(page.getByRole("button", { name: /pay/i })).toHaveCount(0);
});

test("Ask Nipuna answers from the student's records, cites sources and refuses out-of-scope questions", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.goto("/ask-nipuna");
  await expect(page.getByText("Configuration Pending")).toBeVisible();
  await expect(page.getByText(/only your enrolled courses/)).toBeVisible();
  await page.getByLabel("Your question").fill("When is my next class?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const answer = page.getByTestId("ai-answer");
  await expect(answer.getByText(/Your upcoming classes/)).toBeVisible();
  await expect(answer.getByText("Sources / evidence")).toBeVisible();
  await answer.getByRole("button", { name: "Helpful", exact: true }).click();
  await expect(page.getByText("Thanks for the feedback")).toBeVisible();

  await page.getByLabel("Your question").fill("Change my fee balance to zero");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText("Not answered: out of scope")).toBeVisible();
  await expect(page.getByText("I can't change or act on fees and payments.")).toBeVisible();
});

test("staff Ask Nipuna works on batch facts", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/ask-nipuna");
  await page.getByRole("button", { name: "Summarize batch progress", exact: true }).click();
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
    for (const path of ["/support", "/notifications", "/career", "/profile", "/finance", "/ask-nipuna"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), path).toBeLessThanOrEqual(1);
    }
  });
});

test("the branch manager sees escalations and access-extension requests on one page", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/requests");
  await expect(page.getByRole("heading", { level: 1, name: "Escalations & access-extension requests" })).toBeVisible();

  await expect(page.getByRole("tab", { name: "Escalations" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("cell", { name: "SR-1051" }).first()).toBeVisible();

  await page.getByRole("tab", { name: "Access extensions" }).click();
  await expect(page.getByRole("cell", { name: "EXT-031" }).first()).toBeVisible();
  await expect(page.getByText("Repeated extension requests do not stack years.")).toBeVisible();
});
