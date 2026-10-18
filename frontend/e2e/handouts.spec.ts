import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Role separation: the hand-out page ("Accounts to hand out" on Staff accounts) for the Super Admin and the Founder.
 * The seed has no split accounts (every staging user holds one role), so the test inserts one the way db/118 records it.
 * Set E2E_DB_NAME to the database the API under test uses (e.g. nipunalms_sweep-dev; psql must be on the PATH); without it the spec skips.
 */

test.describe.configure({ mode: "serial" });

const DB = process.env["E2E_DB_NAME"];
const RUN = Date.now().toString(36).slice(-6);
const EMAIL = `handout.${RUN}@nipuna.test`;
const NAME = `Handout Person ${RUN}`;

test.beforeAll(() => {
  if (!DB) return;
  execFileSync(
    "psql",
    [
      "-d",
      DB,
      "-v",
      "ON_ERROR_STOP=1",
      "-c",
      `WITH src AS (SELECT user_id FROM users WHERE email = 'trainer.g1@nipuna.test'),
            new AS (INSERT INTO users (full_name, email, password_hash, is_active, must_change_password)
                    VALUES ('${NAME}', '${EMAIL}', NULL, TRUE, TRUE) RETURNING user_id)
       INSERT INTO split_account_handouts (user_id, split_from_user_id, role_id, branch_id)
       SELECT new.user_id, src.user_id, (SELECT role_id FROM roles WHERE role_code = 'TRAINER'), 1 FROM new, src;`,
    ],
    { stdio: "pipe" },
  );
});

test("Super Admin gets the one-time link and marks the account handed out", async ({ page }, info) => {
  test.skip(!DB, "set E2E_DB_NAME to the scratch database to insert a split account");
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.admin);
  await page.goto("/admin/users");
  await expect(page.getByRole("heading", { name: "Staff accounts", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Accounts to hand out" })).toBeVisible();
  const row = page.getByRole("table", { name: "Accounts created by the role split" }).getByRole("row").filter({ hasText: EMAIL });
  await expect(row).toContainText("No link yet");
  await expect(row).toContainText("Not yet");

  await page.getByRole("button", { name: `Create activation link for ${EMAIL}` }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Create link" }).click();
  const secret = page.getByRole("dialog").filter({ hasText: `Activation link for ${NAME}` });
  await expect(secret).toBeVisible();
  await expect(secret.getByRole("textbox", { name: "Activation link" })).toHaveValue(/^https?:\/\/.+\/activate\?token=.+/);
  await secret.getByRole("button", { name: "Done", exact: true }).click();
  await expect(row).toContainText("Link active");

  await page.getByRole("button", { name: `Mark ${EMAIL} as handed out` }).click();
  await expect(page.getByText(`${NAME} marked as handed out`)).toBeVisible();
  await expect(row).not.toContainText("Not yet");
  await expect(page.getByRole("button", { name: `Mark ${EMAIL} as handed out` })).toHaveCount(0);
});

test("the Founder sees the same section on /founder/users", async ({ page }, info) => {
  test.skip(!DB, "set E2E_DB_NAME to the scratch database to insert a split account");
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.founder);
  await page.goto("/founder/users");
  await expect(page.getByRole("heading", { name: "Staff accounts", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Accounts to hand out" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Accounts created by the role split" }).getByRole("row").filter({ hasText: EMAIL })).toContainText(
    "Split from trainer.g1@nipuna.test",
  );
});
