import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Governance (gap fix plan phase 3): the Founder / CEO approves curriculum and decides certificate requests; a correction is
 * requested by the coordinator and decided by the Branch Manager; the Super Admin can switch AI off.
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

test("a correction is requested by the coordinator and approved by the branch manager", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.coordGnt);
  await page.goto("/academic/certificates");
  const row = page.getByRole("row", { name: /NIT-CERT-2026-000001.*Issued/ });
  await row.getByRole("button", { name: "Request correction" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(/Reason/).fill("Surname spelling");
  await dialog.getByLabel("Name to print").fill("Sample Learner A. Kumar");
  await dialog.getByRole("button", { name: "Request" }).click();
  await expect(page.getByText("Correction requested; an independent approver decides it.")).toBeVisible();
  await expect(page.getByRole("row", { name: /NIT-CERT-2026-000001.*Issued/ })).toContainText("Correction requested");

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await login(page, USERS.bmGnt);
  await page.goto("/branch/reports");
  const request = page.getByRole("row", { name: /Surname spelling/ });
  await request.getByRole("button", { name: "Decide" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Record decision" }).click();
  await expect(page.getByText("Correction approved.")).toBeVisible();
  await expect(page.getByRole("row", { name: /Sample Learner A\. Kumar/ })).toContainText("Issued");
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
