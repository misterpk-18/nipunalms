import { expect, test, type APIRequestContext } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * UX phase U13: the trainer's To grade inbox and focused grading screen, Assessments tabs, Batches and Students pages, Content,
 * Reports (students at risk) and the simple Support view. Work to grade is created through the API, so nothing depends on the
 * seed's dates. The tests mutate data and run in order: use a freshly seeded database (create-dev-db --yes && seed-dev).
 */

test.describe.configure({ mode: "serial" });

async function apiLogin(request: APIRequestContext, loginId: string) {
  const response = await request.post("/api/v1/auth/login", { data: { login: loginId, password: PASSWORD } });
  expect(response.ok()).toBeTruthy();
  const { data } = await response.json();
  return { token: data.token as string, userId: data.user.user_id as number };
}
const auth = (token: string) => ({ Authorization: `Bearer ${token}` });
// A new suffix each run, so a re-run on the same database never meets its own earlier data
const RUN = Date.now().toString(36).slice(-5);
const TASK = `U13 grading task ${RUN}`;
const CONTENT = `U13 revision notes ${RUN}`;
const INTERVIEW = `U13 interview ${RUN}`;
/** A slot time in IST ("YYYY-MM-DDTHH:mm") that no earlier run has used, so offering it never clashes. */
const slotTime = () =>
  new Date(Date.now() + (10 + (parseInt(RUN, 36) % 300)) * 86_400_000).toLocaleString("sv-SE", { timeZone: "Asia/Kolkata" }).replace(" ", "T").slice(0, 16);
const PDF = Buffer.from("%PDF-1.4\n1 0 obj\n<< >>\nendobj\ntrailer\n<< >>\n%%EOF\n");

test("two students hand in a new assignment", async ({ request }) => {
  const trainer = await apiLogin(request, USERS.trainerG1);
  const batches = await (await request.get("/api/v1/batches", { headers: auth(trainer.token) })).json();
  const batchId = batches.data[0].batch_id as number;
  const created = await request.post("/api/v1/assignments", {
    headers: auth(trainer.token),
    data: {
      batch_id: batchId,
      title: TASK,
      brief: "Explain overfitting in your own words.",
      max_marks: 20,
      due_at: new Date(Date.now() + 3 * 86_400_000).toISOString(),
      release_now: true,
    },
  });
  expect(created.status(), await created.text()).toBe(201);
  const assignmentId = (await created.json()).data.assignment_id as number;
  for (const student of [USERS.student, "NIT-STU-2026-004183"]) {
    const who = await apiLogin(request, student);
    const sent = await request.post(`/api/v1/assignments/${assignmentId}/submissions`, {
      headers: auth(who.token),
      data: { body_text: `Notes from ${student}` },
    });
    expect(sent.status(), await sent.text()).toBe(201);
  }
});

test("To grade is one inbox; an item opens a focused screen with an explicit Start review and marks checked against the maximum", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Reviews" })).toHaveCount(0);
  await nav.getByRole("link", { name: "To grade" }).click();
  await expect(page).toHaveURL(/\/trainer\/to-grade$/);
  await expect(page.getByRole("heading", { level: 1, name: "To grade" })).toBeVisible();
  for (const tab of ["All", "Assignments", "Tests"]) await expect(page.getByRole("tab", { name: new RegExp(`^${tab}`) })).toBeVisible();
  await expect(page.getByRole("link", { name: "Start with the first" })).toBeVisible();

  // our two hand-ins are in the list, with the student, the work and what waits
  const rows = page.getByRole("row").filter({ hasText: TASK });
  await expect(rows).toHaveCount(2);
  await expect(rows.first()).toContainText("Not started");
  await expect(page.getByRole("button", { name: "Review", exact: true })).toHaveCount(0);

  // the batch filter narrows the list and is kept in the address
  await page.getByLabel("Batch").selectOption({ index: 1 });
  await expect(page).toHaveURL(/batch=\d+/);
  await expect(page.getByRole("row").filter({ hasText: TASK })).toHaveCount(2);

  await page.getByRole("link", { name: new RegExp(`Grade ${TASK} by Anvitha K\\.`) }).click();
  await expect(page).toHaveURL(/\/trainer\/to-grade\/submission\/\d+/);
  await expect(page.getByRole("heading", { level: 1, name: TASK })).toBeVisible();
  await expect(page.getByText("Notes from NIT-STU-2026-004182")).toBeVisible();

  // a review is started on purpose, not by clicking into the box
  await expect(page.getByLabel("Feedback for the student")).toHaveCount(0);
  await page.getByRole("button", { name: "Start review" }).click();
  await expect(page.getByLabel("Feedback for the student")).toBeVisible();
  const save = page.getByRole("button", { name: "Save & next" });
  await expect(save).toBeDisabled();

  // marks are validated against the maximum
  await page.getByLabel("Feedback for the student").fill("Clear explanation; add an example.");
  await page.getByLabel(/^Marks out of 20/).fill("25");
  await expect(page.getByText("Marks must be between 0 and 20.")).toBeVisible();
  await expect(save).toBeDisabled();
  await page.getByLabel(/^Marks out of 20/).fill("-1");
  await expect(page.getByText("Marks must be between 0 and 20.")).toBeVisible();
  await page.getByLabel(/^Marks out of 20/).fill("17");
  await expect(page.getByText("Marks must be between 0 and 20.")).toHaveCount(0);
  await expect(save).toBeEnabled();

  // Save & next saves and opens the next one waiting
  const here = page.url();
  await save.click();
  await expect(page.getByText("Review saved")).toBeVisible();
  await expect(page).not.toHaveURL(here);
  await expect(page).toHaveURL(/\/trainer\/to-grade\/(submission|attempt)\/\d+/);
  await page.getByRole("link", { name: "Back to the list" }).click();
  await expect(page.getByRole("row").filter({ hasText: "Anvitha K." }).filter({ hasText: TASK })).toHaveCount(0);
  await expect(page.getByRole("row").filter({ hasText: "Sample Learner G." }).filter({ hasText: TASK })).toHaveCount(1);
});

test("old links still work: Reviews and the grading tab land on To grade", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/reviews");
  await expect(page).toHaveURL(/\/trainer\/to-grade$/);
  await page.goto("/trainer/assessments?tab=grading");
  await expect(page).toHaveURL(/\/trainer\/to-grade$/);
});

test("Assessments: tabs in workflow order with counts and hints, a new mock interview, drafts you can edit, a confirm on Release", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/assessments");
  const tabs = page.getByRole("tablist", { name: "Assessment areas" }).getByRole("tab");
  await expect(tabs).toHaveText([/^Question bank/, /^Tests/, /^Interviews/]);
  await expect(page.getByText("Build a test from approved questions, then release it to one of your batches.")).toBeVisible();
  await expect(page.getByText("Attempts in progress")).toHaveCount(0);
  await expect(page.getByRole("tab", { name: /Grading queue/ })).toHaveCount(0);

  await page.getByRole("tab", { name: /^Question bank/ }).click();
  await expect(page).toHaveURL(/tab=questions/);
  await expect(page.getByText("Write questions once.")).toBeVisible();

  await page.getByRole("tab", { name: /^Interviews/ }).click();
  await expect(page.getByText("Create a practice interview, offer time slots and record feedback after each one.")).toBeVisible();
  await page.getByRole("button", { name: "New mock interview" }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "New mock interview" })).toBeVisible();
  await dialog.getByLabel("Batch").selectOption({ index: 1 });
  await dialog.getByLabel("Title").fill(INTERVIEW);
  await dialog.getByRole("button", { name: "Create interview" }).click();
  await expect(page.getByText(/created/).first()).toBeVisible();

  // the new interview is a draft: it can be edited, and it cannot be released before it has a slot
  const card = page.locator("section.rounded-xl", { hasText: INTERVIEW });
  await expect(card).toContainText("Offer at least one interview slot");
  await card.getByRole("button", { name: "Edit" }).click();
  await page.getByRole("dialog").getByLabel("Title").fill(`${INTERVIEW} (edited)`);
  await page.getByRole("dialog").getByRole("button", { name: "Save changes" }).click();
  await expect(page.locator("section.rounded-xl", { hasText: `${INTERVIEW} (edited)` })).toBeVisible();

  const edited = page.locator("section.rounded-xl", { hasText: `${INTERVIEW} (edited)` });
  await edited.getByLabel("Slot starts (IST)").fill(slotTime());
  await edited.getByRole("button", { name: "Offer slot" }).click();
  await expect(page.getByText("Slot offered")).toBeVisible();
  await edited.getByRole("button", { name: "Release" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("will see this interview and can book one of your open slots");
  await page.getByRole("alertdialog").getByRole("button", { name: "Cancel" }).click();
  await expect(edited.getByRole("button", { name: "Release" })).toBeVisible();
  await edited.getByRole("button", { name: "Release" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Release" }).click();
  await expect(page.getByText(/released/).first()).toBeVisible();
  await expect(edited.getByRole("button", { name: "Close" })).toBeVisible();
  await edited.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("cannot be reopened");
  await page.getByRole("alertdialog").getByRole("button", { name: "Cancel" }).click();
});

test("Batches and Students open their own pages, with search, a batch filter and Flag this student", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/batches");
  await expect(page.getByRole("heading", { level: 1, name: "Batches" })).toBeVisible();
  await expect(page.getByRole("row", { name: /NIT-GNT-BAT-2026-000001/ })).toContainText("24 of 30");
  await page
    .getByRole("row", { name: /NIT-GNT-BAT-2026-000001/ })
    .getByRole("link", { name: "Open" })
    .click();
  await expect(page).toHaveURL(/\/trainer\/batches\/\d+$/);
  for (const heading of ["How the batch is going", "Classes", "Students", "Assignments", "Content"]) {
    await expect(page.getByRole("heading", { level: 2, name: heading })).toBeVisible();
  }
  await expect(page.getByRole("link", { name: "Batches", exact: true }).first()).toBeVisible(); // breadcrumb
  await expect(page.getByRole("row", { name: new RegExp(TASK) })).toBeVisible();

  // Students: search and a batch filter
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Students" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Students" })).toBeVisible();
  await page.getByRole("textbox", { name: "Search" }).fill("Sample Learner G");
  await expect(page.getByRole("row", { name: /Sample Learner G\./ })).toBeVisible();
  await expect(page.getByRole("row", { name: /Anvitha K\./ })).toHaveCount(0);
  await page.getByRole("textbox", { name: "Search" }).fill("zzzz");
  await expect(page.getByText("No student matches these filters.")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await page.getByLabel("Batch").selectOption({ index: 1 });
  await expect(page).toHaveURL(/batch=\d+/);
  await expect(page.getByRole("row", { name: /Anvitha K\./ })).toBeVisible();

  // a student's page, and flagging from there
  await page.getByRole("link", { name: "Anvitha K." }).first().click();
  await expect(page).toHaveURL(/\/trainer\/students\/\d+$/);
  await expect(page.getByRole("heading", { level: 1, name: "Anvitha K." })).toBeVisible();
  for (const heading of ["Needs your attention", "Attendance", "Work", "Results", "Support requests"]) {
    await expect(page.getByRole("heading", { level: 2, name: heading })).toBeVisible();
  }
  const work = page.locator("section.rounded-xl", { has: page.getByRole("heading", { level: 2, name: "Work", exact: true }) });
  await expect(work.getByRole("row", { name: new RegExp(TASK) })).toContainText("Reviewed");
  await page.getByRole("button", { name: "Flag this student" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Flag Anvitha K." })).toBeVisible();
  await dialog.getByLabel("Details").fill("Missing the Monday classes; please check in.");
  await dialog.getByRole("button", { name: "Raise request" }).click();
  await expect(page.getByText(/raised for Anvitha K\./)).toBeVisible();
  await expect(page.getByText(/Missing the Monday classes; please check in\./).first()).toBeVisible(); // it now shows in this page's Support requests

  // or from a row in the list
  await page.goto("/trainer/students");
  await page.getByRole("button", { name: "Flag Sample Learner G." }).click();
  await expect(page.getByRole("dialog").getByRole("heading", { name: "Flag Sample Learner G." })).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();
});

test("Content: Save & submit is the primary button, a reviewer's comment shows on the row, and the list filters", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/content");
  await page.getByRole("button", { name: "Upload content" }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Batch").selectOption({ index: 1 });
  await dialog.getByLabel("Title").fill(CONTENT);
  await dialog.getByLabel("File", { exact: true }).setInputFiles({ name: "notes.pdf", mimeType: "application/pdf", buffer: PDF });
  await expect(dialog.getByRole("button", { name: "Save & submit for review" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Save draft" })).toBeVisible();
  await dialog.getByRole("button", { name: "Save & submit for review" }).click();
  const row = page.getByRole("row", { name: new RegExp(CONTENT) });
  await expect(row).toContainText("Waiting for review");

  // the Branch Manager asks for changes
  const trainer = await apiLogin(request, USERS.trainerG1);
  const list = await (await request.get("/api/v1/content-items?per_page=100", { headers: auth(trainer.token) })).json();
  const item = list.data.find((i: { title: string }) => i.title === CONTENT);
  const bm = await apiLogin(request, USERS.bmGnt);
  const reviewed = await request.post(`/api/v1/content-items/${item.content_item_id}/review`, {
    headers: auth(bm.token),
    data: { decision: "request_changes", comment: "Add the answers to the practice questions." },
  });
  expect(reviewed.ok(), await reviewed.text()).toBeTruthy();

  await page.reload();
  const changed = page.getByRole("row", { name: new RegExp(CONTENT) });
  await expect(changed).toContainText("Changes requested");
  await expect(changed).toContainText("asked for changes: Add the answers to the practice questions.");
  await expect(changed.getByRole("button", { name: "Fix and resubmit" })).toBeVisible();

  // filters by status and batch
  await page.getByLabel("Status").selectOption({ label: "Draft" });
  await expect(page.getByRole("row", { name: new RegExp(CONTENT) })).toHaveCount(0);
  await page.getByLabel("Status").selectOption({ label: "Changes requested" });
  await expect(page.getByRole("row", { name: new RegExp(CONTENT) })).toBeVisible();
  await page.getByLabel("Batch").selectOption({ index: 1 });
  await expect(page).toHaveURL(/batch=\d+/);
  await expect(page.getByRole("row", { name: new RegExp(CONTENT) })).toBeVisible();

  // fixing it: the corrected version goes straight back for review
  await page
    .getByRole("row", { name: new RegExp(CONTENT) })
    .getByRole("button", { name: "Fix and resubmit" })
    .click();
  const fix = page.getByRole("dialog");
  await fix.getByLabel("File", { exact: true }).setInputFiles({ name: "notes-v2.pdf", mimeType: "application/pdf", buffer: PDF });
  await fix.getByRole("button", { name: "Save & submit for review" }).click();
  await page.getByLabel("Status").selectOption({ label: "Waiting for review" });
  await expect(page.getByRole("row", { name: new RegExp(CONTENT) })).toContainText("v2");
});

test("Reports: students at risk per batch with where to act, and the averages as a short summary", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/reports");
  await expect(page.getByRole("heading", { level: 1, name: "Reports" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Students who need you" })).toBeVisible();
  const batch = page.getByRole("region", { name: /Students who need you/ }).locator("section", { hasText: "NIT-GNT-BAT-2026-000001" });
  await expect(batch).toBeVisible();
  await expect(batch).toContainText(/\d+ of \d+ need attention/);
  const anvitha = batch.getByRole("row", { name: /Anvitha K\./ });
  await expect(anvitha).toContainText("Work missing or late");
  await expect(anvitha.getByRole("link", { name: "Open student" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Summary" })).toBeVisible();
  for (const label of ["Average attendance", "Classes covered", "Time to review"]) await expect(page.getByText(label, { exact: true })).toBeVisible();
  await expect(page.getByText(/Partial Data/)).toHaveCount(0);
  await page.getByText("How this works").click();
  await expect(page.getByText(/Trainers see only assigned batches and students/)).toBeVisible();
  await expect(page.getByText(/NIT-VIJ-BAT/)).toHaveCount(0);
  await anvitha.getByRole("link", { name: "Open student" }).first().click();
  await expect(page).toHaveURL(/\/trainer\/students\/\d+$/);
});

test("Support is the simple view: reply and status first, Escalate under More, no duplicate table", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Support" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Support" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Raise a request" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Students with an open flag" })).toHaveCount(0);
  await expect(page.getByLabel("Category")).toHaveCount(0);
  await expect(page.getByRole("columnheader", { name: "With" })).toBeVisible();

  await page
    .getByRole("button", { name: /^Open SR-/ })
    .first()
    .click();
  const panel = page.getByRole("dialog");
  await expect(panel.getByLabel("Reply")).toBeVisible();
  await expect(panel.getByRole("button", { name: "Resolve" })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Escalate" })).toHaveCount(0);
  await expect(panel.getByLabel(/Internal remark/)).toHaveCount(0);
  await panel.getByRole("button", { name: "More" }).click();
  await expect(panel.getByRole("button", { name: "Escalate" })).toBeVisible();
  await expect(panel.getByLabel(/Internal remark/)).toBeVisible();
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Raise a request" }).click();
  const raise = page.getByRole("dialog");
  await expect(raise.getByRole("heading", { name: "Raise a support request" })).toBeVisible();
  await raise.getByLabel("Student").selectOption({ index: 1 });
  await raise.getByLabel("Details").fill("Needs a catch-up plan after missing a week.");
  await raise.getByRole("button", { name: "Raise request" }).click();
  await expect(page.getByText(/raised for/)).toBeVisible();
});

test("@mobile the phone bar and the new screens fit a phone", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile", "phone layout only");
  await login(page, USERS.trainerG1);
  const bar = page.getByRole("navigation", { name: "Bottom" });
  for (const label of ["Today", "Class schedule", "To grade", "Students"]) await expect(bar.getByRole("link", { name: label })).toBeVisible();
  for (const path of [
    "/trainer/to-grade",
    "/trainer/students",
    "/trainer/batches",
    "/trainer/reports",
    "/trainer/content",
    "/trainer/support",
    "/trainer/assessments",
  ]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), path).toBeLessThanOrEqual(1);
  }
});
