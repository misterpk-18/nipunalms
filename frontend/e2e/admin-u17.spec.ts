import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * UX phase U17: the Super Admin's workspace. Home (Needs action, quick actions, Setup checklist), AI controls with a typed
 * confirmation for company-wide, CRM sync Needs attention, locked users and Unlock, the Calendar (month grid, list, add, edit and
 * cancel with the impact shown first), Issues (assign), Student accounts (Needs attention filter), and phone width. Data comes from
 * the staging seed; the flows add and remove their own entries.
 */

test.describe.configure({ mode: "serial" });

const RUN = Date.now().toString(36).slice(-5);
const noHorizontalScroll = async (page: Page) =>
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);

async function apiLogin(request: APIRequestContext, loginId: string, password = PASSWORD) {
  const response = await request.post("/api/v1/auth/login", { data: { login: loginId, password } });
  expect(response.ok()).toBeTruthy();
  return ((await response.json()) as { data: { token: string } }).data.token;
}
const auth = (token: string) => ({ Authorization: `Bearer ${token}` });
const istDay = (offsetDays: number) => new Date(Date.now() + offsetDays * 86_400_000).toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });

test("the navigation is grouped with counts and the home leads with Needs action", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const admin = await apiLogin(request, USERS.admin);
  const counts = (await (await request.get("/api/v1/me/nav-counts?workspace=admin", { headers: auth(admin) })).json()).data as Record<string, number>;
  expect(Object.keys(counts)).toEqual(expect.arrayContaining(["home", "users", "student_accounts", "issues", "calendar", "crm_sync", "setup"]));

  await login(page, USERS.admin);
  const nav = page.getByRole("navigation", { name: "Main" });
  for (const group of ["People", "Operations", "System"]) await expect(nav.getByText(group, { exact: true })).toBeVisible();
  for (const item of ["Staff accounts", "Student accounts", "Issues", "Academic calendar", "CRM sync", "Setup & health", "AI controls", "Audit log"])
    await expect(nav.getByRole("link", { name: item, exact: true })).toBeVisible();
  if (counts["student_accounts"]) await expect(nav.getByRole("link", { name: /Student accounts/ }).getByTestId("nav-badge")).toBeVisible();

  const needs = page.getByRole("region", { name: "Needs action" });
  await expect(needs).toBeVisible();
  const total = (await (await request.get("/api/v1/admin/needs-action", { headers: auth(admin) })).json()).data.total as number;
  if (total > 0) await expect(needs.getByRole("listitem").first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Quick actions" }).getByRole("link", { name: "Add staff user" })).toBeVisible();
  await page.getByRole("region", { name: "Quick actions" }).getByRole("link", { name: "Add staff user" }).click();
  await expect(page.getByRole("dialog", { name: "Add staff user" })).toBeVisible();
});

test("AI controls: ON or OFF per audience, company-wide needs a typed confirmation, and it comes back", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.admin);
  await page.goto("/admin/ai-controls");
  const student = page.locator('[data-ai="Student"]');
  await expect(student).toContainText("ON");

  await student.getByRole("button", { name: "Switch off" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Why are you switching it off?").fill(`E2E check ${RUN}`);
  const confirm = dialog.getByRole("button", { name: "Switch off", exact: true });
  await expect(confirm).toBeDisabled(); // company-wide: the typed confirmation is missing
  await dialog.getByLabel("Type SWITCH OFF to confirm").fill("SWITCH OFF");
  await confirm.click();
  await expect(student).toContainText("OFF");
  await expect(student).toContainText(`E2E check ${RUN}`);
  await expect(page.locator('[data-ai="Staff"]')).toContainText("ON");

  await student.getByRole("button", { name: "Switch back on" }).click();
  await page.getByRole("dialog").getByLabel("Checks that passed").fill("Fee answers retested");
  await page.getByRole("dialog").getByRole("button", { name: "Switch back on" }).click();
  await expect(student).toContainText("ON");
  await expect(page.getByRole("row", { name: new RegExp(`E2E check ${RUN}`) })).toContainText("Back on");
});

test("the Founder can reach the same AI controls from their own navigation", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.founder);
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "AI controls" }).click();
  await expect(page).toHaveURL(/\/founder\/ai-controls/);
  await expect(page.locator('[data-ai="All"]').getByRole("button", { name: "Switch off" })).toBeVisible();
});

test("a locked user is flagged on the home and unlocked with a reason", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const target = "trainer.g3@nipuna.test";
  for (let i = 0; i < 6; i++) await request.post("/api/v1/auth/login", { data: { login: target, password: `wrong-${i}` } });

  await login(page, USERS.admin);
  await expect(page.getByRole("region", { name: "Needs action" })).toContainText(/staff accounts? (is|are) locked/);
  await page.goto("/admin/users?locked=true");
  const row = page.getByRole("row", { name: /Trainer K\. Sample/ });
  await expect(row).toContainText("Locked");
  await row.getByRole("button", { name: /^Unlock/ }).click();
  await page.getByRole("dialog").getByLabel("Reason").fill("E2E: asked at the helpdesk");
  await page.getByRole("dialog").getByRole("button", { name: "Unlock", exact: true }).click();
  await expect(page.getByText("Trainer K. Sample can sign in again")).toBeVisible();
  await expect(page.getByRole("row", { name: /Trainer K\. Sample/ })).toHaveCount(0);
});

test("CRM sync: Retry on a failed update from the home goes to the same list", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const admin = await apiLogin(request, USERS.admin);
  const home = (await (await request.get("/api/v1/admin/needs-action", { headers: auth(admin) })).json()).data as { rows: { kind: string; retry: unknown }[] };
  await login(page, USERS.admin);
  const retryRows = home.rows.filter((r) => r.kind === "crm_event" && r.retry);
  if (retryRows.length) await expect(page.getByRole("region", { name: "Needs action" }).getByRole("button", { name: "Retry" }).first()).toBeVisible();
  await page.goto("/admin/crm-sync");
  await expect(page.getByRole("tab", { name: /Needs attention/ })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "All updates" }).click();
  await expect(page.getByRole("table", { name: "CRM updates" })).toBeVisible();
});

test("Calendar: a month grid and a list; add, edit and cancel show the impact first", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const admin = await apiLogin(request, USERS.admin);
  // a class still to come, so the impact has something to count
  const sessions = (await (await request.get("/api/v1/class-sessions?state=Scheduled&per_page=100", { headers: auth(admin) })).json()).data as {
    starts_at: string;
  }[];
  const future = sessions
    .map((s) => new Date(s.starts_at))
    .filter((d) => d.getTime() > Date.now() + 86_400_000)
    .sort((a, b) => a.getTime() - b.getTime())[0];
  test.skip(!future, "no class is scheduled to come in the staging data");
  const day = future!.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  const title = `E2E festival ${RUN}`;

  await login(page, USERS.admin);
  await page.goto(`/admin/calendar?month=${day.slice(0, 7)}`);
  await expect(page.getByRole("grid")).toBeVisible();
  await page.getByRole("button", { name: "Add holiday / closure" }).click();
  const add = page.getByRole("dialog", { name: "Add holiday or closure" });
  // the fields follow the kind, and To can't be before From
  await expect(add.getByLabel("Name of the holiday")).toBeVisible();
  await add.getByLabel("What is it?").selectOption("Branch Closure");
  await expect(add.getByLabel("Which branch is closed?")).toBeVisible();
  await expect(add.getByLabel("Name of the holiday")).toHaveCount(0);
  await add.getByLabel("What is it?").selectOption("Company Holiday");
  await add.getByLabel("Name of the holiday").fill(title);
  await add.getByLabel("From").fill(day);
  await add.getByLabel("To (last day)").fill(istDay(-1));
  await expect(add.getByText("The last day can't be before the first day.")).toBeVisible();
  await expect(add.getByRole("button", { name: "Add to calendar" })).toBeDisabled();
  await add.getByLabel("To (last day)").fill(day);
  await add.getByRole("button", { name: "Add to calendar" }).click();
  await expect(page.getByText(`${title} added to the calendar`)).toBeVisible();
  await expect(page.locator(`[data-closure]`).filter({ hasText: title }).first()).toBeVisible();

  // Edit: the impact comes first, nothing is saved until the second step
  await page.getByRole("button", { name: "List" }).click();
  const item = page.locator("li[data-closure]").filter({ hasText: title });
  await item.getByRole("button", { name: `Edit ${title}` }).click();
  const edit = page.getByRole("dialog");
  await edit.getByLabel("Title").fill(`${title} (moved)`);
  await edit.getByRole("button", { name: "Review the impact" }).click();
  await expect(edit.getByTestId("impact")).toContainText(/This affects \d+ class(es)?/);
  await edit.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText(`${title} (moved) updated`)).toBeVisible();

  // Cancel: the impact is read from the server before anything is cancelled
  const moved = page.locator("li[data-closure]").filter({ hasText: `${title} (moved)` });
  await moved.getByRole("button", { name: `Cancel ${title} (moved)` }).click();
  const cancel = page.getByRole("dialog");
  await expect(cancel.getByTestId("impact")).toContainText(/This affects \d+ class(es)?/);
  await expect(cancel.getByRole("button", { name: "Cancel this entry" })).toBeDisabled();
  await cancel.getByLabel("Why is it cancelled?").fill("E2E clean-up");
  await cancel.getByRole("button", { name: "Cancel this entry" }).click();
  await expect(page.getByText(`${title} (moved) cancelled`)).toBeVisible();
  await expect(page.locator("li[data-closure]").filter({ hasText: `${title} (moved)` })).toContainText("Cancelled");
  await expect(page.getByRole("button", { name: `Edit ${title} (moved)` })).toHaveCount(0);
});

test("Issues: the Super Admin assigns an issue and the owner changes", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const admin = await apiLogin(request, USERS.admin);
  const rows = (await (await request.get("/api/v1/issues?owner=none&per_page=100", { headers: auth(admin) })).json()).data as {
    id: string;
    title: string;
    can_assign: boolean;
  }[];
  const issue = rows.find((r) => r.can_assign);
  test.skip(!issue, "every issue already has an owner");
  await login(page, USERS.admin);
  await page.goto("/admin/issues?owner=none");
  const card = page.locator(`[data-issue="${issue!.id}"]`);
  await card.getByRole("button", { name: /^Assign / }).click();
  const dialog = page.getByRole("dialog", { name: "Assign this issue" });
  await dialog.getByLabel("Who should fix it?").selectOption({ label: "Super Admin (Super Admin)" });
  await dialog.getByLabel("What do you expect? (optional)").fill(`E2E ${RUN}`);
  await dialog.getByRole("button", { name: "Assign" }).click();
  await expect(page.getByText("Assigned to Super Admin")).toBeVisible();
  await page.goto("/admin/issues?owner=me");
  await expect(page.locator(`[data-issue="${issue!.id}"]`)).toContainText("Owner: Super Admin");
});

test("Student accounts: the Needs attention filter and the page's suggested next step", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const admin = await apiLogin(request, USERS.admin);
  const flagged = (await (await request.get("/api/v1/admin/students?needs_attention=true&per_page=25", { headers: auth(admin) })).json()) as {
    data: { student_id: number; full_name: string; suggested_step: { label: string } }[];
    meta: { total: number };
  };
  await login(page, USERS.admin);
  await page.goto("/admin/students?attention=true");
  await expect(page.getByRole("button", { name: "Needs attention", exact: true })).toHaveAttribute("aria-pressed", "true");
  if (flagged.meta.total === 0) {
    await expect(page.getByText("No student account needs attention right now.")).toBeVisible();
    return;
  }
  const first = flagged.data[0]!;
  await expect(page.getByRole("row", { name: new RegExp(first.full_name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) })).toContainText(first.suggested_step.label);
  await page.getByRole("link", { name: `Open ${first.full_name}` }).click();
  await expect(page).toHaveURL(new RegExp(`/admin/students/${first.student_id}$`));
  await expect(page.getByRole("region", { name: "Suggested next step" })).toContainText(first.suggested_step.label);
  await expect(page.getByRole("link", { name: "Student accounts" }).first()).toBeVisible();
});

test("the audit log, setup and calendar fit the phone @mobile", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile", "phone layout only");
  await login(page, USERS.admin);
  for (const path of [
    "/admin",
    "/admin/setup",
    "/admin/ai-controls",
    "/admin/calendar",
    "/admin/calendar?view=list",
    "/admin/issues",
    "/admin/audit",
    "/admin/students/3",
  ]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("status", { name: "Loading" })).toHaveCount(0);
    await noHorizontalScroll(page);
  }
});

test("dark mode keeps the new screens readable", async ({ browser }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const context = await browser.newContext({ colorScheme: "dark", baseURL: info.project.use.baseURL as string });
  const page = await context.newPage();
  await login(page, USERS.admin);
  for (const path of ["/admin", "/admin/ai-controls", "/admin/calendar"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).not.toBe("rgb(255, 255, 255)");
  }
  await context.close();
});
