import { expect, test } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * Academic Calendar (role separation decision 18): a Branch Manager proposes a closure for the session's branch and cannot decide it
 * (no Decide button, 403 from the API); the Super Admin decides it; the allocation queue shows each enrolment's allocation deadline.
 * Mutates data: run against a freshly seeded staging database.
 */

test.describe.configure({ mode: "serial" });

const TITLE = `Branch maintenance ${Date.now().toString(36).slice(-5)}`;
let closureId = 0;

test("a Branch Manager proposes a closure, it waits, and the Branch Manager cannot decide it", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/schedule");
  await page.getByRole("button", { name: "Propose a closure" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("From").fill("2026-12-24");
  await dialog.getByLabel("To (last day)").fill("2026-12-25");
  await dialog.getByLabel("Why is the branch closed?").fill(TITLE);
  await dialog.getByRole("button", { name: "Propose closure" }).click();
  const row = page.locator("li[data-closure]").filter({ hasText: TITLE });
  await expect(row).toContainText("Waiting for a decision");
  await expect(row.getByRole("button", { name: "Decide" })).toHaveCount(0);

  // the API refuses the Branch Manager's own decision as well
  const login_ = await request.post("/api/v1/auth/login", { data: { login: USERS.bmGnt, password: PASSWORD } });
  const token = ((await login_.json()) as { data: { token: string } }).data.token;
  const list = await request.get("/api/v1/calendar/closures", { headers: { Authorization: `Bearer ${token}` } });
  const found = ((await list.json()) as { data: { closure_id: number; title: string }[] }).data.find((c) => c.title === TITLE);
  expect(found).toBeTruthy();
  closureId = found!.closure_id;
  const decide = await request.post(`/api/v1/calendar/closures/${closureId}/decision`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { decision: "Approved" },
  });
  expect(decide.status()).toBe(403);
});

test("the Super Admin decides the proposed closure", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.admin);
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Academic calendar" }).click();
  await expect(page.getByRole("heading", { name: "Academic calendar", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "List" }).click();
  const row = page.locator("li[data-closure]").filter({ hasText: TITLE });
  await expect(row).toContainText("Waiting for a decision");
  await row.getByRole("button", { name: "Decide" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Decision").selectOption("Approved");
  await dialog.getByRole("button", { name: "Record decision" }).click();
  await expect(row).toContainText("Approved");
});

test("the Branch Manager's waiting list shows each enrolment's allocation deadline", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/waiting");
  await expect(page.getByText(/Allocate by/).first()).toBeVisible();
});
