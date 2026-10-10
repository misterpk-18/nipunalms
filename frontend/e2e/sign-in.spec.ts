import { expect, test } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

const RUN = Date.now().toString(36);

test.describe("sign-in and accounts", () => {
  test("one clean form, with the reset and activation links beside it", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByLabel("Student ID or email", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Forgot password?" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Activate your account" })).toBeVisible();
    // The old step list and the policy notes are gone from the page
    await expect(page.getByText("Account activation status")).toHaveCount(0);
    await expect(page.getByText("Course Access Released")).toHaveCount(0);

    await page.getByRole("link", { name: "Activate your account" }).click();
    await expect(page).toHaveURL(/\/activate$/);
    await expect(page.getByText(/Open the activation link your branch sent you/)).toBeVisible();
  });

  test("forgot password: the answer never says whether the account exists", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("link", { name: "Forgot password?" }).click();
    await expect(page.getByRole("heading", { name: "Reset your password" })).toBeVisible();
    await page.getByLabel("Student ID or email", { exact: true }).fill("nobody.at.all@nipuna.test");
    await expect(page.getByLabel("Student ID or email", { exact: true })).toHaveValue("nobody.at.all@nipuna.test");
    await page.getByRole("button", { name: "Send me a code" }).click();
    await expect(page.getByText("If the account exists, we've sent a code.")).toBeVisible();

    // The save button needs a 6-digit code and a valid, matching password
    const save = page.getByRole("button", { name: "Save new password" });
    await expect(save).toBeDisabled();
    await page.getByLabel("6-digit code").fill("123456");
    await page.getByLabel("New password", { exact: true }).fill("a-long-enough-password");
    await page.getByLabel("Confirm password").fill("a-long-enough-password");
    await expect(page.getByText("Both passwords match")).toBeVisible();
    await expect(save).toBeEnabled();
    await save.click();
    await expect(page.getByRole("alert")).toContainText("wrong or has expired");
  });

  test("an unknown activation link says so and points to the branch", async ({ page }) => {
    await page.goto("/activate?token=not-a-real-token");
    await expect(page.getByText("We can't find this activation link.")).toBeVisible();
    await expect(page.getByText("Ask your branch for a new link.")).toBeVisible();
  });

  test("a new staff member opens the invite link, chooses a password and is signed in", async ({ page }) => {
    const email = `invitee.${RUN}@nipuna.test`;
    await login(page, USERS.admin);
    await page.goto("/admin/users");
    await page.getByRole("button", { name: "Add staff user" }).click();
    const create = page.getByRole("dialog", { name: "Add staff user" });
    await create.getByLabel("Full name").fill(`Invitee ${RUN}`);
    await create.getByLabel("Email", { exact: true }).fill(email);
    await create.getByLabel("Role", { exact: true }).selectOption("TRAINER");
    await create.getByLabel("Branch", { exact: true }).selectOption({ label: "Guntur (NIT-GNT)" });
    await create.getByRole("button", { name: "Create user" }).click();
    const link = await page.getByRole("textbox", { name: "Invite link" }).inputValue();
    expect(link).toContain("/activate?token=");
    await page.getByRole("button", { name: "Done" }).click();

    const invitee = await page
      .context()
      .browser()!
      .newPage({ baseURL: page.url().split("/admin")[0] });
    await invitee.goto(new URL(link).pathname + new URL(link).search);
    await expect(invitee.getByText(`Welcome, Invitee ${RUN}`)).toBeVisible();
    const activate = invitee.getByRole("button", { name: "Activate account" });
    await expect(activate).toBeDisabled();
    await invitee.getByLabel("Choose your password").fill("short");
    await expect(invitee.getByText("At least 10 characters")).toBeVisible();
    await invitee.getByLabel("Choose your password").fill("A-chosen-passw0rd");
    await invitee.getByLabel("Confirm password").fill("A-chosen-passw0rd");
    await expect(activate).toBeEnabled();
    await activate.click();

    await expect(invitee.getByRole("heading", { name: "Your account is ready" })).toBeVisible();
    await invitee.getByRole("button", { name: "Go to Home" }).click();
    await expect(invitee).toHaveURL(/\/trainer/);
    await expect(invitee).not.toHaveURL(/change-password/);

    // The link works once
    await invitee.goto(new URL(link).pathname + new URL(link).search);
    await expect(invitee.getByText("This activation link has already been used")).toBeVisible();
    await invitee.close();

    // Clean up: deactivate the account
    await page.getByLabel("Search name or email").fill(email);
    await page.getByRole("button", { name: `Deactivate Invitee ${RUN}` }).click();
    const deactivate = page.getByRole("dialog", { name: "Deactivate account" });
    await deactivate.getByLabel("Reason").fill("E2E clean-up");
    await deactivate.getByRole("button", { name: "Deactivate", exact: true }).click();
    await expect(page.getByText(`Invitee ${RUN} deactivated`)).toBeVisible();
  });

  test("a signed-in person changes their password with live checks and a confirmation", async ({ page }) => {
    // Uses a throwaway account so the shared staging passwords stay untouched
    const email = `changer.${RUN}@nipuna.test`;
    await login(page, USERS.admin);
    await page.goto("/admin/users");
    await page.getByRole("button", { name: "Add staff user" }).click();
    const create = page.getByRole("dialog", { name: "Add staff user" });
    await create.getByLabel("Full name").fill(`Changer ${RUN}`);
    await create.getByLabel("Email", { exact: true }).fill(email);
    await create.getByLabel("Role", { exact: true }).selectOption("TRAINER");
    await create.getByLabel("Branch", { exact: true }).selectOption({ label: "Guntur (NIT-GNT)" });
    await create.getByRole("button", { name: "Create user" }).click();
    const temporary = await page.getByRole("textbox", { name: "Temporary password" }).inputValue();
    await page.getByRole("button", { name: "Done" }).click();

    const other = await page
      .context()
      .browser()!
      .newPage({ baseURL: page.url().split("/admin")[0] });
    await login(other, email, temporary);
    await expect(other).toHaveURL(/\/change-password/);
    const submit = other.getByRole("button", { name: "Change password" });
    await other.getByLabel("Current password").fill(temporary);
    await other.getByLabel("New password", { exact: true }).fill(temporary);
    await other.getByLabel("Confirm password").fill(temporary);
    await expect(submit).toBeDisabled(); // the new password must differ from the current one
    await other.getByLabel("New password", { exact: true }).fill(PASSWORD + "-changed");
    await other.getByLabel("Confirm password").fill(PASSWORD + "-changed");
    await expect(other.getByText("Different from your current password")).toBeVisible();
    await submit.click();
    await expect(other.getByText("Password changed.")).toBeVisible();
    await other.close();

    await page.getByLabel("Search name or email").fill(email);
    await page.getByRole("button", { name: `Deactivate Changer ${RUN}` }).click();
    const deactivate = page.getByRole("dialog", { name: "Deactivate account" });
    await deactivate.getByLabel("Reason").fill("E2E clean-up");
    await deactivate.getByRole("button", { name: "Deactivate", exact: true }).click();
    await expect(page.getByText(`Changer ${RUN} deactivated`)).toBeVisible();
  });

  test("an unknown certificate number gets a clear 'not found' message", async ({ page }) => {
    await page.goto("/verify/NIT-CERT-DOES-NOT-EXIST");
    await expect(page.getByRole("heading", { name: "Check a certificate" })).toBeVisible();
    await expect(page.getByText("Certificate not found")).toBeVisible();
  });
});
