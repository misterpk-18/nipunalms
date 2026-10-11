import { expect, test, type Locator, type Page } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Delivery slice (S1) across roles: learner course navigation, batch creation and allocation, scheduling, the trainer's
 * class flow / reschedule request, and curriculum activation releasing waiting enrolments.
 * Tests mutate data and run in order: they assume a freshly seeded staging database (create-dev-db --yes && seed-dev).
 */

/** An IST wall-clock value for <input type="datetime-local"> `minutes` from now. */
function istInput(minutes: number): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Kolkata",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(new Date(Date.now() + minutes * 60_000))
      .map((p) => [p.type, p.value]),
  );
  return `${parts["year"]}-${parts["month"]}-${parts["day"]}T${parts["hour"]}:${parts["minute"]}`;
}

const dialog = (page: Page) => page.getByRole("dialog");

/** Pick the <option> whose text matches (selectOption only takes exact labels). */
async function choose(select: Locator, pattern: RegExp) {
  const label = (await select.locator("option").allTextContents()).find((text) => pattern.test(text));
  expect(label, `an option matching ${pattern}`).toBeDefined();
  await select.selectOption({ label: label! });
}

test.describe.configure({ mode: "serial" });

test("learner navigates My Learning, a combo track, module, topic hub and session", async ({ page }) => {
  await login(page, USERS.student);
  await page.goto("/my-courses");
  await expect(page.getByRole("heading", { name: "My Learning" })).toBeVisible();
  await expect(page.getByText("Combo programme")).toBeVisible();
  await expect(page.getByText("Bought separately")).toBeVisible();
  await expect(page.getByText("Included free")).toBeVisible();
  await expect(page.getByText("Your course is confirmed. Your branch will give you a batch before your first class.").first()).toBeVisible();
  await expect(page.getByText("You have a batch. Your joining date is set when you attend your first regular class.")).toBeVisible();

  // every course card leads with the next topic and says how far along the student is
  await expect(page.getByRole("link", { name: /^(Continue|Start): / }).first()).toBeVisible();
  await expect(page.getByText(/\d+ of \d+ topics done/).first()).toBeVisible();

  await page.getByRole("link", { name: "Open course" }).first().click();
  await expect(page.getByRole("heading", { name: "Tracks in your programme" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Programme modules" })).toBeVisible();
  // the admission and branch details are folded away until asked for
  await expect(page.getByText("Fee ₹")).toBeHidden();
  await page.getByRole("button", { name: "Course info" }).click();
  await expect(page.getByText("Fee ₹")).toBeVisible();

  await page.getByRole("listitem").filter({ hasText: "Machine Learning" }).getByRole("link", { name: "Open track" }).click();
  await expect(page.getByRole("heading", { name: "Machine Learning" })).toBeVisible();
  await page.getByRole("link", { name: "Supervised Learning", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Supervised Learning" })).toBeVisible();
  await expect(page.getByText(/\d+ of \d+ done/).first()).toBeVisible();
  await page.getByRole("link", { name: "Linear & Logistic Regression" }).click();

  // the topic hub: status, classes, recording, files, work and the next topic on one page
  await expect(page.getByRole("heading", { level: 1, name: "Linear & Logistic Regression" })).toBeVisible();
  for (const part of ["Classes", "Recording", "Class materials", "Assignments and tests"]) {
    await expect(page.getByRole("heading", { level: 2, name: part, exact: true })).toBeVisible();
  }
  await expect(page.getByText("Next topic")).toBeVisible();
  await page.getByRole("link", { name: "Linear regression intuition" }).click();
  await expect(page.getByText("Class SES-000101")).toBeVisible();
  await expect(page.getByText("Trainer", { exact: true })).toBeVisible();
});

test("learner schedule groups upcoming classes by day and has a Past tab", async ({ page }) => {
  await login(page, USERS.student);
  await page.goto("/schedule");
  await expect(page.getByRole("heading", { name: "Schedule", level: 1 })).toBeVisible();
  await expect(page.getByText(/times in IST/)).toBeVisible();
  // coming classes are grouped by day (the seeded dates are fixed, so an empty week is fine too)
  const groups = page.getByRole("heading", { level: 2 }).filter({ hasText: /^(Today|Tomorrow|This week|Later)/ });
  await expect(groups.first().or(page.getByText("No classes coming up."))).toBeVisible();
  if (await groups.count()) await expect(page.getByText(/Starts (in|\d)|Live now|The Join button opens/).first()).toBeVisible();

  // the Past tab: attendance and the recording link of classes that have ended
  await page.getByRole("tab", { name: "Past" }).click();
  const missed = page.getByRole("listitem").filter({ hasText: "Linear regression intuition" });
  await expect(missed).toContainText("Absent");
  await expect(missed.getByRole("link", { name: "Watch" })).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Window functions lab" })).toContainText("Present");
});

// Test debt (UX phase U14): this needs the freshly seeded database, where Sample Learner K. still waits for a Power BI batch. The Branch Manager's
// batch and waiting-list flows are covered against any database by branch-u14.spec.ts.
test("coordinator creates a batch with the wizard and allocates a waiting student in one click", async ({ page }) => {
  await login(page, USERS.coordGnt);
  await page.goto("/branch/waiting");
  await expect(page.getByRole("heading", { level: 1, name: "Waiting for a batch" })).toBeVisible();
  const learner = page.getByRole("listitem").filter({ hasText: "Sample Learner K." }).first();
  await expect(learner).toContainText("No open batch of NIT-CRS-019"); // no open Power BI batch yet

  await page.goto("/branch/batches");
  await expect(page.getByRole("heading", { level: 1, name: "Batches" })).toBeVisible();
  await expect(page.getByRole("row", { name: /NIT-GNT-BAT-2026-000003/ })).toContainText("Draft");
  await page.getByRole("button", { name: "New batch" }).first().click();
  await choose(dialog(page).getByLabel("Course *"), /NIT-CRS-019/);
  await dialog(page).getByLabel("Seats *").fill("20");
  await dialog(page).getByRole("button", { name: "Next" }).click();
  await dialog(page).getByRole("button", { name: "Next" }).click();
  await dialog(page).getByRole("button", { name: "Create batch" }).click();
  await expect(page.getByText("Batch created")).toBeVisible();
  await expect(page).toHaveURL(/\/branch\/batches\/\d+$/);

  await page.goto("/branch/waiting");
  const waiting = page.getByRole("listitem").filter({ hasText: "Sample Learner K." }).first();
  await expect(waiting).toContainText("NIT-GNT-BAT-2026-");
  await waiting.getByRole("button", { name: "Allocate" }).first().click();
  await expect(page.getByText(/Sample Learner K\. is in/)).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Sample Learner K." })).toHaveCount(0);
});

test("coordinator schedules classes; trainer starts and delivers one and asks to move another", async ({ page }) => {
  await login(page, USERS.coordGnt);
  await page.goto("/branch/schedule?view=list");
  await page.getByRole("button", { name: "New class" }).click();
  await choose(dialog(page).getByLabel("Batch"), /Data Science/);
  await dialog(page).getByLabel("Title *").fill("E2E live class");
  await dialog(page).getByLabel("Starts (IST) *").fill(istInput(15));
  await dialog(page).getByLabel("Ends (IST) *").fill(istInput(75));
  await dialog(page).getByRole("button", { name: "Schedule class" }).click();
  await expect(page.getByText("Class scheduled")).toBeVisible();
  await expect(page.getByRole("row", { name: /E2E live class/ })).toContainText("Planned");

  // A weekly series for a later day
  await page.getByRole("button", { name: "New class" }).click();
  await choose(dialog(page).getByLabel("Batch"), /Data Science/);
  await dialog(page).getByLabel("Title *").fill("E2E weekly revision");
  await dialog(page)
    .getByLabel("Starts (IST) *")
    .fill(istInput(60 * 24 * 40).slice(0, 11) + "16:00");
  await dialog(page)
    .getByLabel("Ends (IST) *")
    .fill(istInput(60 * 24 * 40).slice(0, 11) + "17:00");
  await dialog(page).getByLabel("Repeat").selectOption("weekly");
  await dialog(page).getByLabel("Number of weekly classes").fill("3");
  await dialog(page).getByRole("button", { name: "Schedule class" }).click();
  await expect(page.getByRole("row", { name: /E2E weekly revision/ })).toHaveCount(3);
});

test("trainer runs the class from Today's flow, and requests a reschedule", async ({ page }) => {
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/sessions");
  // Sessions is the schedule: a class is run from Today, so there is no Start or Mark delivered here
  await expect(page.getByRole("button", { name: "Mark delivered" })).toHaveCount(0);
  await page
    .getByRole("row", { name: /E2E live class/ })
    .getByRole("link", { name: "Run class" })
    .click();
  const flow = page.getByRole("region", { name: "Class: E2E live class" });
  await flow.getByRole("button", { name: "Start class" }).click();
  await expect(page.getByText("Class started.")).toBeVisible();
  await flow.getByRole("button", { name: "Continue to attendance" }).click();
  await flow.getByRole("button", { name: "Continue to class log" }).click();
  await flow.getByLabel("Notes").fill("Covered model evaluation");
  await flow.getByRole("button", { name: "Finish class" }).click();
  await page.getByRole("button", { name: "Save class log" }).click();
  await expect(page.getByText("Class log saved.")).toBeVisible();

  await page.goto("/trainer/sessions");
  await expect(page.getByRole("row", { name: /E2E live class/ })).toContainText("Held");

  const target = page.getByRole("row", { name: /PCA lab/ });
  await target.getByRole("button", { name: "Request reschedule" }).click();
  await dialog(page).getByLabel("Reason").fill("Lab clash with an exam");
  await dialog(page).getByRole("button", { name: "Send request" }).click();
  await expect(page.getByRole("row", { name: /PCA lab/ }).getByText("Reschedule requested")).toBeVisible();
});

test("coordinator approves the request; the session is rescheduled with history", async ({ page }) => {
  await login(page, USERS.coordGnt);
  await page.goto("/branch/schedule?view=list");
  const request = page.getByRole("region", { name: "Needs decision" }).getByRole("listitem").filter({ hasText: /PCA lab.*Lab clash with an exam/ });
  await request.getByRole("button", { name: "Approve", exact: true }).click();
  await dialog(page).getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Approved. The class moved")).toBeVisible();
  await expect(page.getByRole("row", { name: /PCA lab/ }).first()).toContainText("Moved");
});

test("super admin approves and activates the curriculum; the batch and its students pick it up", async ({ page }) => {
  await login(page, USERS.admin);
  await page.goto("/branch/curriculum");
  await expect(page.getByRole("heading", { name: "Course Curriculum & Versions" })).toBeVisible();
  const row = page.getByRole("row", { name: /NIT-CRS-052/ });
  await expect(row).toContainText("batch(es) have no curriculum yet");
  await row.getByRole("button", { name: "Manage versions" }).click();
  await page.getByRole("button", { name: /CV 3\.0 · Under Review/ }).click();
  await expect(page.getByText("Django & REST APIs")).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Curriculum updated").first()).toBeVisible();
  await page.getByRole("button", { name: "Activate" }).click();
  await expect(page.getByRole("row", { name: /NIT-CRS-052/ })).toContainText("Ready");

  await page.evaluate(() => window.sessionStorage.clear());
  await page.goto("/login");
  await login(page, USERS.student);
  await page.goto("/my-courses");
  await expect(page.getByText("Your course is confirmed. Your branch will allocate you to a batch before your first class.").first()).toBeVisible();
});

test("branch manager sees the batches and classes of the branch", async ({ page }) => {
  await login(page, USERS.bmVij);
  await page.goto("/branch/batches");
  await expect(page.getByRole("heading", { level: 1, name: "Batches" })).toBeVisible();
  await expect(page.getByRole("row", { name: /NIT-VIJ-BAT-2026-000001/ }).first()).toBeVisible();
  await expect(page.getByRole("row", { name: /NIT-GNT-BAT/ })).toHaveCount(0);
  await page.goto("/branch/schedule?view=list");
  await expect(page.getByRole("row", { name: /Capstone check-in/ })).toBeVisible();
});

test("@mobile learner course list has no horizontal scroll", async ({ page }) => {
  await login(page, USERS.student);
  await page.goto("/my-courses");
  await expect(page.getByRole("heading", { name: "My Learning" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
