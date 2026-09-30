import { expect, test, type Page } from "@playwright/test";
import { USERS, login } from "./helpers";

/**
 * Staff dashboards (Academic, Branch, Super Admin, Founder) and the exception queues (P3). Needs the API on the dev
 * database seeded with `seed-dev`: Guntur has four Curriculum Mapping Pending enrolments, one awaiting allocation,
 * two open recording exceptions and an escalated support request; Vijayawada has two recording exceptions and nothing
 * waiting for a seat.
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

test.describe("Academic dashboard and exception queue", () => {
  test("Guntur coordinator: tiles, batch risk note, quick links", async ({ page }) => {
    await login(page, USERS.coordGnt);
    await expect(page.getByRole("heading", { name: "Academic dashboard" })).toBeVisible();
    await expect(page.getByText("Guntur · LMS academic domain")).toBeVisible();
    await expect(tile(page, "Enrolments awaiting batch allocation")).toContainText("5");
    await expect(tile(page, "Enrolments awaiting batch allocation")).toContainText("Curriculum Mapping Pending (4)");
    await expect(tile(page, "Unfulfilled recording promises")).toContainText("2");
    await expect(tile(page, "Academic results awaiting publication review")).toBeVisible();
    await expect(tile(page, "Batches delivery-ready")).toContainText("/");
    await expect(tile(page, "Open exceptions")).toContainText("awaiting a named owner");
    await expect(page.getByText("NIT-GNT-BAT-2026-000003: Curriculum Mapping Pending")).toBeVisible();
    await expect(page.getByText("Four distinct records")).toBeVisible();
    await expect(page.locator("#main").getByRole("link", { name: "Recording exceptions" })).toBeVisible();
    // the Vijayawada batch is not part of a Guntur view
    await expect(page.getByText("NIT-VIJ-BAT-2026-000001")).toHaveCount(0);
  });

  test("Vijayawada coordinator sees only Vijayawada", async ({ page }) => {
    await login(page, USERS.coordVij);
    await expect(page.getByText("Vijayawada · LMS academic domain")).toBeVisible();
    await expect(tile(page, "Enrolments awaiting batch allocation")).toContainText("0");
    await expect(tile(page, "Unfulfilled recording promises")).toContainText("2");
    await expect(page.getByText("NIT-GNT-BAT-2026-000003")).toHaveCount(0);

    await page.goto("/academic/exceptions");
    await expect(page.getByRole("heading", { name: "Exception / Recovery queue" })).toBeVisible();
    await expect(page.getByRole("row", { name: /RX-0014/ })).toBeVisible();
    await expect(page.getByRole("row", { name: /ENR-/ })).toHaveCount(0);
  });

  test("the coordinator logs a recovery step and becomes the named owner", async ({ page }) => {
    await login(page, USERS.coordGnt);
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Exceptions", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Exception / Recovery queue" })).toBeVisible();
    const row = page.getByRole("row").filter({ hasText: "Curriculum Mapping Pending" }).filter({ hasText: "Awaiting named owner" }).first();
    await expect(row).toContainText("Awaiting named owner");
    await expect(row).toContainText("Academic Coordinator — Guntur");
    const reference = (await row.getByRole("cell").first().innerText()).trim();

    await row.getByRole("button", { name: /^Update ENR-/ }).click();
    const confirm = page.getByRole("button", { name: "Log recovery step" });
    await expect(confirm).toBeDisabled();
    await page.getByLabel("What was done, or will be done").fill(`Curriculum v2 sent for approval ${RUN}`);
    await confirm.click();
    await expect(page.getByText("Recovery step logged.")).toBeVisible();

    const updated = page.getByRole("row", { name: new RegExp(reference) });
    await expect(updated).toContainText("Recovery In Progress");
    await expect(updated).toContainText("Coordinator");
    await expect(updated).not.toContainText("Awaiting named owner");
    await expect(updated).toContainText("recovery step");
  });

  test("filter by type", async ({ page }) => {
    await login(page, USERS.coordGnt);
    await page.goto("/academic/exceptions");
    await page.getByLabel("Exception type").selectOption({ label: "Recording" });
    await expect(page.getByRole("row", { name: /RX-0012/ })).toBeVisible();
    await expect(page.getByRole("row", { name: /ENR-/ })).toHaveCount(0);
  });
});

test.describe("Branch dashboard", () => {
  test("Branch Manager: CRM figures are Unavailable, never zero; locked to the branch", async ({ page }) => {
    await login(page, USERS.bmGnt);
    await expect(page.getByRole("heading", { name: "Branch academic dashboard" })).toBeVisible();
    await expect(page.getByText("Guntur · LMS academic domain")).toBeVisible();
    for (const label of ["Branch verified collections against target", "Branch new paid Admissions", "Overdue branch follow-ups"]) {
      await expect(tile(page, label)).toContainText("Unavailable");
      await expect(tile(page, label)).toContainText("Not Configured");
      await expect(tile(page, label)).not.toHaveText(/(^|\s)0(\s|$)/);
    }
    await expect(tile(page, "Running / starting batches")).toBeVisible();
    await expect(tile(page, "Schedule & recording exceptions")).toBeVisible();
    await expect(tile(page, "Open escalations & extension requests")).toContainText("Escalations 1");
    for (const link of ["Batches, schedule & people", "Escalations & extensions", "Certificates & reports"]) {
      await expect(page.locator("#main").getByRole("link", { name: link })).toBeVisible();
    }
    await expect(page.getByText("Finance and Admissions remain in the CRM. This view shows academic data for the locked branch only.")).toBeVisible();
    await expect(page.getByText("NIT-VIJ")).toHaveCount(0);
  });
});

test.describe("Super Admin overview and exception queues", () => {
  test("overview: tiles, sync status, AI status", async ({ page }) => {
    await login(page, USERS.admin);
    await expect(page.getByRole("heading", { name: "Super Admin — all authorised branches" })).toBeVisible();
    await expect(tile(page, "Critical integration failures")).toBeVisible();
    await expect(tile(page, "Work awaiting named ownership/cover")).toContainText("Open exceptions with no named owner");
    await expect(tile(page, "Overdue payment verifications")).toContainText("Unavailable");
    await expect(tile(page, "Overdue payment verifications")).toContainText("Not Configured");
    await expect(tile(page, "Integrations operationally verified")).toContainText("0 /");
    await expect(tile(page, "Failed provisioning")).toBeVisible();
    await expect(tile(page, "Open exceptions (all queues)")).toBeVisible();
    await expect(page.getByRole("heading", { name: "CRM / LMS sync status" })).toBeVisible();
    await expect(page.getByRole("row", { name: /CRM → LMS events/ })).toContainText("1 failed event(s)");
    await expect(page.getByRole("row", { name: /LMS → CRM status outbox/ })).toContainText("Integration Unavailable");
    await expect(page.getByRole("heading", { name: "Provisioning exceptions" })).toBeVisible();
    await expect(page.getByText("monthly rupee ceiling not yet approved")).toBeVisible();
    await expect(page.locator("#main").getByRole("link", { name: "Exception queues" })).toBeVisible();
    await expect(page.locator("#main").getByRole("link", { name: "Integration readiness" })).toBeVisible();
  });

  test("Exception Queues — all branches: grouped by queue with a branch column", async ({ page }) => {
    await login(page, USERS.admin);
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Exception Queues" }).click();
    await expect(page.getByRole("heading", { name: "Exception Queues — all branches" })).toBeVisible();
    for (const queue of ["Curriculum / allocation", "Meet / recording", "CRM/LMS sync", "Access / recovery", "Support"]) {
      await expect(page.getByRole("heading", { name: new RegExp(`^${queue.replace("/", "\\/")} \\(`) })).toBeVisible();
    }
    const recording = page.getByRole("row", { name: /RX-0014/ });
    await expect(recording).toContainText("Vijayawada");
    await expect(page.getByRole("row", { name: /RX-0012/ })).toContainText("Guntur");
    await expect(page.getByRole("row", { name: /seed-/ })).toContainText("All branches");
    await expect(page.getByRole("row", { name: /EXT-033/ })).toContainText("Awaiting Approval");
  });

  test("the Founder reads the queues but cannot log steps", async ({ page }) => {
    await login(page, USERS.founder);
    await page.goto("/admin/exceptions");
    await expect(page.getByRole("heading", { name: "Exception Queues — all branches" })).toBeVisible();
    await expect(page.getByRole("row", { name: /RX-0012/ })).toContainText("Read only");
    await expect(page.getByRole("button", { name: /^Update / })).toHaveCount(0);
  });
});

test.describe("Founder overview", () => {
  test("tiles, decisions and links", async ({ page }) => {
    await login(page, USERS.founder);
    await expect(page.getByRole("heading", { name: "Founder / CEO overview" })).toBeVisible();
    for (const label of ["Verified collections against target", "New paid Admissions against target", "Overdue amount"]) {
      await expect(tile(page, label)).toContainText("Unavailable");
      await expect(tile(page, label)).toContainText("Not Configured");
    }
    await expect(tile(page, "Active enrolments in delivery")).toContainText("Guntur");
    await expect(tile(page, "Active enrolments in delivery")).toContainText("Vijayawada");
    await expect(tile(page, "Batches at delivery risk")).toContainText("Curriculum Mapping Pending");
    await expect(tile(page, "Certificates awaiting approval")).toBeVisible();

    const decisions = page.locator("section").filter({ has: page.getByRole("heading", { name: "Decisions needing you" }) });
    await expect(decisions).toContainText("Approve monthly AI rupee ceiling");
    await expect(decisions).toContainText("Configuration Pending");
    await expect(decisions).toContainText("Recording access exception after 2nd anniversary");
    await expect(decisions).toContainText("Sample Learner F.");
    await expect(decisions).toContainText("Awaiting Approval");
    await expect(page.locator("#main").getByRole("link", { name: "Super Admin view" })).toBeVisible();
    await expect(page.locator("#main").getByRole("link", { name: "Branch views" })).toBeVisible();
  });
});

test.describe("@mobile staff dashboards", () => {
  test("@mobile coordinator dashboard and queue fit the screen", async ({ page }) => {
    await login(page, USERS.coordGnt);
    await expect(page.getByRole("heading", { name: "Academic dashboard" })).toBeVisible();
    await expect(tile(page, "Enrolments awaiting batch allocation")).toContainText("5");
    await noHorizontalScroll(page);
    await page.goto("/academic/exceptions");
    await expect(page.getByRole("heading", { name: "Exception / Recovery queue" })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Update ENR-/ }).first()).toBeVisible();
    await noHorizontalScroll(page);
  });

  test("@mobile founder and branch views keep CRM figures Unavailable", async ({ page }) => {
    await login(page, USERS.founder);
    await expect(tile(page, "Overdue amount")).toContainText("Unavailable");
    await noHorizontalScroll(page);
    await page.goto("/admin/exceptions");
    await expect(page.getByRole("heading", { name: "Exception Queues — all branches" })).toBeVisible();
    await noHorizontalScroll(page);
  });
});
