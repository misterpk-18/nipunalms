import { expect, test, type Page } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * Super Admin & security (slice S6, reshaped in U17): Setup & health, users & access, student accounts, CRM sync, audit log, and the
 * Founder / Branch Manager boundaries. Needs the API on the dev database seeded with `seed-dev` (staging users).
 */

const RUN = Date.now().toString(36);

async function signOut(page: Page) {
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
}

async function noHorizontalScroll(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
}

test.describe("Super Admin", () => {
  test("setup & health: one checklist with plain states, an evidence rule for Working and a staff owner", async ({ page }) => {
    await login(page, USERS.admin);
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Setup & health" }).click();
    await expect(page.getByRole("heading", { name: "Setup & health", level: 1 })).toBeVisible();

    await expect(page.locator('[data-setup="MEET_ORGANIZER_GNT"]')).toContainText("Not set up");
    await expect(page.locator('[data-setup="WHATSAPP"]')).toContainText("Not set up");
    await expect(page.getByText("Integration Unavailable")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Meet and class checks" })).toBeVisible();

    // Working needs a note of how it was checked
    await page.getByRole("button", { name: "Update WhatsApp" }).click();
    await page.getByLabel("Where does it stand?").selectOption("Working");
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Verification needs an evidence note").first()).toBeVisible();
    await page.getByRole("button", { name: "Cancel" }).click();

    const note = `Recording capability checked ${RUN}`;
    await page.getByRole("button", { name: "Update Google Drive recordings" }).click();
    await page.getByLabel("Owner").selectOption({ label: "Super Admin (Super Admin)" });
    await page.getByLabel("Notes").fill(note);
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Google Drive recordings updated")).toBeVisible();
    const row = page.locator('[data-setup="GOOGLE_DRIVE_RECORDINGS"]');
    await expect(row).toContainText(note);
    await expect(row).toContainText("Owner: Super Admin");

    // The old addresses land here
    await page.goto("/admin/integrations");
    await expect(page).toHaveURL(/\/admin\/setup/);
    await page.goto("/admin/security");
    await expect(page).toHaveURL(/\/admin\/setup/);
  });

  test("setup & health: a security setting is marked Working with evidence", async ({ page }) => {
    await login(page, USERS.admin);
    await page.goto("/admin/setup");
    await expect(page.locator('[data-setup="SCOPE_ENFORCEMENT"]')).toContainText("Set up");

    const evidence = `Stale token refused after re-login ${RUN}`;
    await page.getByRole("button", { name: "Update Re-authentication for sensitive actions" }).click();
    await page.getByLabel("Where does it stand?").selectOption("Working");
    await page.getByLabel("How you checked it").fill(evidence);
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Re-authentication for sensitive actions updated")).toBeVisible();
    const row = page.locator('[data-setup="FRESH_AUTH"]');
    await expect(row).toContainText("Working");
    await expect(row).toContainText(evidence);
  });

  test("users & access: create a trainer, temporary password must be changed, deactivate blocks sign-in", async ({ page }) => {
    const email = `trainer.e2e.${RUN}@nipuna.test`;
    await login(page, USERS.admin);
    await page.goto("/admin/users");
    await expect(page.getByRole("heading", { name: "Users & access" })).toBeVisible();
    await expect(page.getByRole("row", { name: /Trainer R\. Sample/ })).toContainText("Trainer · NIT-GNT");

    await page.getByRole("button", { name: "Add staff user" }).click();
    const create = page.getByRole("dialog", { name: "Add staff user" });
    await create.getByLabel("Full name").fill(`Trainer E2E ${RUN}`);
    await create.getByLabel("Email", { exact: true }).fill(email);
    await create.getByLabel("Role", { exact: true }).selectOption("TRAINER");
    await expect(create.getByText("Runs classes, marks attendance and grades work for their batches.", { exact: true })).toBeVisible();
    await create.getByLabel("Branch", { exact: true }).selectOption({ label: "Guntur (NIT-GNT)" });
    await create.getByRole("button", { name: "Create user" }).click();

    const temporary = await page.getByRole("textbox", { name: "Temporary password" }).inputValue();
    expect(temporary.length).toBeGreaterThanOrEqual(10);
    await page.getByRole("button", { name: "Done" }).click();

    await page.getByLabel("Search name or email").fill(email);
    const row = page.getByRole("row", { name: new RegExp(email) });
    await expect(row).toContainText("Must change password");
    await expect(page.getByRole("button", { name: `Resend invite to Trainer E2E ${RUN}` })).toBeVisible();

    // The new trainer signs in with the temporary password and is sent to change it
    const other = await page
      .context()
      .browser()!
      .newPage({ baseURL: page.url().split("/admin")[0] });
    await login(other, email, temporary);
    await expect(other).toHaveURL(/\/change-password/);
    await other.close();

    // There is no "Add role": an account holds one role. Then deactivate: sign-in stops working
    await expect(page.getByRole("button", { name: `Add role to Trainer E2E ${RUN}` })).toHaveCount(0);

    await page.getByRole("button", { name: `Deactivate Trainer E2E ${RUN}` }).click();
    const deactivate = page.getByRole("dialog", { name: "Deactivate account" });
    await deactivate.getByLabel("Reason").fill("E2E clean-up");
    await deactivate.getByRole("button", { name: "Deactivate", exact: true }).click();
    await expect(page.getByText(`Trainer E2E ${RUN} deactivated`)).toBeVisible();

    const blocked = await page
      .context()
      .browser()!
      .newPage({ baseURL: page.url().split("/admin")[0] });
    await blocked.goto("/login");
    await blocked.getByLabel("Student ID or email", { exact: true }).fill(email);
    await blocked.getByLabel("Password", { exact: true }).fill(temporary);
    await blocked.getByRole("button", { name: "Sign in" }).click();
    await expect(blocked).toHaveURL(/\/login/);
    await expect(blocked.getByText("Invalid login or password")).toBeVisible();
    await blocked.close();
  });

  test("student accounts: the student's page, send a new link, suspend blocks sign-in, reactivate restores it", async ({ page, baseURL }) => {
    await login(page, USERS.admin);
    await page.goto("/admin/students");
    await expect(page.getByRole("heading", { name: "Student accounts", level: 1 })).toBeVisible();

    // Assisted activation for the learner still in Activation Pending: the student opens as a page, not a modal
    await page.getByLabel("Student ID, name, mobile, admission number or email").fill("Sample Learner J.");
    await expect(page.getByRole("row", { name: /Sample Learner J\./ })).toContainText("Waiting to activate");
    await page.getByRole("link", { name: "Open Sample Learner J." }).click();
    await expect(page).toHaveURL(/\/admin\/students\/\d+$/);
    await expect(page.getByRole("region", { name: "Suggested next step" })).toBeVisible();
    await page
      .getByRole("region", { name: "Suggested next step" })
      .getByRole("button", { name: /Send new link|Send activation link/ })
      .click();
    const link = await page.getByRole("textbox", { name: "Activation link" }).inputValue();
    expect(link).toContain("/activate?token=");
    await page.getByRole("button", { name: "Done" }).click();

    // Suspend an activated learner
    await page.goto("/admin/students");
    await page.getByLabel("Student ID, name, mobile, admission number or email").fill("Sample Learner C.");
    const row = page.getByRole("row", { name: /Sample Learner C\./ });
    await expect(row).toContainText("Activated");
    const code = (await row.locator(".font-mono").first().innerText()).trim();
    await page.getByRole("link", { name: "Open Sample Learner C." }).click();
    await page.getByRole("button", { name: "Suspend account" }).click();
    const suspend = page.getByRole("dialog", { name: "Suspend account" });
    await suspend.getByLabel("Reason").fill("E2E suspension check");
    await suspend.getByRole("button", { name: "Suspend", exact: true }).click();
    await expect(page.getByText("Account suspended", { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/suspended the account of Sample Learner C\./).first()).toBeVisible();

    const student = await page.context().browser()!.newPage({ baseURL });
    await student.goto("/login");
    await student.getByLabel("Student ID or email", { exact: true }).fill(code);
    await student.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await student.getByRole("button", { name: "Sign in" }).click();
    await expect(student.getByText("Invalid login or password")).toBeVisible();

    await page.getByRole("region", { name: "Suggested next step" }).getByRole("button", { name: "Reactivate account" }).click();
    await expect(page.getByText("Account reactivated")).toBeVisible();
    await login(student, code);
    await expect(student).toHaveURL(/\/dashboard/);

    // Signing out everywhere ends the student's session
    await page.getByRole("button", { name: "Sign out everywhere" }).click();
    await page.getByRole("button", { name: "Sign out everywhere" }).last().click();
    await expect(page.getByText(/session(s)? ended/)).toBeVisible();
    await student.goto("/schedule");
    await expect(student).toHaveURL(/\/login/);
    await student.close();
  });

  test("CRM sync: opens on what needs attention with a plain cause; retry keeps the reason until the cause is fixed", async ({ page }) => {
    await login(page, USERS.admin);
    await page.goto("/admin/crm-sync");
    await expect(page.getByRole("heading", { name: "CRM sync", level: 1 })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Needs attention/ })).toHaveAttribute("aria-selected", "true");

    const failed = page.getByRole("listitem").filter({ hasText: "NIT-CRS-999" }).first();
    await expect(failed).toContainText("has not reached the LMS yet");
    await failed.getByRole("button", { name: /^Details/ }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText("A student's admission was confirmed", { exact: false }).first()).toBeVisible();
    await expect(dialog.getByText("NIT-CRS-999", { exact: false }).first()).toBeVisible();
    await dialog.getByRole("button", { name: "Technical details" }).click();
    await expect(dialog.getByRole("heading", { name: "What the CRM sent" })).toBeVisible();
    await page.keyboard.press("Escape");

    await failed.getByRole("button", { name: /^Retry/ }).click();
    await expect(page.getByRole("listitem").filter({ hasText: "NIT-CRS-999" }).first()).toContainText("has not reached the LMS yet");

    await page.getByRole("tab", { name: /Sent to the CRM/ }).click();
    await expect(page.getByRole("row", { name: /LmsAccountProvisioned/ }).first()).toContainText("Waiting");
  });

  test("audit log reads as sentences, with presets, a last-7-days range and a CSV", async ({ page }) => {
    await login(page, USERS.admin);
    await page.goto("/admin/audit");
    await expect(page.getByRole("heading", { name: "Audit log", level: 1 })).toBeVisible();

    await page.getByRole("button", { name: "Accounts", exact: true }).click();
    const first = page.getByRole("list", { name: "Audit entries" }).getByRole("listitem").first();
    await expect(first).toContainText(/account|password|invite|link|signed|activated/i);
    await expect(page.getByRole("list", { name: "Audit entries" }).getByText("signed in")).toHaveCount(0);
    await first.getByText("Details").click();
    await expect(first.getByText(/Reason given|Record|·/).first()).toBeVisible();

    await page.getByRole("button", { name: "Last 7 days" }).click();
    await expect(page.getByRole("button", { name: "Last 7 days" })).toHaveAttribute("aria-pressed", "true");
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download CSV" }).click();
    expect((await download).suggestedFilename()).toBe("audit-log.csv");
  });
});

test.describe("boundaries", () => {
  test("the Founder reads but cannot change; a Branch Manager cannot open the admin screens", async ({ page }) => {
    await login(page, USERS.founder);
    await page.goto("/admin/users");
    await expect(page.getByRole("heading", { name: "Users & access" })).toBeVisible();
    await expect(page.getByRole("row", { name: /Super Admin/ }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Add staff user" })).toHaveCount(0);
    await page.goto("/admin/setup");
    await expect(page.locator('[data-setup="MEET_ORGANIZER_GNT"]')).toBeVisible();
    await expect(page.getByRole("button", { name: /^Update / })).toHaveCount(0);
    await page.goto("/admin/audit");
    await expect(page.getByRole("heading", { name: "Audit log", level: 1 })).toBeVisible();
    await signOut(page);

    await login(page, USERS.bmGnt);
    await page.goto("/admin/users");
    await expect(page.getByText(/cannot open this workspace/)).toBeVisible();
  });
});

test.describe("phone layout @mobile", () => {
  test.use({ viewport: { width: 360, height: 740 } });

  test("admin screens fit the phone @mobile", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile", "phone layout only");
    await login(page, USERS.admin);
    for (const path of [
      "/admin",
      "/admin/setup",
      "/admin/ai-controls",
      "/admin/users",
      "/admin/students",
      "/admin/crm-sync",
      "/admin/calendar",
      "/admin/calendar?view=list",
      "/admin/issues",
      "/admin/audit",
    ]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByText("Loading…")).toHaveCount(0);
      await noHorizontalScroll(page);
    }
  });
});
