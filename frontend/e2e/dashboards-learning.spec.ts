import { expect, test, type APIRequestContext } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * P3: Student Home, Trainer Today and the trainer / academic reports. Run against a freshly seeded dev database
 * (`flask --app app create-dev-db --yes && flask --app app seed-dev`). The Today flow itself is covered by trainer-u12.spec.ts.
 */

test.describe.configure({ mode: "serial" });

async function apiLogin(request: APIRequestContext, loginId: string) {
  const response = await request.post("/api/v1/auth/login", { data: { login: loginId, password: PASSWORD } });
  expect(response.ok()).toBeTruthy();
  const { data } = await response.json();
  return { token: data.token as string, userId: data.user.user_id as number };
}

test("student home leads with one thing to do, then four cards, and switches to Telugu", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await expect(page).toHaveURL(/\/dashboard$/);

  await expect(page.getByRole("heading", { level: 1, name: "Welcome, Anvitha K." })).toBeVisible();
  await expect(page.getByText("NIT-STU-2026-004182 · Guntur")).toBeVisible();

  // the hero: one sentence and one button
  const hero = page.getByRole("region", { name: "Up next" });
  await expect(hero).toBeVisible();
  await expect(hero.getByRole("button").or(hero.getByRole("link")).first()).toBeVisible();

  // four cards; Career, Support, Ask Nipuna and the certificate have left Home
  for (const title of ["Due Work", "Continue Learning", "Latest Released Recording", "Attendance Alert"]) {
    await expect(page.getByRole("heading", { level: 2, name: title, exact: true })).toBeVisible();
  }
  for (const gone of ["Career Support", "Ask Nipuna", "Certificate Status", "Upcoming Assignment / Test"]) {
    await expect(page.getByRole("heading", { level: 2, name: gone, exact: true })).toHaveCount(0);
  }
  // earlier specs release recordings and deliver classes, so check the shape rather than one fixed title
  const learning = page.locator("section", { has: page.getByRole("heading", { level: 2, name: "Continue Learning", exact: true }) });
  await expect(learning.getByRole("link", { name: "Open topic" })).toHaveAttribute("href", /\/topics\/\d+/);
  await expect(learning.getByText(/\d+ of \d+ topics done/)).toBeVisible();
  const recording = page.locator("section", { has: page.getByRole("heading", { level: 2, name: "Latest Released Recording", exact: true }) });
  await expect(recording.getByRole("link", { name: "All recordings" })).toHaveAttribute("href", "/materials");
  await expect(recording.getByText("Available", { exact: true })).toBeVisible();

  // language setting: the greeting, the hero and the card titles follow it
  await page.getByRole("button", { name: "తెలుగు" }).click();
  await expect(page.getByRole("heading", { level: 1, name: /^నమస్తే, / })).toBeVisible();
  await expect(page.getByRole("region", { name: "తర్వాత చేయాల్సినది" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "అభ్యాసం కొనసాగించండి" })).toBeVisible();
  const teluguRecording = page.locator("section", { has: page.getByRole("heading", { level: 2, name: "తాజా విడుదలైన రికార్డింగ్", exact: true }) });
  await expect(teluguRecording.getByText("అందుబాటులో ఉంది", { exact: true })).toBeVisible();
});

test("student home fits the phone with the hero first @mobile", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile", "phone layout only");
  await login(page, USERS.student);
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { level: 1, name: "Welcome, Anvitha K." })).toBeVisible();
  await expect(page.getByRole("region", { name: "Up next" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Continue Learning" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
});

test("trainer today: the next class or an empty day with tomorrow, and a to-do list with a button per item", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await expect(page).toHaveURL(/\/trainer$/);
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();

  // the stat tiles are gone: what needs the trainer is a to-do list with one button per row
  await expect(page.getByText("Assigned sessions scheduled")).toHaveCount(0);
  const todo = page.getByRole("region", { name: "To do" });
  await expect(todo).toBeVisible();
  await expect(todo.getByRole("link", { name: "Grade" }).first()).toBeVisible();
  await expect(todo.getByText(/assignments? to review/)).toBeVisible();

  // a day with a class leads with it; an empty day says so and shows tomorrow
  const next = page.getByRole("region", { name: /^Class: / });
  if ((await next.count()) === 0) {
    await expect(page.getByText("No class is scheduled for you today.")).toBeVisible();
    await expect(page.getByRole("region", { name: "Tomorrow" })).toBeVisible();
  } else {
    await expect(
      next
        .first()
        .getByText(/Next up|On now|Opened from your list|Class/)
        .first(),
    ).toBeVisible();
  }
  await page.getByText("How this works").click();
  await expect(page.getByText(/Trainers see only assigned batches and students/)).toBeVisible();
});

test("trainer reports: students at risk per batch with where to act, then a short summary", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.trainerG1);
  await page.goto("/trainer/reports");
  await expect(page.getByRole("heading", { level: 1, name: "Reports" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /^Students who need you/ })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Summary", exact: true })).toBeVisible();
  await expect(page.getByText(/NIT-GNT-BAT-2026-000001/).first()).toBeVisible();
  await expect(page.getByText(/Average attendance/)).toBeVisible();
  await expect(page.getByText(/Time to review/)).toBeVisible();
  await page.getByText("How this works").click();
  await expect(page.getByText(/Trainers see only assigned batches and students/)).toBeVisible();
  // another branch's batches never appear
  await expect(page.getByText(/NIT-VIJ-BAT/)).toHaveCount(0);
});

test("academic reports: the coordinator sees only their own branch", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.goto("/branch/reports");
  await expect(page.getByRole("heading", { level: 1, name: "Reports" })).toBeVisible();
  for (const title of ["Classes and attendance", "Completion and certificates", "Support and issues", "Progress by batch", "Last six months"]) {
    await expect(page.getByRole("heading", { level: 2, name: title, exact: true })).toBeVisible();
  }
  await expect(page.getByText("Classes held").first()).toBeVisible();
  await expect(page.getByText(/Data Science . Guntur/).first()).toBeVisible();
  await expect(page.getByText(/NIT-VIJ-BAT/)).toHaveCount(0);
});

test("academic reports: Vijayawada's coordinator gets Vijayawada figures, never Guntur's", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordVij);
  await page.goto("/branch/reports");
  await expect(page.getByRole("heading", { level: 2, name: "Classes and attendance" })).toBeVisible();
  await expect(page.getByText(/NIT-GNT-BAT/)).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 2, name: "Completion and certificates" })).toBeVisible();
});
