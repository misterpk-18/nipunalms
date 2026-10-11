import { expect, test, type Page } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Staff dashboards (Academic, Branch, Super Admin, Founder) and the exception queues (P3). Needs the API on the dev
 * database seeded with `seed-dev`: Guntur has enrolments awaiting a batch seat (some for NIT-CRS-052, which has no
 * curriculum yet), two open recording exceptions and an escalated support request; Vijayawada has two recording
 * exceptions and nothing waiting for a seat.
 */

const RUN = Date.now().toString(36);

async function noHorizontalScroll(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
}

/** The tile with this label (tiles are role="group" cards, or links when they lead somewhere). */
function tile(page: Page, label: string) {
  const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return page
    .getByRole("group", { name: label })
    .or(page.getByRole("link", { name: new RegExp(`^${escaped}`) }))
    .first();
}

test.describe("Branch dashboard (academic work) and exception queue", () => {
  test("Guntur coordinator: tiles, batch risk note, quick links", async ({ page }) => {
    await login(page, USERS.coordGnt);
    await expect(page.getByRole("heading", { level: 1, name: "My work" })).toBeVisible();
    await expect(page.getByText("Guntur · what needs you today")).toBeVisible();
    // Counts depend on what earlier specs resolved, so the tiles are checked for shape, not for the seed's exact numbers
    await expect(tile(page, "Enrolments awaiting batch allocation")).toContainText(/\d/);
    await expect(tile(page, "Unfulfilled recording promises")).toContainText(/\d/);
    await expect(tile(page, "Academic results awaiting publication review")).toBeVisible();
    await expect(tile(page, "Batches delivery-ready")).toContainText("/");
    await expect(tile(page, "Open exceptions")).toContainText("awaiting a named owner");
    await expect(page.getByText("NIT-GNT-BAT-2026-000003:")).toHaveCount(0); // a batch with no curriculum yet is not at risk
    await expect(page.locator("#main").getByRole("link", { name: "Recordings" }).first()).toBeVisible();
    // the Vijayawada batch is not part of a Guntur view
    await expect(page.getByText("NIT-VIJ-BAT-2026-000001")).toHaveCount(0);
  });

  test("Vijayawada coordinator sees only Vijayawada", async ({ page }) => {
    await login(page, USERS.coordVij);
    await expect(page.getByText("Vijayawada · what needs you today")).toBeVisible();
    await expect(tile(page, "Enrolments awaiting batch allocation")).toContainText("0");
    await expect(tile(page, "Unfulfilled recording promises")).toContainText(/\d/);
    await expect(page.getByText("NIT-GNT-BAT-2026-000003")).toHaveCount(0);

    await page.goto("/branch/issues");
    await expect(page.getByRole("heading", { level: 1, name: "Issues" })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Recordings\s*\d+/ })).toBeVisible(); // the Vijayawada recording problem
    await expect(page.getByText("Guntur", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Student waiting for a batch")).toHaveCount(0);
  });

  test("the coordinator logs a recovery step and becomes the named owner", async ({ page }) => {
    await login(page, USERS.coordGnt);
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Issues", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Issues" })).toBeVisible();
    await page.getByLabel("Owner").selectOption({ label: "Nobody yet" });
    const row = page.getByRole("listitem").filter({ hasText: "Student waiting for a batch" }).filter({ hasText: "Nobody yet" }).first();
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: "Add note" }).click();
    const confirm = page.getByRole("dialog").getByRole("button", { name: "Add note" });
    await expect(confirm).toBeDisabled();
    await page.getByRole("dialog").getByLabel("Note").fill(`Batch proposed for the October intake ${RUN}`);
    await confirm.click();
    await expect(page.getByText("Note added. You now own this issue.")).toBeVisible();

    await page.getByLabel("Owner").selectOption({ label: "Mine" });
    await expect(page.getByText(/1 note/).first()).toBeVisible();
  });

  test("filter by type", async ({ page }) => {
    await login(page, USERS.coordGnt);
    await page.goto("/branch/issues");
    await page.getByRole("button", { name: /^Recordings\s*\d+/ }).click();
    await expect(page.getByText("Recording problem").first()).toBeVisible();
    await expect(page.getByText("Student waiting for a batch")).toHaveCount(0);
  });
});

test.describe("Branch dashboard", () => {
  test("Branch Manager: CRM figures are Unavailable, never zero; locked to the branch", async ({ page }) => {
    await login(page, USERS.bmGnt);
    await expect(page.getByRole("heading", { level: 1, name: "My work" })).toBeVisible();
    await expect(page.getByText("Guntur · what needs you today")).toBeVisible();
    for (const label of ["Branch verified collections against target", "Branch new paid Admissions", "Overdue branch follow-ups"]) {
      await expect(tile(page, label)).toContainText("Unavailable");
      await expect(tile(page, label)).toContainText("Not connected");
      await expect(tile(page, label)).not.toHaveText(/(^|\s)0(\s|$)/);
    }
    await expect(tile(page, "Running / starting batches")).toBeVisible();
    await expect(tile(page, "Schedule & recording exceptions")).toBeVisible();
    await expect(tile(page, "Open escalations & extension requests")).toContainText("Escalations 1");
    for (const link of ["Batches", "Student support", "Reports"]) {
      await expect(page.locator("#main").getByRole("link", { name: link }).first()).toBeVisible();
    }
    await expect(page.getByText("Finance and Admissions remain in the CRM. This view shows academic data for the locked branch only.")).toBeVisible();
    await expect(page.getByText("NIT-VIJ")).toHaveCount(0);
  });
});

test.describe("Super Admin home and issues", () => {
  test("home: Needs action, quick actions and the Setup checklist", async ({ page }) => {
    await login(page, USERS.admin);
    await expect(page.getByRole("heading", { name: "Super Admin home", level: 1 })).toBeVisible();
    await expect(page.getByRole("region", { name: "Needs action" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Setup checklist" })).toContainText("are working");
    await expect(page.getByRole("region", { name: "Quick actions" }).getByRole("link", { name: "Add staff user" })).toBeVisible();
    await expect(page.getByText("Integration Unavailable")).toHaveCount(0);
    await expect(page.getByText("Critical integration failures")).toHaveCount(0);
  });

  test("Issues: every branch in one paged list the Super Admin can assign from", async ({ page }) => {
    await login(page, USERS.admin);
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Issues", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Issues", level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Assign / }).first()).toBeVisible();
    await expect(page.getByText("Guntur").first()).toBeVisible();
    await expect(page.getByText("Vijayawada").first()).toBeVisible();
  });

  test("the Founder reads the issues but cannot assign or log notes", async ({ page }) => {
    await login(page, USERS.founder);
    await page.goto("/admin/exceptions");
    await expect(page).toHaveURL(/\/admin\/issues/);
    await expect(page.getByRole("heading", { name: "Issues", level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Assign / })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Add note" })).toHaveCount(0);
  });
});

test.describe("Founder overview", () => {
  test("tiles, the inbox and links", async ({ page, request }) => {
    const token = (await (await request.post("/api/v1/auth/login", { data: { login: USERS.founder, password: "Nipuna-staging-1" } })).json()).data.token;
    const summary = (await (await request.get("/api/v1/founder/summary", { headers: { Authorization: `Bearer ${token}` } })).json()).data;
    await login(page, USERS.founder);
    await expect(page.getByRole("heading", { name: "Founder / CEO home" })).toBeVisible();
    // the CRM tiles stay hidden until the CRM has sent its figures (U16)
    for (const label of ["Verified collections against target", "New paid Admissions against target", "Overdue amount"])
      await expect(page.getByRole("group", { name: label })).toHaveCount(summary.crm_connected ? 1 : 0);
    await expect(tile(page, "Active enrolments in delivery")).toContainText("Guntur");
    await expect(tile(page, "Active enrolments in delivery")).toContainText("Vijayawada");
    await expect(tile(page, "Batches at delivery risk")).toContainText("Meet organizer");
    await expect(tile(page, "Certificates waiting for a Branch Manager")).toBeVisible();

    const needs = page.getByRole("region", { name: "Needs you" });
    await expect(needs).toBeVisible();
    await expect(
      needs.getByRole("listitem").filter({ hasText: "Approve the monthly AI budget" }).or(needs.getByText("Nothing is waiting for you")),
    ).toBeVisible();
    await expect(page.locator("#main").getByRole("link", { name: "Branch views" })).toHaveCount(0); // the switcher in the header does this
  });
});

test.describe("@mobile staff dashboards", () => {
  test("@mobile coordinator dashboard and queue fit the screen", async ({ page }) => {
    await login(page, USERS.coordGnt);
    await expect(page.getByRole("heading", { level: 1, name: "My work" })).toBeVisible();
    await expect(tile(page, "Enrolments awaiting batch allocation")).toContainText(/\d/);
    await noHorizontalScroll(page);
    await page.goto("/branch/issues");
    await expect(page.getByRole("heading", { level: 1, name: "Issues" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add note" }).first()).toBeVisible();
    await noHorizontalScroll(page);
  });

  test("@mobile founder and branch views fit the screen", async ({ page }) => {
    await login(page, USERS.founder);
    await expect(page.getByRole("heading", { name: "Founder / CEO home" })).toBeVisible();
    await noHorizontalScroll(page);
    await page.goto("/admin/issues");
    await expect(page.getByRole("heading", { name: "Issues", level: 1 })).toBeVisible();
    await noHorizontalScroll(page);
  });
});
