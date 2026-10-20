import { expect, test } from "@playwright/test";
import { login, USERS } from "./helpers";

test.describe("Google Workspace on Setup & health", () => {
  test("the Super Admin sees what is on, why nothing is stuck, and sets a branch's sender", async ({ page }) => {
    await login(page, USERS.admin);
    await page.goto("/admin/setup");
    await expect(page.getByRole("heading", { name: "Setup & health", level: 1 })).toBeVisible();

    await expect(page.getByRole("heading", { name: "Google Workspace" })).toBeVisible();
    for (const code of ["GOOGLE_MEET", "GOOGLE_DRIVE", "EMAIL"]) {
      await expect(page.locator(`[data-google="${code}"]`)).toContainText("Off");
    }
    await expect(page.getByText("Google is not connected yet")).toBeVisible();
    await expect(page.getByText("No Google call is stuck.")).toBeVisible();
    await expect(page.getByText("No email has failed.")).toBeVisible();

    // A branch's own email sender, then back to the branch mailbox
    const settings = page.locator("section", { has: page.getByRole("heading", { name: "Google settings for each branch" }) });
    const sender = settings.getByLabel("Email sender");
    await sender.fill("e2e-sender@example.test");
    await settings.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Google settings saved")).toBeVisible();
    await expect(page.getByText("Now: e2e-sender@example.test")).toBeVisible();

    await sender.fill("");
    await settings.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Now: e2e-sender@example.test")).toHaveCount(0);

    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
  });

  test("a Branch Manager has no Google screen", async ({ page }) => {
    await login(page, USERS.bmGnt);
    await page.goto("/admin/setup");
    await expect(page.getByRole("heading", { name: "Google Workspace" })).toHaveCount(0);
  });
});
