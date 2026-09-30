import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Assessments (slice S3) across roles: the student submits, the trainer reviews, the Academic Coordinator publishes, the student
 * sees the published result; a practice quiz with a receipt; the mock interview booking; the trainer authors an assignment.
 * Mutates data: run against a freshly seeded staging database (Anvitha's asg-11 "Regression on housing dataset" is Due).
 */

test.describe.configure({ mode: "serial" });

test("student sees each assignment state and submits the Due one", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.goto("/assignments");
  await expect(page.getByRole("link", { name: "Regression on housing dataset" })).toBeVisible(); // Due is the default tab
  for (const [tab, title] of [
    ["Upcoming", "Decision tree tuning notebook"],
    ["Overdue", "Data cleaning checkpoint"],
    ["Submitted", "Pandas cleaning practice"],
    ["Under Review", "EDA mini report"],
    ["Reviewed", "SQL window functions set"],
    ["Resubmission Requested", "Python data structures worksheet"],
  ]) {
    await page.getByRole("tab", { name: tab, exact: true }).click();
    await expect(page.getByRole("link", { name: title })).toBeVisible();
  }

  await page.getByRole("tab", { name: "Due", exact: true }).click();
  await page.getByRole("link", { name: "Regression on housing dataset" }).click();
  await expect(page.getByRole("heading", { name: "Regression on housing dataset" })).toBeVisible();
  await page.getByLabel("Notes").fill("Linear regression with three features; assumptions in the notebook.");
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  await expect(page.getByText(/Submitted as v1\. Receipt SUB-/)).toBeVisible();
  await expect(page.getByText("Your submissions")).toBeVisible();
});

test("trainer reviews it, the coordinator publishes, the student sees the published result", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/reviews");
  const card = page.locator("section", { hasText: "Regression on housing dataset — Anvitha K." });
  await expect(card).toBeVisible();
  await expect(page.locator("section", { hasText: "Regression on housing dataset — Sample Learner G." })).toBeVisible();
  await card.getByLabel("Feedback").fill("Solid baseline; justify the feature choice.");
  await card.getByLabel(/^Marks/).fill("17");
  await card.getByRole("button", { name: "Save review" }).click();
  await expect(page.getByText(/Review saved/)).toBeVisible();
  await expect(card).toBeHidden();

  await page.evaluate(() => window.sessionStorage.clear());
  await page.goto("/login");
  await login(page, USERS.coordGnt);
  await page.goto("/academic/assessments");
  const row = page.getByRole("row", { name: /Regression on housing dataset/ });
  await expect(row).toContainText("Awaiting moderation");
  await row.getByRole("button", { name: "Publish" }).click();
  await expect(page.getByText(/results? published to students/)).toBeVisible();

  await page.evaluate(() => window.sessionStorage.clear());
  await page.goto("/login");
  await login(page, USERS.student);
  await page.goto("/results");
  await expect(page.getByRole("row", { name: /Regression on housing dataset/ })).toContainText("17.00 / 20.00");
  await expect(page.getByRole("row", { name: /SQL coding exercise/ })).toContainText("Provisional — pending moderation");
  await expect(page.getByRole("row", { name: /SQL coding exercise/ })).not.toContainText(/\d+\.\d\d \/ /);
  await expect(page.getByRole("row", { name: /Python Foundations module test/ })).toContainText("42.00 / 50.00");
});

test("student takes the practice quiz and gets a receipt; the tests list shows the seeded states", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.goto("/tests");
  await expect(page.getByText("Submitted — receipt RCPT-T-00931")).toBeVisible();
  await expect(page.getByText("Slot Confirmation Pending")).toBeVisible();
  await expect(page.getByText("Configuration Pending").first()).toBeVisible();
  await expect(page.getByText("Not Released")).toBeVisible();
  await expect(page.getByText(/Scheduled 03 Oct 2026/)).toBeVisible();

  await page.getByRole("link", { name: "Regression practice quiz" }).click();
  await page.getByRole("button", { name: "Start test" }).click();
  await expect(page.getByLabel("Time remaining")).toBeVisible();
  await page.getByLabel("True").check();
  await page.getByLabel("Your answer").fill("3");
  await page.getByLabel("F1-score").check();
  await page.getByLabel("L1 (Lasso)").check();
  await page.getByLabel("L2 (Ridge)").check();
  await page.getByRole("button", { name: "Submit test" }).click();
  await expect(page.getByRole("heading", { name: "Submission Receipt" })).toBeVisible();
  await expect(page.getByText(/RCPT-T-\d{5}/).first()).toBeVisible();
  await expect(page.getByText(/Score: 6\.00 \/ 6\.00/)).toBeVisible(); // practice quizzes are scored at once
});

test("trainer authors and releases an assignment", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/assignments");
  await expect(page.getByRole("row", { name: /SQL window functions set/ })).toBeVisible();
  await page.getByRole("button", { name: "New assignment" }).click();
  await page.getByLabel("Batch").selectOption({ index: 1 });
  await page.getByLabel("Title").fill("Feature scaling exercise");
  await page.getByLabel("Brief").fill("Scale the housing features and compare model error.");
  await page.getByRole("button", { name: "Create and release" }).click();
  await expect(page.getByText("Assignment released to the batch")).toBeVisible();
  await expect(page.getByRole("row", { name: /Feature scaling exercise/ })).toContainText("Released");
});

test("mock interview slot is confirmed by the trainer", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/assessments");
  await page.getByRole("tab", { name: "Mock interviews" }).click();
  await page.getByRole("button", { name: "Confirm" }).first().click();
  await expect(page.getByText(/Slot confirmed/)).toBeVisible();
});

test("assessment screens fit a phone @mobile", async ({ page }) => {
  await login(page, USERS.student);
  for (const path of ["/assignments", "/tests", "/results"]) {
    await page.goto(path);
    await expect(page.getByRole("heading").first()).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  }
});
