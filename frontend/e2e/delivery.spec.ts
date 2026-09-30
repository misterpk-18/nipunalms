import { expect, test, type Locator, type Page } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Delivery slice (S1) across roles: learner course navigation, batch creation and allocation, scheduling, the trainer's
 * start / deliver / reschedule request, and curriculum activation releasing waiting enrolments.
 * Tests mutate data and run in order: they assume a freshly seeded staging database (create-dev-db --yes && seed-dev).
 */

/** An IST wall-clock value for <input type="datetime-local"> `minutes` from now. */
function istInput(minutes: number): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
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

test("learner navigates My Courses, a combo track, module, topic and session", async ({ page }) => {
  await login(page, USERS.student);
  await page.goto("/my-courses");
  await expect(page.getByRole("heading", { name: "My Courses" })).toBeVisible();
  await expect(page.getByText("Combo (3 + 1)")).toBeVisible();
  await expect(page.getByText("Separately purchased")).toBeVisible();
  await expect(page.getByText("Promotional complimentary — linked to qualifying paid Admission ADM-GNT-2026-000214")).toBeVisible();
  await expect(page.getByText("Curriculum Mapping Pending · Recovery Owner: Academic Coordinator — Guntur")).toBeVisible();
  await expect(page.getByText("You are allocated to batch NIT-VIJ-BAT-2026-000001")).toBeVisible();

  await page.getByRole("link", { name: "Open course" }).first().click();
  await expect(page.getByText("Admission reference (CRM)")).toBeVisible();
  await expect(page.getByText("ADM-GNT-2026-000214 (CRM)")).toBeVisible();
  await expect(page.getByText("Combo programme — one paid Admission")).toBeVisible();

  await page.getByRole("listitem").filter({ hasText: "NIT-CRS-018/T2" }).getByRole("link", { name: "Open track" }).click();
  await expect(page.getByRole("heading", { name: "Machine Learning" })).toBeVisible();
  await page.getByRole("link", { name: "Supervised Learning", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Supervised Learning" })).toBeVisible();
  await page.getByRole("link", { name: "Linear & Logistic Regression" }).click();
  await expect(page.getByRole("heading", { name: "Linear & Logistic Regression" })).toBeVisible();
  await page.getByRole("link", { name: "Linear regression intuition" }).click();
  await expect(page.getByText("Actual Class Session · SES-000101")).toBeVisible();
  await expect(page.getByText("Meet organizer (label)")).toBeVisible();
  await expect(page.getByRole("button", { name: "Join Class" })).toBeDisabled();
});

test("learner schedule lists upcoming classes of the allocated batches", async ({ page }) => {
  await login(page, USERS.student);
  await page.goto("/schedule");
  await expect(page.getByText("All times in IST")).toBeVisible();
  await expect(page.getByRole("link", { name: "Random forests & boosting" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Join Class" }).first()).toBeDisabled();
});

test("coordinator creates a batch and allocates a waiting student after the review", async ({ page }) => {
  await login(page, USERS.coordGnt);
  await page.goto("/academic/batches");
  await expect(page.getByRole("heading", { name: "Batch Management" })).toBeVisible();
  await expect(page.getByRole("row", { name: /NIT-GNT-BAT-2026-000003/ })).toContainText("Blocked");
  await expect(page.getByRole("row", { name: /Sample Learner C\./ })).toContainText("None"); // no open Power BI batch yet

  await page.getByRole("button", { name: "New batch" }).click();
  await choose(dialog(page).getByLabel("Course"), /NIT-CRS-019/);
  await dialog(page).getByLabel("Capacity").fill("20");
  await dialog(page).getByRole("button", { name: "Create batch" }).click();
  await expect(page.getByText("Batch created")).toBeVisible();

  const learner = page.getByRole("row", { name: /Sample Learner C\./ });
  await expect(learner).toContainText("NIT-GNT-BAT-2026-");
  await learner.getByRole("button", { name: "Review & allocate" }).click();
  await expect(dialog(page).getByText("Batch allocation review")).toBeVisible();
  await expect(dialog(page).getByText("Ready to allocate")).toBeVisible();
  await dialog(page).getByRole("button", { name: "Allocate", exact: true }).click();
  await expect(page.getByText("Student allocated")).toBeVisible();
  await expect(page.getByRole("row", { name: /Sample Learner C\./ })).toHaveCount(0);
});

test("coordinator schedules classes; trainer starts and delivers one and asks to move another", async ({ page }) => {
  await login(page, USERS.coordGnt);
  await page.goto("/academic/schedule");
  await page.getByRole("button", { name: "New class session" }).click();
  await choose(dialog(page).getByLabel("Batch"), /NIT-GNT-BAT-2026-000001/);
  await dialog(page).getByLabel("Title").fill("E2E live class");
  await dialog(page).getByLabel("Starts (IST)").fill(istInput(15));
  await dialog(page).getByLabel("Ends (IST)").fill(istInput(75));
  await dialog(page).getByRole("button", { name: "Schedule" }).click();
  await expect(page.getByText("Session(s) scheduled")).toBeVisible();
  await expect(page.getByRole("row", { name: /E2E live class/ })).toContainText("Scheduled");

  // A weekly series for a later day
  await page.getByRole("button", { name: "New class session" }).click();
  await choose(dialog(page).getByLabel("Batch"), /NIT-GNT-BAT-2026-000001/);
  await dialog(page).getByLabel("Title").fill("E2E weekly revision");
  await dialog(page).getByLabel("Starts (IST)").fill(istInput(60 * 24 * 40).slice(0, 11) + "16:00");
  await dialog(page).getByLabel("Ends (IST)").fill(istInput(60 * 24 * 40).slice(0, 11) + "17:00");
  await dialog(page).getByLabel("Repeat").selectOption("weekly");
  await dialog(page).getByLabel("Number of weekly sessions").fill("3");
  await dialog(page).getByRole("button", { name: "Schedule" }).click();
  await expect(page.getByRole("row", { name: /E2E weekly revision/ })).toHaveCount(3);

});

test("trainer starts and delivers the class, and requests a reschedule", async ({ page }) => {
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/sessions");
  const live = page.getByRole("row", { name: /E2E live class/ });
  await live.getByRole("button", { name: "Start" }).click();
  await expect(page.getByText("Class started")).toBeVisible();
  await expect(page.getByRole("row", { name: /E2E live class/ })).toContainText("Live");
  await page.getByRole("row", { name: /E2E live class/ }).getByRole("button", { name: "Mark delivered" }).click();
  await dialog(page).getByLabel("Notes (topics covered)").fill("Covered model evaluation");
  await dialog(page).getByRole("button", { name: "Mark delivered" }).click();
  await expect(page.getByText("Marked as delivered")).toBeVisible();
  await page.getByRole("tab", { name: "Delivered / closed" }).click();
  await expect(page.getByRole("row", { name: /E2E live class/ })).toContainText("Delivered");

  await page.getByRole("tab", { name: "Upcoming" }).click();
  const target = page.getByRole("row", { name: /PCA lab/ });
  await target.getByRole("button", { name: "Request reschedule" }).click();
  await dialog(page).getByLabel("Reason").fill("Lab clash with an exam");
  await dialog(page).getByRole("button", { name: "Send request" }).click();
  await expect(page.getByRole("row", { name: /PCA lab/ }).getByText("Reschedule requested")).toBeVisible();
});

test("coordinator approves the request; the session is rescheduled with history", async ({ page }) => {
  await login(page, USERS.coordGnt);
  await page.goto("/academic/schedule");
  const request = page.getByRole("row", { name: /PCA lab.*Lab clash with an exam/ });
  await request.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Approved — the session moved")).toBeVisible();
  await expect(page.getByRole("row", { name: /PCA lab/ }).first()).toContainText("Rescheduled");
});

test("super admin approves and activates the curriculum; the waiting student is released", async ({ page }) => {
  await login(page, USERS.admin);
  await page.goto("/academic/curriculum");
  await expect(page.getByRole("heading", { name: "Course Curriculum & Versions" })).toBeVisible();
  const row = page.getByRole("row", { name: /NIT-CRS-052/ });
  await expect(row).toContainText("Curriculum Mapping Pending");
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
  await expect(page.getByText("Your course is confirmed. Your Academic Coordinator will allocate you to a batch before your first class.")).toBeVisible();
});

test("branch manager sees batches, exceptions, trainers and students of the branch", async ({ page }) => {
  await login(page, USERS.bmVij);
  await page.goto("/branch/operations");
  await expect(page.getByRole("heading", { name: "Batches, schedule & people" })).toBeVisible();
  await expect(page.getByRole("row", { name: /NIT-VIJ-BAT-2026-000001/ })).toContainText("Pending Verification");
  await expect(page.getByRole("row", { name: /Capstone check-in/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Trainers" })).toBeVisible();
  await page.getByLabel("Search students").fill("Sample Learner J");
  await expect(page.getByRole("row", { name: /Sample Learner J\./ })).toBeVisible();
});

test("@mobile learner course list has no horizontal scroll", async ({ page }) => {
  await login(page, USERS.student);
  await page.goto("/my-courses");
  await expect(page.getByRole("heading", { name: "My Courses" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
