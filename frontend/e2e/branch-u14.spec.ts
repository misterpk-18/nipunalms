import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * UX phase U14: the Branch Manager's My work, Batches (wizard, step bar, one-step confirm, Create classes), Waiting for a batch,
 * Schedule & calendar and Class day. Data is created through the API and the screens, with a suffix that is new on every run.
 * The tests mutate data and run in order: use a freshly seeded database (create-dev-db --yes && seed-dev). The students who
 * wait for a Python batch are the seed's; a run that finds none skips the steps that need one.
 */

test.describe.configure({ mode: "serial" });

async function apiLogin(request: APIRequestContext, loginId: string) {
  const response = await request.post("/api/v1/auth/login", { data: { login: loginId, password: PASSWORD } });
  expect(response.ok()).toBeTruthy();
  const { data } = await response.json();
  return { token: data.token as string, userId: data.user.user_id as number };
}
const auth = (token: string) => ({ Authorization: `Bearer ${token}` });

const RUN = Date.now().toString(36).slice(-5);
const ROOM = `E2E Lab ${RUN}`;
const PAYMENT = `Pay at the front desk ${RUN}`;
/** A window of three weeks far ahead that no earlier run has used, so the trainer and the room never clash. */
// (22 days further on for every ten seconds that pass, so two runs close together never overlap)
const OFFSET = 60 + 22 * (Math.floor(Date.now() / 10_000) % 400);
const day = (n: number) => new Date(Date.now() + n * 86_400_000).toLocaleDateString("sv-SE", { timeZone: "Asia/Kolkata" });
const START = day(OFFSET);
const END = day(OFFSET + 20);
const MIDDLE = day(OFFSET + 8); // a day in the second week of the window, where both teaching days have a class
/** The Monday on or before `date` (YYYY-MM-DD). */
const mondayOf = (date: string) => {
  const d = new Date(`${date}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
  return d.toISOString().slice(0, 10);
};
const noHorizontalScroll = async (page: Page) =>
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);

/** The CRM tells the LMS about an admission: a new student waiting for a Python batch at Guntur (the dev service key). */
async function admit(request: APIRequestContext, name: string, n: number) {
  const tail = `${Date.now() % 100000}${n}`.padStart(8, "0");
  const sent = await request.post("/api/v1/integrations/crm/events", {
    headers: { "X-Service-Key": "dev-crm-service-key" },
    data: {
      event_id: `e2e-u14-${RUN}-${n}`,
      event_type: "AdmissionQualified",
      source_version: 1,
      occurred_at: new Date().toISOString(),
      data: {
        person: { crm_person_id: `P-E2E-${RUN}-${n}`, full_name: name, email: `e2e.${RUN}.${n}@example.test`, mobile: `98${tail}`.slice(0, 10) },
        admission: {
          crm_admission_id: `A-E2E-${RUN}-${n}`,
          admission_code: `ADM-GNT-2026-9${tail}`.slice(0, 20),
          course_code: "NIT-CRS-052",
          original_branch_code: "NIT-GNT",
          service_branch_code: "NIT-GNT",
          collecting_branch_code: "NIT-GNT",
          mode: "Classroom",
          admission_date: new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Kolkata" }),
        },
        enrolments: [{ course_code: "NIT-CRS-052" }],
      },
    },
  });
  return sent.ok();
}
const LEARNER_A = `E2E Learner A ${RUN}`;
const LEARNER_B = `E2E Learner B ${RUN}`;

let batchCode = "";
let batchId = 0;
let admitted = false;

test("My work leads the Branch home, with a button on every row and the new navigation", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await expect(page).toHaveURL(/\/branch$/);
  await expect(page.getByRole("heading", { level: 1, name: "My work" })).toBeVisible();
  const list = page.getByRole("region", { name: "My work today" });
  await expect(list).toBeVisible();
  await expect(list.getByRole("link", { name: "Allocate" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Main" });
  for (const item of ["My work", "Class day", "Batches", "Waiting for a batch", "Schedule & calendar", "Attendance & progress"])
    await expect(nav.getByRole("link", { name: item, exact: true })).toBeVisible();
  for (const gone of ["Meet Operations", "Batches, Schedule & People", "Dashboard"])
    await expect(nav.getByRole("link", { name: gone, exact: true })).toHaveCount(0);

  await list.getByRole("link", { name: "Allocate" }).click();
  await expect(page).toHaveURL(/\/branch\/waiting$/);
  await expect(page.getByRole("heading", { level: 1, name: "Waiting for a batch" })).toBeVisible();
});

test("old routes land on the new screens", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/meet-operations");
  await expect(page).toHaveURL(/\/branch\/class-day$/);
  await page.goto("/branch/operations");
  await expect(page).toHaveURL(/\/branch\/batches$/);
  await page.goto("/academic/meet-operations");
  await expect(page).toHaveURL(/\/branch\/class-day$/);
});

test("a Branch Manager works in one branch: My work has no branch picker", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch");
  await expect(page.getByRole("heading", { level: 1, name: "My work" })).toBeVisible();
  await expect(page.getByLabel("Branch", { exact: true })).toHaveCount(0);
  await expect(page.getByTestId("role-label")).toHaveText("Branch Manager · Guntur");
});

test("the new batch wizard asks for Course, then Mode, dates and timetable, then Trainer, and opens the batch page", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  admitted = (await admit(request, LEARNER_A, 1)) && (await admit(request, LEARNER_B, 2));

  await login(page, USERS.bmGnt);
  await page.goto("/branch/batches");
  await expect(page.getByRole("heading", { level: 1, name: "Batches" })).toBeVisible();
  await page.getByRole("button", { name: "New batch" }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Step 1 of 3: Course")).toBeVisible();
  await dialog.getByRole("button", { name: "Next" }).click();
  await expect(dialog.getByText("Choose the course.")).toBeVisible();
  const course = dialog.getByLabel("Course *");
  await course.selectOption((await course.locator("option", { hasText: "NIT-CRS-052" }).getAttribute("value"))!);
  await dialog.getByLabel("Seats *").fill("4");
  await dialog.getByRole("button", { name: "Next" }).click();

  await expect(dialog.getByText("Step 2 of 3: Mode, dates and timetable")).toBeVisible();
  await dialog.getByLabel("Starts on").fill(START);
  await dialog.getByLabel("Ends on").fill(END);
  await dialog.getByLabel("Class starts (IST)").fill("15:00");
  await dialog.getByLabel("Class ends (IST)").fill("14:00");
  await dialog.getByRole("button", { name: "Next" }).click();
  await expect(dialog.getByText("The class must end after it starts.")).toBeVisible();
  await dialog.getByLabel("Class ends (IST)").fill("17:00");
  await dialog.getByRole("group").getByLabel("Tue").check();
  await dialog.getByRole("group").getByLabel("Thu").check();
  await dialog.getByLabel("Room").fill(ROOM);
  await dialog.getByRole("button", { name: "Next" }).click();

  await expect(dialog.getByText("Step 3 of 3: Trainer")).toBeVisible();
  await dialog.getByLabel("Lead trainer").selectOption({ label: "Trainer K. Sample" });
  await expect(dialog.getByText("Tue, Thu · 15:00–17:00")).toBeVisible();
  await dialog.getByRole("button", { name: "Create batch" }).click();

  await expect(page).toHaveURL(/\/branch\/batches\/\d+$/);
  batchId = Number(new URL(page.url()).pathname.split("/").pop());
  await expect(page.getByText("Batch created")).toBeVisible();
  batchCode = (await page.locator("header p .font-mono").first().innerText()).trim();
  expect(batchCode).toMatch(/^NIT-GNT-BAT-/);
});

test("the batch page shows the steps, what is missing, and the next action as the main button", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto(`/branch/batches/${batchId}`);
  const steps = page.getByRole("list", { name: "Steps" });
  for (const label of ["Created", "Trainer", "Ready", "Confirmed", "Students", "Classes"]) await expect(steps.getByText(label, { exact: true })).toBeVisible();
  // the trainer was chosen in the wizard; the verified room seats and the recording statement are still missing, and they are shown before Confirm
  const problems = page.getByRole("region", { name: "Before you can confirm" });
  await expect(problems).toContainText("Room / online arrangements and verified capacity");
  await expect(problems).toContainText("Recording provision");
  await page.getByRole("button", { name: "Finish the setup" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Starts on")).toHaveCount(0); // the timetable is already set: only what is missing is asked
  await dialog.getByLabel("Seats verified in the room *").fill("10");
  await dialog.getByLabel("Will students get recordings? *").selectOption("Not Included");
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("region", { name: "Before you can confirm" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Confirm batch" })).toBeVisible();
});

test("confirming with a warning asks for a reason, then the next step is students", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto(`/branch/batches/${batchId}`);
  await page.getByRole("button", { name: "Confirm batch" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("After this, changing its start date, mode, days or times needs each student's agreement.")).toBeVisible();
  const submit = dialog.getByRole("button", { name: "Confirm batch" });
  // a course with no approved curriculum is a warning: the reason is then required and kept on record (the seed's Python course has none)
  const reason = dialog.getByLabel("Why this is acceptable *");
  if (await reason.count()) {
    await expect(dialog.getByText("Look at this before you confirm")).toBeVisible();
    await expect(submit).toBeDisabled();
    await reason.fill(`Curriculum for the course is still in review ${RUN}`);
  }
  await submit.click();
  await expect(page.getByText(/is confirmed/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Add students from the waiting list" })).toBeVisible();
});

test("add students from the waiting list on the batch page", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto(`/branch/batches/${batchId}`);
  await page.getByRole("button", { name: "Add students from the waiting list" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Add students from the waiting list" })).toBeVisible();
  test.skip(!admitted, "the CRM events that add the waiting students were refused on this database");
  const row = dialog.getByRole("list", { name: "Students waiting for this batch" }).getByRole("listitem").filter({ hasText: LEARNER_A });
  await expect(row).toContainText("seats left");
  await row.getByRole("button", { name: "Allocate" }).click();
  await expect(page.getByText(`${LEARNER_A} is in`)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("tab", { name: /^Students\s*1/ })).toBeVisible();
});

test("Waiting for a batch lists matching batches with one-click Allocate", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/waiting");
  await expect(page.getByRole("status").filter({ hasText: /students? waiting/ })).toBeVisible();
  test.skip(!admitted, "the CRM events that add the waiting students were refused on this database");
  await page.getByLabel("Search the waiting list").fill(LEARNER_B);
  const student = page.getByRole("list", { name: "Students waiting for a batch" }).getByRole("listitem").filter({ hasText: LEARNER_B });
  await expect(student).toContainText("waiting 0 days");
  const line = student.getByRole("listitem").filter({ hasText: batchCode });
  await expect(line).toContainText("seats left");
  await expect(line).toContainText("Tue, Thu · 15:00–17:00");
  await line.getByRole("button", { name: "Allocate" }).click();
  await expect(page.getByText(`${LEARNER_B} is in`)).toBeVisible();
  await expect(page.getByRole("list", { name: "Students waiting for a batch" }).getByText(LEARNER_B)).toHaveCount(0);
});

test("Create classes previews the timetable, skips a holiday, and creates the classes", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  // a company holiday on the first Tuesday of the window is skipped
  const admin = await apiLogin(request, USERS.admin);
  const first = new Date(`${START}T12:00:00Z`);
  while (first.getUTCDay() !== 2) first.setUTCDate(first.getUTCDate() + 1);
  const holiday = first.toISOString().slice(0, 10);
  const made = await request.post("/api/v1/calendar/closures", {
    headers: auth(admin.token),
    data: { kind: "Company Holiday", starts_on: holiday, ends_on: holiday, title: `E2E holiday ${RUN}` },
  });
  expect(made.status(), await made.text()).toBeLessThan(300);

  await login(page, USERS.bmGnt);
  await page.goto(`/branch/batches/${batchId}`);
  await page.getByRole("tab", { name: /^Classes/ }).click();
  await expect(page.getByText("No classes yet.")).toBeVisible();
  await page.getByRole("button", { name: "Create classes", exact: true }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: /Create classes for/ })).toBeVisible();
  await expect(dialog.getByText(/\d+ classes? from/)).toBeVisible();
  await dialog.locator("summary", { hasText: /days? skipped/ }).click();
  await expect(dialog.getByText(`Holiday: E2E holiday ${RUN}`)).toBeVisible();
  const create = dialog.getByRole("button", { name: /^Create \d+ classes?$/ });
  await expect(create).toBeEnabled();
  await create.click();
  await expect(page.getByText(/\d+ classes created/)).toBeVisible();
  await expect(page.getByRole("list", { name: "Steps" }).getByRole("listitem").last().locator("svg")).toBeVisible(); // the last step, Classes, is ticked
  await expect(page.getByRole("row").filter({ hasText: "Trainer K. Sample" }).first()).toBeVisible();
});

test("Schedule: week by batch and by trainer, a class opens with its details, New class is filled in from the batch", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto(`/branch/schedule?week=${mondayOf(MIDDLE)}&batch=${batchId}`);
  await expect(page.getByRole("heading", { level: 1, name: "Schedule & calendar" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Week" })).toHaveAttribute("aria-selected", "true");
  const chip = page.getByRole("button", { name: /^.*, .*, Planned$/ }).first();
  await expect(chip).toBeVisible();
  await page.getByLabel("Group by").selectOption("trainer");
  await expect(page.getByRole("rowheader", { name: "Trainer K. Sample" })).toBeVisible();
  await chip.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Trainer K. Sample")).toBeVisible();
  await expect(dialog.getByText(ROOM)).toBeVisible();
  await dialog.locator("summary", { hasText: "Advanced" }).click();
  await expect(dialog.getByText("Class ID")).toBeVisible();
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "New class" }).click();
  const form = page.getByRole("dialog");
  await expect(form.getByLabel("Room")).toHaveValue(ROOM);
  await expect(form.getByLabel("Starts (IST)")).not.toHaveValue("");
  await expect(form.getByLabel("Title *")).not.toHaveValue("");
  await expect(form.locator("summary", { hasText: "Advanced" })).toBeVisible();
  // an extra class on the Wednesday of that week (no teaching day, so nothing clashes)
  const wednesday = new Date(`${mondayOf(MIDDLE)}T12:00:00Z`);
  wednesday.setUTCDate(wednesday.getUTCDate() + 2);
  const wed = wednesday.toISOString().slice(0, 10);
  await form.getByLabel("Title *").fill(`E2E extra ${RUN}`);
  await form.getByLabel("Starts (IST) *").fill(`${wed}T11:00`);
  await form.getByLabel("Ends (IST) *").fill(`${wed}T12:00`);
  await form.getByRole("button", { name: "Schedule class" }).click();
  await expect(page.getByText("Class scheduled")).toBeVisible();
  await expect(page.getByRole("button", { name: new RegExp(`^E2E extra ${RUN}`) })).toBeVisible();

  await page.getByRole("tab", { name: "List" }).click();
  await expect(page).toHaveURL(/view=list/);
  await page.getByRole("tab", { name: "All" }).click();
  const row = page.getByRole("row").filter({ hasText: "Trainer K. Sample" }).first();
  await expect(row.getByRole("button", { name: /More actions for/ })).toBeVisible();
});

test("Needs decision: a trainer's reschedule request is decided from the strip", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const bm = await apiLogin(request, USERS.bmGnt);
  const sessions = await (await request.get(`/api/v1/class-sessions?batch_id=${batchId}&upcoming=true`, { headers: auth(bm.token) })).json();
  const target = sessions.data[1];
  const trainer = await apiLogin(request, "trainer.g3@nipuna.test");
  const moved = new Date(new Date(target.starts_at).getTime() + 3600_000);
  const asked = await request.post(`/api/v1/class-sessions/${target.session_id}/reschedule-requests`, {
    headers: auth(trainer.token),
    data: { proposed_starts_at: moved.toISOString(), proposed_ends_at: new Date(moved.getTime() + 7200_000).toISOString(), reason: `Clinic visit ${RUN}` },
  });
  expect(asked.status(), await asked.text()).toBe(201);

  await login(page, USERS.bmGnt);
  await page.goto("/branch/schedule?decide=1");
  const strip = page.getByRole("region", { name: "Needs decision" });
  await expect(strip).toBeVisible();
  const item = strip.getByRole("listitem").filter({ hasText: `Clinic visit ${RUN}` });
  await expect(item).toContainText("Trainer K. Sample asks to move");
  await item.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("The students and the trainer are told.");
  await page.getByRole("dialog").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Approved. The class moved")).toBeVisible();
  await expect(strip.getByText(`Clinic visit ${RUN}`)).toHaveCount(0);
});

test("Class day: tiles filter the list and a missing Meet link is set inline", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const nowIst = new Date(Date.now() + 5.5 * 3600_000);
  test.skip(nowIst.getUTCHours() === 23 || (nowIst.getUTCHours() === 0 && nowIst.getUTCMinutes() < 10), "too close to midnight IST for a class today");
  const bm = await apiLogin(request, USERS.bmGnt);
  // a short class at a minute no earlier run is likely to have used (the trainer cannot teach two classes at once)
  const start = new Date(Date.now() + (3 + (Math.floor(Date.now() / 10_000) % 55)) * 60_000);
  const created = await request.post("/api/v1/class-sessions", {
    headers: auth(bm.token),
    data: {
      batch_id: batchId,
      title: `E2E online ${RUN}`,
      starts_at: start.toISOString(),
      ends_at: new Date(start.getTime() + 4 * 60_000).toISOString(),
      mode: "Live Online",
      override_reason: "e2e",
    },
  });
  test.skip(created.status() !== 201, `a class could not be added today (${created.status()}): ${(await created.text()).slice(0, 120)}`);

  await login(page, USERS.bmGnt);
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Class day" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Class day" })).toBeVisible();
  const tile = page.getByRole("button", { name: /^Meet link missing/ });
  await expect(tile).toBeVisible();
  await tile.click();
  await expect(tile).toHaveAttribute("aria-pressed", "true");
  const row = page.getByRole("row").filter({ hasText: `E2E online ${RUN}` });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Add Meet link" }).click();
  await page.getByRole("dialog").getByLabel("Meet link *").fill(`https://meet.google.com/e2e-${RUN}-abc`);
  await page.getByRole("dialog").getByRole("button", { name: "Save link" }).click();
  await expect(page.getByText("Meet link saved")).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: `E2E online ${RUN}` })).toHaveCount(0); // it no longer matches the filter
  await page.getByRole("button", { name: /^All classes/ }).click();
  await expect(page.getByRole("row").filter({ hasText: `E2E online ${RUN}` })).toContainText("Link ready");
});

test("the Meet checks moved to the Super Admin's integration screen", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.admin);
  await page.goto("/admin/integrations");
  await expect(page.getByRole("heading", { name: "Meet and class checks" })).toBeVisible();
  await page.goto("/branch/class-day");
  await expect(page.getByText("Last background checks")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Meet integration" })).toHaveCount(0);
});

test("the Super Admin sets how students pay at a branch and the Branch Manager only reads it", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.admin);
  await page.goto("/admin/setup");
  await page.getByLabel("Branch for the payment instructions").selectOption({ label: "Guntur" });
  await page.getByLabel("Payment instructions", { exact: true }).fill(PAYMENT);
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Saved", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);

  await login(page, USERS.bmGnt);
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Payment instructions", exact: true }).click();
  await expect(page.getByText("Set by the Super Admin in Setup & health")).toBeVisible();
  await expect(page.getByLabel("Payment instructions", { exact: true })).toHaveText(PAYMENT);
  await expect(page.getByRole("textbox", { name: "Payment instructions" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Save", exact: true })).toHaveCount(0);
});

test("@mobile Branch screens fit the phone", async ({ page, request }, info) => {
  test.skip(info.project.name !== "mobile", "phone layout only");
  await login(page, USERS.bmGnt);
  await expect(page.getByRole("heading", { level: 1, name: "My work" })).toBeVisible();
  await noHorizontalScroll(page);
  for (const [path, heading] of [
    ["/branch/waiting", "Waiting for a batch"],
    ["/branch/batches", "Batches"],
    [`/branch/batches/${batchId || 1}`, ""],
    ["/branch/schedule", "Schedule & calendar"],
    ["/branch/class-day", "Class day"],
  ] as const) {
    await page.goto(path);
    if (heading) await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    else await expect(page.getByRole("list", { name: "Steps" })).toBeVisible();
    await noHorizontalScroll(page);
  }
  // the week shows as a list of days on a phone
  const bm = await apiLogin(request, USERS.bmGnt);
  const coming = await (await request.get("/api/v1/class-sessions?upcoming=true&per_page=1", { headers: auth(bm.token) })).json();
  test.skip(coming.data.length === 0, "no class is coming up on this database");
  const firstDay = new Date(coming.data[0].starts_at).toLocaleDateString("sv-SE", { timeZone: "Asia/Kolkata" });
  await page.goto(`/branch/schedule?week=${mondayOf(firstDay)}`);
  await expect(page.getByRole("region", { name: /^Tue / })).toBeVisible();
  await noHorizontalScroll(page);
});
