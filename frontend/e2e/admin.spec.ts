import { expect, test, type Page } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * Super Admin & security (slice S6): readiness registers, users & access, student accounts, CRM sync, audit log, and the
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
  test("integration readiness: statuses, update with evidence rules, audit", async ({ page }) => {
    await login(page, USERS.admin);
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Integration Readiness" }).click();
    await expect(page.getByRole("heading", { name: "Integration Readiness" })).toBeVisible();

    const meet = page.getByRole("row", { name: /Google Meet organizer — Guntur/ });
    await expect(meet).toContainText("Pending Verification");
    await expect(page.getByRole("row", { name: /WhatsApp/ }).first()).toContainText("Not Configured");
    await expect(page.getByText("nothing here is Live Verified without evidence")).toBeVisible();

    // A setup that is not Configured cannot be marked Verified
    await page.getByRole("button", { name: "Update WhatsApp" }).click();
    await page.getByLabel("Operational verification").selectOption("Verified");
    await page.getByLabel("Evidence").fill("Sent a test message");
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Only a Configured setup can be marked Verified").first()).toBeVisible();
    await page.getByRole("button", { name: "Cancel" }).click();

    const note = `Recording capability checked ${RUN}`;
    await page.getByRole("button", { name: "Update Google Drive recordings" }).click();
    await page.getByLabel("Notes").fill(note);
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Google Drive recordings updated")).toBeVisible();
    await expect(page.getByRole("row", { name: /Google Drive recordings/ })).toContainText(note);
  });

  test("security readiness: a control is verified with evidence", async ({ page }) => {
    await login(page, USERS.admin);
    await page.goto("/admin/security");
    await expect(page.getByRole("heading", { name: "Security Readiness" })).toBeVisible();
    await expect(page.getByRole("row", { name: /Server-side scope enforcement/ })).toContainText("Configured");

    const evidence = `Stale token refused after re-login ${RUN}`;
    await page.getByRole("button", { name: "Update Re-authentication for sensitive actions" }).click();
    await page.getByLabel("Operational verification").selectOption("Verified");
    await page.getByLabel("Evidence").fill(evidence);
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Re-authentication for sensitive actions updated")).toBeVisible();
    const row = page.getByRole("row", { name: /Re-authentication for sensitive actions/ });
    await expect(row).toContainText("Verified");
    await expect(row).toContainText(evidence);
  });

  test("users & access: create a trainer, temporary password must be changed, deactivate blocks sign-in", async ({ page }) => {
    const email = `trainer.e2e.${RUN}@nipuna.test`;
    await login(page, USERS.admin);
    await page.goto("/admin/users");
    await expect(page.getByRole("heading", { name: "Users & Access" })).toBeVisible();
    await expect(page.getByRole("row", { name: /Trainer R\. Sample/ })).toContainText("Trainer · NIT-GNT");

    await page.getByRole("button", { name: "Add staff user" }).click();
    const create = page.getByRole("dialog", { name: "Add staff user" });
    await create.getByLabel("Full name").fill(`Trainer E2E ${RUN}`);
    await create.getByLabel("Email", { exact: true }).fill(email);
    await create.getByLabel("Role", { exact: true }).selectOption("TRAINER");
    await create.getByLabel("Branch", { exact: true }).selectOption({ label: "Guntur (NIT-GNT)" });
    await create.getByRole("button", { name: "Create user" }).click();

    const temporary = await page.getByRole("textbox", { name: "Temporary password" }).inputValue();
    expect(temporary.length).toBeGreaterThanOrEqual(10);
    await page.getByRole("button", { name: "Done" }).click();

    await page.getByLabel("Search name or email").fill(email);
    const row = page.getByRole("row", { name: new RegExp(email) });
    await expect(row).toContainText("Must change password");

    // The new trainer signs in with the temporary password and is sent to change it
    const other = await page
      .context()
      .browser()!
      .newPage({ baseURL: page.url().split("/admin")[0] });
    await login(other, email, temporary);
    await expect(other).toHaveURL(/\/change-password/);
    await other.close();

    // Add a second role, then deactivate: sign-in stops working
    await page.getByRole("button", { name: `Add role to Trainer E2E ${RUN}` }).click();
    const addRole = page.getByRole("dialog", { name: /Add role for/ });
    await addRole.getByLabel("Role", { exact: true }).selectOption("ACADEMIC_COORDINATOR");
    await addRole.getByLabel("Branch", { exact: true }).selectOption({ label: "Guntur (NIT-GNT)" });
    await addRole.getByRole("button", { name: "Add role" }).click();
    await expect(page.getByText(`Role added for Trainer E2E ${RUN}`)).toBeVisible();
    await expect(row).toContainText("Academic Coordinator · NIT-GNT");

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

  test("student accounts: activation link shown once, suspend blocks sign-in, reactivate restores it", async ({ page, baseURL }) => {
    await login(page, USERS.admin);
    await page.goto("/admin/students");
    await expect(page.getByRole("heading", { name: "Student Accounts" })).toBeVisible();

    // Assisted activation for the learner still in Activation Pending
    await page.getByLabel("Student ID, name or email").fill("Sample Learner J.");
    await expect(page.getByRole("row", { name: /Sample Learner J\./ })).toContainText("Activation Pending");
    await page.getByRole("button", { name: "Open Sample Learner J." }).click();
    await page.getByRole("button", { name: /Reissue activation link|Issue activation link/ }).click();
    const link = await page.getByRole("textbox", { name: "Activation link" }).inputValue();
    expect(link).toContain("/activate?token=");
    await page.getByRole("button", { name: "Done" }).click();
    await page.keyboard.press("Escape");

    // Suspend an activated learner
    await page.getByLabel("Student ID, name or email").fill("Sample Learner C.");
    const row = page.getByRole("row", { name: /Sample Learner C\./ });
    await expect(row).toContainText("Activated");
    const code = (await row.locator(".font-mono").first().innerText()).trim();
    await page.getByRole("button", { name: "Open Sample Learner C." }).click();
    await page.getByRole("button", { name: "Suspend account" }).click();
    const suspend = page.getByRole("dialog", { name: "Suspend account" });
    await suspend.getByLabel("Reason").fill("E2E suspension check");
    await suspend.getByRole("button", { name: "Suspend", exact: true }).click();
    await expect(page.getByText("Account suspended", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("E2E suspension check").first()).toBeVisible();

    const student = await page.context().browser()!.newPage({ baseURL });
    await student.goto("/login");
    await student.getByLabel("Student ID or email", { exact: true }).fill(code);
    await student.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await student.getByRole("button", { name: "Sign in" }).click();
    await expect(student.getByText("Invalid login or password")).toBeVisible();

    await page.getByRole("button", { name: "Reactivate account" }).click();
    await expect(page.getByText("Account reactivated")).toBeVisible();
    await login(student, code);
    await expect(student).toHaveURL(/\/dashboard/);

    // Revoke sessions signs the student out everywhere
    await page.getByRole("button", { name: "Revoke sessions" }).click();
    await page.getByRole("button", { name: "Revoke sessions" }).last().click();
    await expect(page.getByText(/session(s)? ended/)).toBeVisible();
    await student.goto("/schedule");
    await expect(student).toHaveURL(/\/login/);
    await student.close();
  });

  test("CRM sync: failed event with payload, retry keeps the error until the cause is fixed", async ({ page }) => {
    await login(page, USERS.admin);
    await page.goto("/admin/crm-sync");
    await expect(page.getByRole("heading", { name: "CRM Sync" })).toBeVisible();
    await expect(page.getByText("Failed events", { exact: true })).toBeVisible();

    await page.getByLabel("Event status").selectOption("Failed");
    const failed = page.getByRole("row", { name: /AdmissionQualified/ }).first();
    await expect(failed).toContainText("Unknown course");
    await failed.getByRole("button", { name: /^View / }).click();
    await expect(page.getByRole("dialog").getByText("NIT-CRS-999").first()).toBeVisible();
    await page.keyboard.press("Escape");

    await failed.getByRole("button", { name: /^Retry / }).click();
    await expect(page.getByText(/Unknown course 'NIT-CRS-999'/).first()).toBeVisible();

    await page.getByRole("tab", { name: /Outbox/ }).click();
    await expect(page.getByRole("row", { name: /LmsAccountProvisioned/ }).first()).toContainText("Pending");
  });

  test("audit log shows the account actions with the actor and filters by action", async ({ page }) => {
    await login(page, USERS.admin);
    await page.goto("/admin/audit");
    await expect(page.getByRole("heading", { name: "Audit Log" })).toBeVisible();

    await page.getByLabel("Action", { exact: true }).selectOption("STUDENT_SUSPENDED");
    const row = page.getByRole("row", { name: /STUDENT_SUSPENDED/ }).first();
    await expect(row).toContainText("Super Admin");
    await expect(row).toContainText("activation_status");
    await expect(row).toContainText(/E2E suspension check|Duplicate enrolment under review/);
    await expect(page.getByRole("row", { name: /LOGIN/ })).toHaveCount(0);
  });
});

test.describe("boundaries", () => {
  test("the Founder reads but cannot change; a Branch Manager cannot open the admin screens", async ({ page }) => {
    await login(page, USERS.founder);
    await page.goto("/admin/users");
    await expect(page.getByRole("heading", { name: "Users & Access" })).toBeVisible();
    await expect(page.getByRole("row", { name: /Super Admin/ }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Add staff user" })).toHaveCount(0);
    await page.goto("/admin/integrations");
    await expect(page.getByRole("row", { name: /Google Meet organizer — Guntur/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Update / })).toHaveCount(0);
    await page.goto("/admin/audit");
    await expect(page.getByRole("heading", { name: "Audit Log" })).toBeVisible();
    await signOut(page);

    await login(page, USERS.bmGnt);
    await page.goto("/admin/users");
    await expect(page.getByText("Permission Restricted")).toBeVisible();
  });
});

test.describe("phone layout @mobile", () => {
  test.use({ viewport: { width: 360, height: 740 } });

  test("admin screens fit the phone @mobile", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile", "phone layout only");
    await login(page, USERS.admin);
    for (const path of ["/admin/integrations", "/admin/security", "/admin/users", "/admin/students", "/admin/crm-sync", "/admin/audit"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByText("Loading…")).toHaveCount(0);
      await noHorizontalScroll(page);
    }
  });
});
