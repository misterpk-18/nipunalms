import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Governance (gap fix plan phase 3): the Founder / CEO decides certificate requests (there is no curriculum approval any more); a correction is
 * requested by the Branch Manager and decided by the Super Admin; the Super Admin can switch AI off.
 * Mutates data: run against a freshly seeded staging database, after attendance.spec.ts.
 */

test.describe.configure({ mode: "serial" });

test("the founder has one Approvals inbox, and its certificate decisions page", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.founder);
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Approvals", exact: true }).click();
  await expect(page).toHaveURL(/\/founder\/approvals/);
  await expect(page.getByRole("heading", { level: 1, name: "Approvals" })).toBeVisible();
  await page.goto("/founder/certificates");
  await expect(page.getByRole("heading", { name: "Certificate decisions" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Waiting for you" })).toBeVisible();
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
  await page.goto("/admin/approvals");
  await page
    .getByRole("listitem")
    .filter({ hasText: /Correction to certificate NIT-CERT-2026-000001/ })
    .getByRole("link", { name: "Review" })
    .click();
  await page.getByRole("dialog").getByTestId("decision-bar").getByRole("button", { name: "Approve" }).click();
  await page
    .getByRole("alertdialog")
    .getByRole("button", { name: /Approve/ })
    .click();
  await expect(page.getByText("Correction approved")).toBeVisible();
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await login(page, USERS.bmGnt);
  await page.goto("/branch/completion?stage=issued");
  await expect(page.getByRole("listitem").filter({ hasText: "NIT-CERT-2026-000001" })).toContainText("version");
});

test("the super admin sees AI controls as ON or OFF per audience", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.admin);
  await page.goto("/admin/security");
  await expect(page).toHaveURL(/\/admin\/setup/);
  await page.goto("/admin/ai-controls");
  await expect(page.getByRole("heading", { name: "AI controls", level: 1 })).toBeVisible();
  for (const key of ["Student", "Staff", "All"]) await expect(page.locator(`[data-ai="${key}"]`)).toBeVisible();
});

test("public verification needs no sign-in @mobile", async ({ page }) => {
  await page.goto("/verify/NIT-CERT-2026-999999");
  await expect(page.getByRole("heading", { name: "Check a certificate" })).toBeVisible();
  await expect(page.getByText("Certificate not found")).toBeVisible();
});
