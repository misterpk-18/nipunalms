import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * UX phase U16: the Founder's workspace. The home leads with "Needs you" (certificate decisions, access
 * extensions with the Branch Manager's recommendation, the AI budget, Branch Managers' own requests); each item opens in a side
 * panel with a pinned Approve / Reject bar. Courses have no approval step (role separation).
 * Data comes from the staging seed; the flows add one rejected certificate request per run.
 */

test.describe.configure({ mode: "serial" });

const RUN = Date.now().toString(36).slice(-5);
const noHorizontalScroll = async (page: Page) =>
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);

async function apiLogin(request: APIRequestContext, loginId: string) {
  const response = await request.post("/api/v1/auth/login", { data: { login: loginId, password: PASSWORD } });
  expect(response.ok()).toBeTruthy();
  return ((await response.json()) as { data: { token: string } }).data.token;
}
const auth = (token: string) => ({ Authorization: `Bearer ${token}` });

test("the home leads with Needs you, the navigation is grouped with a count, and CRM tiles wait for the CRM", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const founder = await apiLogin(request, USERS.founder);
  const inbox = (await (await request.get("/api/v1/founder/inbox", { headers: auth(founder) })).json()).data as { total: number; crm_connected: boolean };

  await login(page, USERS.founder);
  await expect(page.getByRole("heading", { level: 1, name: "Founder / CEO home" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Needs you" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Main" });
  for (const label of ["Home", "Approvals", "Courses", "Reports"]) await expect(nav.getByRole("link", { name: label, exact: true })).toBeVisible();
  for (const gone of ["Founder Dashboard", "Curriculum approvals", "Certificate decisions", "Curriculum"])
    await expect(nav.getByRole("link", { name: gone, exact: true })).toHaveCount(0);
  if (inbox.total > 0) await expect(nav.getByRole("link", { name: "Approvals", exact: true }).getByTestId("nav-badge")).toHaveText(String(inbox.total));

  // the CRM tiles follow the CRM's own status
  const tiles = page.getByRole("group", { name: "Overdue amount" });
  if (inbox.crm_connected) await expect(tiles).toHaveCount(1);
  else {
    await expect(tiles).toHaveCount(0);
    await expect(page.getByText("appear here once the CRM has sent them")).toBeVisible();
  }
  await expect(page.getByRole("group", { name: "Active enrolments in delivery" })).toBeVisible();

  // nothing on the Founder's pages sends them to the Branch Manager's screens
  for (const path of ["/founder", "/founder/approvals", "/founder/certificates", "/founder/access"]) {
    await page.goto(path);
    await expect(page.locator("#main").locator('a[href*="/branch/"]')).toHaveCount(0);
  }
});

test("a certificate request: Approve and Reject have no default, each says what it does, Reject needs a reason", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const bm = await apiLogin(request, USERS.bmGnt);
  const certificates = (await (await request.get("/api/v1/certificates?status=Issued&per_page=50", { headers: auth(bm) })).json()).data as {
    certificate_id: number;
    certificate_number: string;
    pending_request: unknown;
  }[];
  const target = certificates.find((c) => !c.pending_request);
  test.skip(!target, "every issued certificate already has a request waiting");
  const asked = await request.post(`/api/v1/certificates/${target!.certificate_id}/change-requests`, {
    headers: auth(bm),
    data: { kind: "Revocation", reason: `Entered against the wrong enrolment ${RUN}`, evidence: "Enrolment record checked" },
  });
  expect(asked.status(), JSON.stringify(await asked.json())).toBe(201);

  await login(page, USERS.founder);
  await page.goto("/founder/certificates");
  const row = page.getByRole("listitem").filter({ hasText: `Revocation of certificate ${target!.certificate_number}` });
  await expect(row).toContainText("A Branch Manager's own request");
  await row.getByRole("link", { name: "Review" }).click();

  const panel = page.getByRole("dialog");
  await expect(panel.getByRole("heading", { name: `Revocation of certificate ${target!.certificate_number}` })).toBeVisible();
  await expect(panel.getByText(`Entered against the wrong enrolment ${RUN}`)).toBeVisible();
  const bar = panel.getByTestId("decision-bar");
  await bar.getByRole("button", { name: "Approve" }).click();
  const confirm = page.getByRole("alertdialog");
  await expect(confirm).toContainText("The certificate stops being valid");
  await confirm.getByRole("button", { name: "Cancel" }).click();

  await bar.getByRole("button", { name: "Reject" }).click();
  const ask = page.getByRole("dialog").last();
  await expect(ask).toContainText("The certificate stays valid");
  const reject = ask.getByRole("button", { name: "Reject" });
  await expect(reject).toBeDisabled();
  await ask.getByLabel(/Why are you saying no/).fill(`The evidence is not enough ${RUN}`);
  await reject.click();
  await expect(page.getByText("Revocation rejected")).toBeVisible();
  await expect(row).toHaveCount(0);
});

test("an access extension shows the Branch Manager's recommendation; approving needs an end date", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.founder);
  await page.goto("/founder/access");
  await expect(page.getByRole("heading", { level: 1, name: "Access extensions" })).toBeVisible();
  const rows = page.getByRole("list", { name: "Access extension requests" }).getByRole("listitem");
  await expect(rows.first().or(page.getByText("No request is waiting."))).toBeVisible();
  test.skip((await rows.count()) === 0, "no request beyond two years waits");
  await rows.first().getByRole("button", { name: "Review" }).click();

  const panel = page.getByRole("dialog");
  await expect(panel.getByRole("heading", { name: /Access beyond two years for/ })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "The Branch Manager's recommendation" })).toBeVisible();
  const bar = panel.getByTestId("decision-bar");
  await bar.getByRole("button", { name: "Approve" }).click();
  const extend = page.getByRole("dialog").last();
  await expect(extend.getByLabel("New end date")).toBeVisible();
  const go = extend.getByRole("button", { name: "Extend access" });
  if ((await extend.getByLabel("New end date").inputValue()) === "") await expect(go).toBeDisabled();
  await extend.getByRole("button", { name: "Cancel" }).click();
  await bar.getByRole("button", { name: "Reject" }).click();
  await expect(page.getByRole("dialog").last().getByRole("button", { name: "Reject" })).toBeDisabled();
});

test("the AI budget is set from the inbox and asks before it saves", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const founder = await apiLogin(request, USERS.founder);
  const inbox = (await (await request.get("/api/v1/founder/inbox", { headers: auth(founder) })).json()).data as { items: { kind: string }[] };
  test.skip(!inbox.items.some((i) => i.kind === "ai_budget"), "the AI budget was already approved");
  await login(page, USERS.founder);
  await page.getByRole("listitem").filter({ hasText: "Approve the monthly AI budget" }).getByRole("link", { name: "Set budget" }).click();
  const panel = page.getByRole("dialog");
  const approve = panel.getByTestId("decision-bar").getByRole("button", { name: "Approve budget" });
  await expect(approve).toBeDisabled();
  await panel.getByLabel(/Monthly budget/).fill("25000");
  await approve.click();
  await expect(page.getByRole("alertdialog")).toContainText("₹25,000 a month");
  await page.getByRole("alertdialog").getByRole("button", { name: "Cancel" }).click(); // the budget is left for the owner to set
});

test("the Founder opens Reports for all branches with no permission error", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const failures: string[] = [];
  page.on("response", (r) => {
    if (r.url().includes("/api/v1/") && r.status() >= 400) failures.push(`${r.status()} ${r.url()}`);
  });
  await login(page, USERS.founder);
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Reports", exact: true }).click();
  await expect(page).toHaveURL(/\/founder\/reports/);
  await expect(page.getByRole("heading", { level: 1, name: /Reports/ })).toBeVisible();
  await expect(page.getByText("Loading…")).toHaveCount(0);
  await expect(page.getByText(/don't have access|not allowed|Forbidden/i)).toHaveCount(0);
  expect(failures).toEqual([]);
});

test("@mobile the Founder's screens fit a phone", async ({ page }) => {
  await login(page, USERS.founder);
  await expect(page.getByRole("heading", { level: 1, name: "Founder / CEO home" })).toBeVisible();
  await noHorizontalScroll(page);
  for (const path of ["/founder/approvals", "/founder/access", "/founder/certificates", "/founder/reports", "/founder/courses"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await noHorizontalScroll(page);
  }
});

test("dark mode keeps the Founder home readable", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await page.emulateMedia({ colorScheme: "dark" });
  await login(page, USERS.founder);
  await page.goto("/founder");
  await expect(page.getByRole("heading", { level: 1, name: "Founder / CEO home" })).toBeVisible();
  await page.screenshot({ path: "test-results/founder-home-dark.png", fullPage: true });
});
