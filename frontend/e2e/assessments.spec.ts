import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Assessments (slice S3) across roles: the student submits, the trainer reviews, the Academic Coordinator publishes, the student
 * sees the published result; a practice quiz with a receipt; the mock interview booking; the trainer authors an assignment.
 * Mutates data: run against a freshly seeded staging database (Anvitha's asg-11 "Regression on housing dataset" is Due).
 */

test.describe.configure({ mode: "serial" });

test("Tasks & Tests groups the work by what the student must do, and the old lists redirect", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.goto("/assignments");
  await expect(page).toHaveURL(/\/tasks$/);
  await page.goto("/tests");
  await expect(page).toHaveURL(/\/tasks$/);
  await expect(page.getByRole("heading", { name: "Tasks & Tests", level: 1 })).toBeVisible();

  // three tabs with counts; work that is handed in waits, reviewed work is done
  await expect(page.getByRole("tab", { name: /^To do/ })).toBeVisible();
  await page.getByRole("tab", { name: /^Waiting for review/ }).click();
  await expect(page.getByRole("link", { name: "Pandas cleaning practice" })).toBeVisible(); // submitted
  await expect(page.getByRole("link", { name: "EDA mini report" })).toBeVisible(); // under review
  await expect(page.getByText("Waiting for confirmation")).toBeVisible(); // the booked mock interview slot
  await page.getByRole("tab", { name: /^Done/ }).click();
  await expect(page.getByRole("link", { name: "SQL window functions set" })).toBeVisible(); // reviewed and published

  await page.getByRole("button", { name: "How marks and results work" }).click();
  await expect(page.getByText(/Marks stay provisional/)).toBeVisible();
});

test("student opens a task, reads the brief and submits near the top", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.goto("/tasks");
  // the first open assignment on the To do tab (the seed's dates are fixed, so which one it is depends on today)
  await expect(page.getByRole("tab", { name: /^To do/ })).toBeVisible(); // the list has loaded
  const open = page.locator('a[href^="/assignments/"]').first();
  test.skip((await open.count()) === 0, "no open assignment left in the seeded data");
  await open.click();
  await expect(page.getByRole("heading", { name: "The brief" })).toBeVisible();
  test.skip((await page.getByRole("button", { name: "Submit your work" }).count()) === 0, "its submission window has closed in the seeded data");
  await expect(page.getByRole("button", { name: "Submit your work" })).toBeVisible(); // the button next to the title
  await page.getByRole("button", { name: "Submit your work" }).click(); // jumps to the form
  await expect(page.getByLabel("Notes")).toBeFocused();
  await page.getByLabel("Notes").fill("Linear regression with three features; assumptions in the notebook.");
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  await expect(page.getByText(/Submitted as version 1\. Receipt SUB-/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your earlier versions" })).toBeVisible();
  await page.getByRole("link", { name: "Back to tasks" }).first().click();
  await expect(page).toHaveURL(/\/tasks$/);
});

test("trainer reviews it, the coordinator publishes, the student sees the published result", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/to-grade");
  const work = (student: string) => page.getByRole("row").filter({ hasText: "Regression on housing dataset" }).filter({ hasText: student });
  // the seed's hand-ins for this assignment are Sample Learner G.'s and H.'s (Anvitha's window closed on a fixed seed date)
  await expect(work("Sample Learner G.")).toBeVisible();
  await expect(work("Sample Learner H.")).toBeVisible();
  await work("Sample Learner G.")
    .getByRole("link", { name: /^Grade/ })
    .click();
  await page.getByRole("button", { name: "Start review" }).click();
  await page.getByLabel("Feedback for the student").fill("Solid baseline; justify the feature choice.");
  await page.getByLabel(/^Marks out of/).fill("17");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText(/Review saved/)).toBeVisible();
  await page.goto("/trainer/to-grade");
  await expect(work("Sample Learner G.")).toHaveCount(0);

  await page.evaluate(() => window.sessionStorage.clear());
  await page.goto("/login");
  await login(page, USERS.coordGnt);
  await page.goto("/branch/assessments"); // the old address opens Marks & results
  await expect(page).toHaveURL(/\/branch\/results/);
  const card = page.getByRole("listitem").filter({ hasText: "Regression on housing dataset" });
  await expect(card).toContainText("To review");
  await card.getByRole("button", { name: "Review marks" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Publish results" }).click();
  const confirm = page.getByRole("alertdialog");
  await expect(confirm.getByText(/Students will see their marks now/)).toBeVisible(); // publishing asks first
  await confirm.getByRole("button", { name: "Publish now" }).click();
  await expect(page.getByText(/results? published/)).toBeVisible();

  await page.evaluate(() => window.sessionStorage.clear());
  await page.goto("/login");
  await login(page, USERS.student);
  await page.goto("/progress?tab=results");
  await expect(page.getByRole("row", { name: /SQL coding exercise/ })).toContainText("Provisional");
  await expect(page.getByRole("row", { name: /SQL coding exercise/ })).not.toContainText(/\d+\.\d\d \/ /);
  await expect(page.getByRole("row", { name: /Python Foundations module test/ })).toContainText("42.00 / 50.00");
});

test("student takes the practice quiz: start and submit both ask first, then a receipt shows where to go next", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.goto("/tasks");
  await page.getByRole("link", { name: "Regression practice quiz" }).first().click();

  // starting says what it means before the clock runs
  await page.getByRole("button", { name: "Start test" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("Attempts left");
  await page.getByRole("alertdialog").getByRole("button", { name: "Start now" }).click();
  await expect(page.getByLabel("Time remaining")).toBeVisible();

  // the navigator shows what is answered and what is flagged
  const navigator = page.getByRole("navigation", { name: "Questions" });
  await expect(navigator).toContainText("0 of");
  await page.getByLabel("True").check();
  await expect(navigator).toContainText("1 of");
  await page.getByRole("button", { name: "Flag for review" }).first().click();
  await expect(navigator).toContainText("1 flagged");

  await page.getByLabel("Your answer").fill("3");
  await page.getByLabel("F1-score").check();
  await page.getByLabel("L1 (Lasso)").check();
  await page.getByLabel("L2 (Ridge)").check();

  // submitting warns about anything left unanswered
  await page.getByRole("button", { name: "Submit test" }).click();
  await expect(page.getByRole("alertdialog")).toContainText(/answered all|not answered/);
  await page.getByRole("alertdialog").getByRole("button", { name: "Submit now" }).click();
  await expect(page.getByRole("heading", { name: "Submission receipt" })).toBeVisible();
  await expect(page.getByText(/RCPT-T-\d{5}/).first()).toBeVisible();
  await expect(page.getByText(/Score 6\.00 \/ 6\.00/)).toBeVisible(); // practice quizzes are scored at once
  await expect(page.getByRole("link", { name: "Back to tasks" }).first()).toBeVisible();
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
  await page.getByRole("tab", { name: /^Interviews/ }).click();
  await page.getByRole("button", { name: "Confirm" }).first().click();
  await expect(page.getByText(/Slot confirmed/)).toBeVisible();
});

test("assessment screens fit a phone @mobile", async ({ page }) => {
  await login(page, USERS.student);
  for (const path of ["/tasks", "/schedule", "/progress?tab=results"]) {
    await page.goto(path);
    await expect(page.getByRole("heading").first()).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  }
});
