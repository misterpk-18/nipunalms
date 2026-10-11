import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Batch and live-class operations (gap fix plan phase 6): the readiness record and state labels on a batch, the Meet
 * Operations page, and the student's preferred-slot card. Read-only against the seeded staging data.
 */

test.describe.configure({ mode: "serial" });

test("a coordinator sees state labels and the 7-point readiness record on a batch", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.goto("/branch/batches");

  // The list names states the way the people who run batches do, and says what each batch needs next
  const running = page.getByRole("row", { name: /NIT-GNT-BAT-2026-000001/ });
  await expect(running).toContainText("In progress");
  await expect(page.getByRole("row", { name: /NIT-GNT-BAT-2026-000003/ }).first()).toContainText("Draft");
  await expect(page.getByLabel("Show")).toContainText("Finished or cancelled");

  await running.getByRole("link", { name: /^Open / }).click();
  await expect(page.getByRole("list", { name: "Steps" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Requests" })).toBeVisible();
  await page.getByRole("tab", { name: "Checks" }).click();
  await expect(page.getByRole("heading", { name: "Checklist before confirming (7 points)" })).toBeVisible();
  await expect(page.getByText("1. Course and curriculum version")).toBeVisible();
  await expect(page.getByText(/^[1-7]\. /)).toHaveCount(7);

  // The Requests tab lists the batch's capacity, transfer, material-change and merge / split records
  await page.getByRole("tab", { name: "Requests" }).click();
  await expect(page.getByRole("heading", { name: "Capacity requests" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Transfer requests" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Material changes" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Merge and split" })).toBeVisible();
});

test("the Class day page loads with its sections", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.getByRole("link", { name: "Class day" }).first().click();
  await expect(page).toHaveURL(/\/branch\/class-day/);
  await expect(page.getByRole("heading", { name: "Class day", level: 1 })).toBeVisible();
  await expect(page.getByLabel("Date")).toBeVisible();
  for (const section of ["Open disruptions", "Replacements owed", "Classes waiting for approval", "Class logs not written"]) {
    await expect(page.getByRole("heading", { name: section })).toBeVisible();
  }
  // the Meet connection and the background checks are the Super Admin's, on the integration screen
  for (const gone of ["Meet integration", "Last background checks"]) await expect(page.getByRole("heading", { name: gone })).toHaveCount(0);
});

test("a student sees the preferred-slot card and the changes card", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.goto("/my-courses");
  await expect(page.getByRole("heading", { name: "Preferred slot" })).toBeVisible();
  await expect(page.getByText("A request does not reserve a seat.").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Changes needing your agreement" })).toBeVisible();
  await expect(page.getByText("Reading a notice is not agreement.")).toBeVisible();
});

// Flows below change data: run against a freshly seeded staging database.

test("the branch manager confirms the proposed weekend batch", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/batches");
  const proposed = page.getByRole("row", { name: /NIT-GNT-BAT-2026-000004/ });
  await expect(proposed).toContainText("Proposed");
  await proposed.getByRole("link", { name: /^Open / }).click();
  await page.getByRole("button", { name: "Confirm batch" }).click();
  const confirm = page.getByRole("dialog");
  const reason = confirm.getByLabel("Why this is acceptable *");
  if (await reason.count()) await reason.fill("Checked with the trainer");
  await confirm.getByRole("button", { name: "Confirm batch" }).click();
  await page.goto("/branch/batches");
  await expect(page.getByRole("row", { name: /NIT-GNT-BAT-2026-000004/ })).toContainText("Confirmed");
});

test("the student agrees to the timetable change", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.goto("/my-courses");
  await page.getByRole("button", { name: "Agree" }).first().click();
  await page.getByRole("dialog").getByRole("button", { name: "Agree" }).click();
  await expect(page.getByText("You agreed")).toBeVisible();
});
