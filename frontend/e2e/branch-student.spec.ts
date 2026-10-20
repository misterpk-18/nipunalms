import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/** The Branch Manager's student page, opened from the name on Waiting for a batch. Read-only: nothing is created or changed. */
test("a waiting student's name opens the Branch Manager's student page", async ({ page }) => {
  await page.goto("/login");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/waiting");
  await expect(page.getByRole("heading", { level: 1, name: "Waiting for a batch" })).toBeVisible();

  await expect(page.getByRole("status").filter({ hasText: /students? waiting/ })).toContainText(/\d+/);
  const first = page.getByRole("list", { name: "Students waiting for a batch" }).getByRole("listitem").first();
  test.skip((await first.count()) === 0, "nobody is waiting for a batch on this database");
  const link = first.getByRole("link").first();
  const code = (await link.textContent())?.match(/NIT-STU-\d{4}-\d+/)?.[0];
  expect(code).toBeTruthy();
  await link.click();

  await expect(page).toHaveURL(/\/branch\/students\/\d+$/);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText(code!).first()).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Student" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Courses" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Admissions" })).toBeVisible();
  // a waiting student has a course with no batch yet, so Allocate leads back to Waiting for that student
  await page.getByRole("link", { name: "Allocate" }).first().click();
  await expect(page).toHaveURL(new RegExp(`/branch/waiting\\?q=${code}`));
});
