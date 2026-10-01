import { expect, test, type APIRequestContext } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * P3: Student Home, Trainer Today and the trainer / academic reports. Run against a freshly seeded dev database
 * (`flask --app app create-dev-db --yes && flask --app app seed-dev`). The Today flow creates and closes out a class for today.
 */

test.describe.configure({ mode: "serial" });

async function apiLogin(request: APIRequestContext, loginId: string) {
  const response = await request.post("/api/v1/auth/login", { data: { login: loginId, password: PASSWORD } });
  expect(response.ok()).toBeTruthy();
  const { data } = await response.json();
  return { token: data.token as string, userId: data.user.user_id as number };
}

test("student home shows the ranked tiles and every card for Anvitha, and switches to Telugu", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await expect(page).toHaveURL(/\/dashboard$/);

  await expect(page.getByRole("heading", { level: 1, name: "Welcome, Anvitha K." })).toBeVisible();
  await expect(page.getByText("NIT-STU-2026-004182 · Service branch: Guntur")).toBeVisible();

  // three ranked tiles
  for (const label of ["Next Class", "Due Work", "Current Course Progress"]) await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Curriculum delivered (NIT-CRS-900)")).toBeVisible();
  await expect(page.getByText("Separate from attendance and required learning")).toBeVisible();
  await expect(page.getByRole("button", { name: "Join Class" })).toBeDisabled();

  // the card grid
  for (const title of [
    "Continue Learning",
    "Latest Released Recording",
    "Upcoming Assignment / Test",
    "Attendance Alert",
    "Certificate Status",
    "Career Support",
    "Support",
    "Ask Nipuna",
  ]) {
    await expect(page.getByRole("heading", { level: 2, name: title, exact: true })).toBeVisible();
  }
  // earlier specs release recordings and deliver classes, so check the shape rather than one fixed title
  const learning = page.locator("section", { has: page.getByRole("heading", { level: 2, name: "Continue Learning", exact: true }) });
  await expect(learning.getByRole("link")).toHaveAttribute("href", /\/topics\/\d+/);
  const recording = page.locator("section", { has: page.getByRole("heading", { level: 2, name: "Latest Released Recording", exact: true }) });
  await expect(recording.getByRole("link")).toHaveAttribute("href", "/recordings");
  await expect(recording.getByText("Released", { exact: true })).toBeVisible();
  await expect(recording.getByText(/Access until \d{1,2} \w{3,4} \d{4}/)).toBeVisible();
  await expect(page.getByText(/REC-0041/)).toBeVisible();
  await expect(page.getByText("Not Yet Eligible")).toBeVisible();
  await expect(page.getByText(/Opted in · Profile \d+% complete/)).toBeVisible();
  await expect(page.getByText(/no guaranteed placement/i)).toBeVisible();
  await expect(page.getByText(/\d+ of 50 daily responses used/)).toBeVisible();
  await expect(page.getByText(/Engagement data last refreshed|shown as Stale/i).first()).toBeVisible();

  // language setting: the greeting and card titles follow it
  await page.getByRole("button", { name: "తెలుగు" }).click();
  await expect(page.getByRole("heading", { level: 1, name: /^నమస్తే, / })).toBeVisible();
  await expect(page.getByText("తదుపరి తరగతి", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "అభ్యాసం కొనసాగించండి" })).toBeVisible();
});

test("student home fits the phone and keeps Join Class within reach @mobile", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile", "phone layout only");
  await login(page, USERS.student);
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { level: 1, name: "Welcome, Anvitha K." })).toBeVisible();
  await expect(page.getByText("Next Class", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Join Class" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Continue Learning" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Ask Nipuna" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
});

test("trainer today: tiles, the empty state, then the session flow from open to close-out", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await expect(page).toHaveURL(/\/trainer$/);

  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();
  await expect(page.getByText("Assigned sessions scheduled")).toBeVisible();
  await expect(page.getByText("Submissions awaiting my review")).toBeVisible();
  await expect(page.getByText("Assigned students with open support flags")).toBeVisible();
  await expect(page.getByText(/Oldest: \d+ days?/)).toBeVisible();
  await expect(page.getByText("No assigned session scheduled today.")).toBeVisible();
  await expect(page.getByText(/Trainers see only assigned batches and students/)).toBeVisible();

  // the coordinator schedules a class for today (ten minutes from now, IST)
  const coordinator = await apiLogin(request, USERS.coordGnt);
  const trainer = await apiLogin(request, USERS.trainerG1);
  const auth = (token: string) => ({ Authorization: `Bearer ${token}` });
  const batches = await (await request.get("/api/v1/batches", { headers: auth(trainer.token) })).json();
  const batchId = batches.data[0].batch_id as number;
  const sessions = await (await request.get(`/api/v1/class-sessions?batch_id=${batchId}&per_page=100`, { headers: auth(trainer.token) })).json();
  const topicId = (sessions.data.find((s: { topic: { topic_id: number } | null }) => s.topic) as { topic: { topic_id: number } }).topic.topic_id;
  const start = new Date(Date.now() + 10 * 60_000);
  const ist = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  test.skip(ist(start) !== ist(new Date()), "too close to midnight IST to schedule a class for today");
  const created = await request.post("/api/v1/class-sessions", {
    headers: auth(coordinator.token),
    data: {
      batch_id: batchId,
      topic_id: topicId,
      title: "Today flow class",
      starts_at: start.toISOString(),
      ends_at: new Date(start.getTime() + 60 * 60_000).toISOString(),
      mode: "Classroom",
      trainer_user_id: trainer.userId,
    },
  });
  expect(created.status(), await created.text()).toBe(201);

  await page.reload();
  await expect(page.getByRole("heading", { level: 2, name: "Today's flow — Today flow class" })).toBeVisible();
  const steps = page.getByRole("list", { name: "Session flow" });
  for (const label of ["Open today's session", "Join / Start Meet", "Record delivered topics", "Mark attendance", "Notes & closeout"]) {
    await expect(steps.getByText(label)).toBeVisible();
  }

  await page.getByRole("button", { name: "Open session" }).click();
  await expect(page.getByText("Session opened.")).toBeVisible();
  await expect(steps.getByRole("listitem").nth(1)).toHaveAttribute("aria-current", "step");
  await page.getByRole("button", { name: "Continue (class started)" }).click();

  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Save delivered topics" }).click();
  await expect(page.getByText("Delivered topics saved.")).toBeVisible();

  await page.getByRole("button", { name: "Mark all Present" }).click();
  await page.getByRole("button", { name: "Confirm attendance" }).click();
  await expect(page.getByText("Attendance confirmed.")).toBeVisible();

  await page.getByLabel("Session notes").fill("Covered the topic; revisit examples next class.");
  await page.getByRole("button", { name: "Close out session" }).click();
  await expect(page.getByText(/Session closed out\. Recording mapping: Pending Verification\./)).toBeVisible();
});

test("trainer reports: delivery and attendance per assigned batch, review turnaround and engagement", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/reports");
  await expect(page.getByRole("heading", { level: 1, name: "Reports" })).toBeVisible();
  for (const title of ["Curriculum delivered", "Attendance (trainer-confirmed)", "Review turnaround", "Engagement"]) {
    await expect(page.getByRole("heading", { level: 2, name: title, exact: true })).toBeVisible();
  }
  await expect(page.getByText(/NIT-GNT-BAT-2026-000001/).first()).toBeVisible();
  await expect(page.getByText(/reviewed submission\(s\)/)).toBeVisible();
  await expect(page.getByText(/Partial Data:/).first()).toBeVisible(); // unmarked delivered classes keep the attendance average provisional
  await expect(page.getByText(/Trainers see only assigned batches and students/)).toBeVisible();
  // another branch's batches never appear
  await expect(page.getByText(/NIT-VIJ-BAT/)).toHaveCount(0);
});

test("academic reports: the coordinator sees only their own branch", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.goto("/academic/reports");
  await expect(page.getByRole("heading", { level: 1, name: "Academic Reports" })).toBeVisible();
  for (const title of ["Curriculum delivered (branch)", "Attendance / approved recovery", "Completion reviews closed", "Certificate issue lead time"]) {
    await expect(page.getByRole("heading", { level: 2, name: title, exact: true })).toBeVisible();
  }
  await expect(page.getByText(/Approved recovery: \d+/)).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "By batch" })).toBeVisible();
  await expect(page.getByText(/NIT-GNT-BAT-2026-000001/).first()).toBeVisible();
  await expect(page.getByText(/NIT-VIJ-BAT/)).toHaveCount(0);
});

test("academic reports: Vijayawada's coordinator gets Vijayawada figures, never Guntur's", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordVij);
  await page.goto("/academic/reports");
  await expect(page.getByRole("heading", { level: 2, name: "Curriculum delivered (branch)" })).toBeVisible();
  await expect(page.getByText(/NIT-GNT-BAT/)).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 2, name: "Certificate issue lead time" })).toBeVisible();
});
