import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Academic Calendar (gap fix plan phase 4): a Branch Manager records a branch closure (approved as recorded), the
 * Super Admin sees the calendar; the allocation queue shows each enrolment's allocation deadline.
 * Mutates data: run against a freshly seeded staging database.
 */

test.describe.configure({ mode: "serial" });

test("a branch manager records a branch closure and it is approved as recorded", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.goto("/branch/schedule");
  await page.getByRole("button", { name: "Add to the calendar" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("From").fill("2026-12-24");
  await dialog.getByLabel("To (inclusive)").fill("2026-12-25");
  await dialog.getByLabel("Title").fill("Branch maintenance");
  await dialog.getByRole("button", { name: "Add" }).click();
  await expect(page.getByText("Added to the calendar.")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("row", { name: /Branch maintenance/ }).first()).toContainText("Approved");
});

test("the super admin sees the academic calendar and the allocation deadlines", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.admin);
  await page.getByRole("link", { name: "Academic Calendar" }).click();
  await expect(page.getByRole("heading", { name: "Academic Calendar" })).toBeVisible();
  await expect(page.getByRole("row", { name: /Branch maintenance/ }).first()).toBeVisible();
  await page.goto("/branch/waiting");
  await expect(page.getByText(/Allocate by/).first()).toBeVisible();
});
