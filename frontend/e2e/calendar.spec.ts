import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Academic Calendar (gap fix plan phase 4): a coordinator proposes a branch closure, the Branch Manager approves it, the
 * Super Admin sees the calendar; the allocation queue shows each enrolment's allocation deadline.
 * Mutates data: run against a freshly seeded staging database.
 */

test.describe.configure({ mode: "serial" });

test("a coordinator proposes a branch closure and the branch manager approves it", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.goto("/academic/schedule");
  await page.getByRole("button", { name: "Add to the calendar" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("From").fill("2026-12-24");
  await dialog.getByLabel("To (inclusive)").fill("2026-12-25");
  await dialog.getByLabel("Title").fill("Branch maintenance");
  await dialog.getByRole("button", { name: "Add" }).click();
  await expect(page.getByText("Proposed; the Branch Manager approves it.")).toBeVisible();

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await login(page, USERS.bmGnt);
  await page.goto("/branch/operations");
  await page.getByRole("row", { name: /Branch maintenance/ }).getByRole("button", { name: "Decide" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Record decision" }).click();
  await expect(page.getByText("Closure approved.")).toBeVisible();
  await expect(page.getByRole("row", { name: /Branch maintenance/ })).toContainText("Approved");
});

test("the super admin sees the academic calendar and the allocation deadlines", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.admin);
  await page.getByRole("link", { name: "Academic Calendar" }).click();
  await expect(page.getByRole("heading", { name: "Academic Calendar" })).toBeVisible();
  await expect(page.getByRole("row", { name: /Branch maintenance/ })).toBeVisible();
  await page.goto("/academic/batches");
  await expect(page.getByRole("columnheader", { name: "Allocate by" })).toBeVisible();
});
