import { expect, test, type APIRequestContext } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * UX phase U12: the trainer's Today flow (the only way to run a class), Sessions as a schedule, Attendance as "Unmarked &
 * corrections" and My requests. Classes are created through the API relative to now, so nothing depends on the seed's dates.
 * The tests mutate data and run in order: use a freshly seeded database (create-dev-db --yes && seed-dev).
 */

test.describe.configure({ mode: "serial" });

async function apiLogin(request: APIRequestContext, loginId: string) {
  const response = await request.post("/api/v1/auth/login", { data: { login: loginId, password: PASSWORD } });
  expect(response.ok()).toBeTruthy();
  const { data } = await response.json();
  return { token: data.token as string, userId: data.user.user_id as number };
}
const auth = (token: string) => ({ Authorization: `Bearer ${token}` });
const istDay = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });

/** The Branch Manager schedules a class for trainer.g1 `startsInMinutes` from now. */
async function schedule(request: APIRequestContext, title: string, startsInMinutes: number, minutes: number, mode: "Classroom" | "Live Online") {
  const bm = await apiLogin(request, USERS.bmGnt);
  const trainer = await apiLogin(request, USERS.trainerG1);
  const batches = await (await request.get("/api/v1/batches", { headers: auth(trainer.token) })).json();
  const batchId = batches.data[0].batch_id as number;
  const existing = await (await request.get(`/api/v1/class-sessions?batch_id=${batchId}&per_page=100`, { headers: auth(trainer.token) })).json();
  const topicId = (existing.data.find((s: { topic: { topic_id: number } | null }) => s.topic) as { topic: { topic_id: number } }).topic.topic_id;
  const start = new Date(Date.now() + startsInMinutes * 60_000);
  const response = await request.post("/api/v1/class-sessions", {
    headers: auth(bm.token),
    data: {
      batch_id: batchId,
      topic_id: topicId,
      title,
      starts_at: start.toISOString(),
      ends_at: new Date(start.getTime() + minutes * 60_000).toISOString(),
      mode,
      trainer_user_id: trainer.userId,
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  return (await response.json()).data[0].session_id as number;
}

test("the Branch Manager schedules two classes for today", async ({ request }) => {
  test.skip(istDay(new Date(Date.now() + 100 * 60_000)) !== istDay(new Date()), "too close to midnight IST to schedule classes for today");
  await schedule(request, "U12 flow class", 3, 40, "Classroom");
  await schedule(request, "U12 online class", 50, 40, "Live Online");
});

test("Today runs the next class from start to class log, and a refresh keeps the place", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await expect(page).toHaveURL(/\/trainer$/);
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();

  const flow = page.getByRole("region", { name: "Class: U12 flow class" });
  await expect(flow.getByText("Next up")).toBeVisible();
  await expect(page.getByRole("region", { name: "Later today" }).getByText("U12 online class")).toBeVisible();
  await expect(page.getByRole("region", { name: "To do" })).toBeVisible();

  await flow.getByRole("button", { name: "Start class" }).click();
  await expect(page.getByText("Class started.")).toBeVisible();

  // refresh: still at the Join step
  await page.reload();
  await expect(flow.getByText("There is no meeting to join.")).toBeVisible();
  await flow.getByRole("button", { name: "Continue to attendance" }).click();

  // refresh: still at Attendance, with the sticky Save bar
  await page.reload();
  await expect(flow.getByRole("button", { name: "Save attendance" })).toBeVisible();
  await flow.getByRole("button", { name: "Mark everyone else Present" }).click();
  await flow.getByRole("button", { name: "Save attendance" }).click();
  await expect(page.getByText("Attendance saved.")).toBeVisible();
  await flow.getByRole("button", { name: "Continue to class log" }).click();

  // the class log: what is typed is kept on the server
  await flow.getByText("Partly held").click();
  await flow.getByLabel("What was not covered").fill("Exception handling");
  await flow.getByLabel("Notes").fill("Covered controllers and request mapping.");
  await expect(flow.getByLabel("Break (minutes)")).toBeVisible();
  await page.waitForTimeout(1200); // the draft is saved a moment after typing
  await page.reload();
  await expect(flow.getByLabel("What was not covered")).toHaveValue("Exception handling");
  await expect(flow.getByLabel("Notes")).toHaveValue("Covered controllers and request mapping.");
  await expect(flow.getByRole("checkbox", { name: /Planned/ })).toBeChecked(); // the planned topic is ticked

  await flow.getByText("Held in full").click();
  await flow.getByRole("button", { name: "Finish class" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("This class will count as taught");
  await page.getByRole("button", { name: "Save class log" }).click();
  await expect(page.getByText("Class log saved.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Class: U12 flow class" })).toHaveCount(0); // the online class is next now
  await page.getByText("Finished today (1)").click();
  await page.getByRole("button", { name: "View" }).click();
  await expect(page.getByText("Held in full")).toBeVisible();
});

test("a class with no Meet link: one click asks the Branch Manager and the flow carries on", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  const flow = page.getByRole("region", { name: "Class: U12 online class" });
  await expect(flow.getByText("Next up")).toBeVisible();
  await flow.getByRole("button", { name: "Start class" }).click();
  await expect(flow.getByText("There is no Meet link for this class yet.")).toBeVisible();
  await flow.getByRole("button", { name: "Ask Branch Manager" }).click();
  await expect(page.getByText("Your Branch Manager has been asked for a link.")).toBeVisible();
  await expect(flow.getByText(/Your Branch Manager was asked at/)).toBeVisible();
  await expect(flow.getByRole("button", { name: "Ask Branch Manager" })).toHaveCount(0);
  await flow.getByRole("button", { name: "Continue to attendance" }).click();
  await expect(flow.getByRole("button", { name: "Save attendance" })).toBeVisible();

  const bm = await apiLogin(request, USERS.bmGnt);
  const notices = await (await request.get("/api/v1/notifications?per_page=50", { headers: auth(bm.token) })).json();
  const told = notices.data.find((n: { title: string }) => n.title === "Meet link needed: U12 online class");
  expect(told, "the Branch Manager is told").toBeTruthy();
  expect(told.link).toBeTruthy();
});

test("Sessions is a schedule: Run class opens the Today flow and a past class gets its log there", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/sessions");
  await expect(page.getByRole("heading", { level: 1, name: "Class schedule" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Mark delivered" })).toHaveCount(0);

  await page.getByRole("tab", { name: "Past" }).click();
  await page
    .getByRole("row", { name: /Cross-validation workshop/ })
    .getByRole("link", { name: "Add class log" })
    .click();
  await expect(page).toHaveURL(/\/trainer\?session=\d+/);
  const flow = page.getByRole("region", { name: "Class: Cross-validation workshop" });
  await expect(flow.getByText("This class is over and has no log yet.")).toBeVisible();
  await flow.getByRole("button", { name: "Finish class" }).click();
  await page.getByRole("button", { name: "Save class log" }).click();
  await expect(page.getByText("Class log saved.")).toBeVisible();
  // attendance can be marked straight after
  await expect(flow.getByRole("button", { name: "Mark attendance" })).toBeVisible();
});

test("a reschedule request shows under My requests, and the decision comes back with its reason", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/sessions");
  await page
    .getByRole("row", { name: /PCA lab/ })
    .getByRole("button", { name: "Request reschedule" })
    .click();
  await page.getByRole("dialog").getByLabel("Reason").fill("Lab clash with an exam");
  await page.getByRole("dialog").getByRole("button", { name: "Send request" }).click();
  await expect(page.getByRole("row", { name: /PCA lab/ }).getByText("Reschedule requested")).toBeVisible();

  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "My requests" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "My requests" })).toBeVisible();
  const card = page.getByRole("listitem").filter({ hasText: "Move PCA lab" });
  await expect(card).toContainText("Waiting for a decision");
  await expect(card).toContainText("Lab clash with an exam");
  await expect(card).toContainText("Waiting for the Branch Manager");

  // the Branch Manager says no, with a reason
  const bm = await apiLogin(request, USERS.bmGnt);
  const open = await (await request.get("/api/v1/reschedule-requests?status=Open", { headers: auth(bm.token) })).json();
  const mine = open.data.find((r: { session: { title: string } }) => r.session.title === "PCA lab");
  const rejected = await request.post(`/api/v1/reschedule-requests/${mine.request_id}/reject`, {
    headers: auth(bm.token),
    data: { note: "Exam week, please keep the date" },
  });
  expect(rejected.ok()).toBeTruthy();

  await page.reload();
  await page.getByRole("tab", { name: /Decided/ }).click();
  await expect(page.getByRole("listitem").filter({ hasText: "Move PCA lab" })).toContainText("Their note: Exam week, please keep the date");
  const trainer = await apiLogin(request, USERS.trainerG1);
  const notices = await (await request.get("/api/v1/notifications?per_page=50", { headers: auth(trainer.token) })).json();
  const told = notices.data.find((n: { title: string }) => n.title === "Reschedule not approved: PCA lab");
  expect(told?.link).toBe("/trainer/requests");
});

test("Attendance is the Unmarked & corrections list and opens the register with a sticky Save bar", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Attendance" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Unmarked & corrections" })).toBeVisible();
  for (const tab of ["Classes to mark", "Corrections waiting", "Recoveries to check", "Recent classes"])
    await expect(page.getByRole("tab", { name: tab })).toBeVisible();
  await page.getByRole("tab", { name: "Corrections waiting" }).click();
  await expect(page.getByText("No correction is waiting for a decision.")).toBeVisible();

  await page.getByRole("tab", { name: "Recent classes" }).click();
  await page
    .getByRole("row", { name: /U12 flow class/ })
    .getByRole("link", { name: /Mark attendance|Open register/ })
    .click();
  await expect(page).toHaveURL(/\/trainer\/attendance\?session=\d+/);
  await expect(page.getByRole("heading", { level: 1, name: "Mark attendance" })).toBeVisible();
  await expect(page.getByTestId("save-bar")).toBeInViewport();
  await page.getByRole("link", { name: "Attendance", exact: true }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Unmarked & corrections" })).toBeVisible();
});

test("@mobile Today and the register fit the phone, with the Save bar above the bottom bar", async ({ page, request }, info) => {
  test.skip(info.project.name !== "mobile", "phone layout only");
  await login(page, USERS.trainerG1);
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);

  const trainer = await apiLogin(request, USERS.trainerG1);
  const list = await (await request.get("/api/v1/class-sessions?per_page=100&mine=true", { headers: auth(trainer.token) })).json();
  const done = list.data.find((s: { title: string }) => s.title === "U12 flow class");
  await page.goto(`/trainer/attendance?session=${done.session_id}`);
  const bar = page.getByTestId("save-bar");
  await expect(bar).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
  const barBox = (await bar.boundingBox())!;
  const navBox = (await page.getByRole("navigation", { name: "Bottom" }).boundingBox())!;
  expect(barBox.y + barBox.height).toBeLessThanOrEqual(navBox.y + 1);
});
