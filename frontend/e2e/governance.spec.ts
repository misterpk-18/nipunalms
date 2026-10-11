import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Governance (gap fix plan phase 3): the Founder / CEO approves curriculum and decides certificate requests; a correction is
 * requested by the Branch Manager and decided by the Super Admin; the Super Admin can switch AI off.
 * Mutates data: run against a freshly seeded staging database, after attendance.spec.ts.
 */

test.describe.configure({ mode: "serial" });

test("the founder has curriculum approvals and certificate decisions", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.founder);
  await page.getByRole("link", { name: "Curriculum Approvals" }).click();
  await expect(page.getByRole("heading", { name: "Curriculum approvals" })).toBeVisible();
  await page.getByRole("link", { name: "Certificate Decisions" }).click();
  await expect(page.getByRole("heading", { name: "Certificate decisions" })).toBeVisible();
  await expect(page.getByText("No certificate request is waiting for a decision.")).toBeVisible();
});

test("a branch manager's correction request is approved by the super admin", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.goto("/branch/completion?stage=issued");
  const card = page.getByRole("listitem").filter({ hasText: "NIT-CERT-2026-000001" });
  await expect(card).toBeVisible();
  // a run that already asked leaves the request waiting: then only the decision is left to test
  if ((await card.getByText("A change request is waiting for a decision").count()) === 0) {
    await card.getByRole("button", { name: "More" }).click();
    await page.getByRole("menuitem", { name: "Request a correction" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel(/Reason/).fill("Surname spelling");
    await dialog.getByLabel("Name to print").fill("Sample Learner A. Kumar");
    await dialog.getByRole("button", { name: "Request correction" }).click();
  }
  await expect(page.getByText("A change request is waiting for a decision").first()).toBeVisible();

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await login(page, USERS.admin);
  await page.goto("/branch/completion");
  await page.getByRole("button", { name: /Requests and fee releases/ }).click();
  const request = page.getByRole("row").filter({ has: page.getByRole("button", { name: "Decide" }) }).first();
  await request.getByRole("button", { name: "Decide" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Record decision" }).click();
  await expect(page.getByText("Correction approved.")).toBeVisible();
  await page.goto("/branch/completion?stage=issued");
  await expect(page.getByRole("listitem").filter({ hasText: "NIT-CERT-2026-000001" })).toContainText("version");
});

test("the super admin sees the AI controls", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.admin);
  await page.goto("/admin/security");
  await expect(page.getByRole("heading", { name: "AI controls" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Switch AI off" })).toBeVisible();
  await expect(page.getByText("AI has not been switched off.")).toBeVisible();
});

test("public verification needs no sign-in @mobile", async ({ page }) => {
  await page.goto("/verify/NIT-CERT-2026-999999");
  await expect(page.getByRole("heading", { name: "Certificate verification" })).toBeVisible();
  await expect(page.getByText(/No certificate with this number/)).toBeVisible();
});
