import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * UX phase U16: the Founder's workspace. The home leads with "Needs you" (curriculum approvals, certificate decisions, access
 * extensions with the Branch Manager's recommendation, the AI budget, Branch Managers' own requests); each item opens in a side
 * panel with a pinned Approve / Reject (or Return) bar; curriculum can be approved and activated in one step. Data comes from the
 * staging seed; the flows add a draft that is returned or retired again and one rejected certificate request per run.
 */

test.describe.configure({ mode: "serial" });

const RUN = Date.now().toString(36).slice(-5);
const COURSE = "NIT-CRS-026";
const noHorizontalScroll = async (page: Page) =>
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);

async function apiLogin(request: APIRequestContext, loginId: string) {
  const response = await request.post("/api/v1/auth/login", { data: { login: loginId, password: PASSWORD } });
  expect(response.ok()).toBeTruthy();
  return ((await response.json()) as { data: { token: string } }).data.token;
}
const auth = (token: string) => ({ Authorization: `Bearer ${token}` });

type Version = { curriculum_version_id: number; version_label: string; status: string; course: { course_code: string } };

/** The Branch Manager's complete draft of the course, submitted for review; an earlier failed run's draft is discarded first. */
async function submitDraft(request: APIRequestContext) {
  const bm = await apiLogin(request, USERS.bmGnt);
  const founder = await apiLogin(request, USERS.founder);
  const inCourse = async (status: string) =>
    ((await (await request.get(`/api/v1/curriculum-versions?status=${status}`, { headers: auth(bm) })).json()).data as Version[]).filter(
      (v) => v.course.course_code === COURSE,
    );
  // an earlier failed run may have left a version under review, approved or in draft: clear it so a new draft can start
  for (const old of await inCourse("Under Review"))
    await request.post(`/api/v1/curriculum-versions/${old.curriculum_version_id}/return`, { headers: auth(founder), data: { reason: "e2e clean-up" } });
  for (const old of await inCourse("Approved"))
    await request.post(`/api/v1/curriculum-versions/${old.curriculum_version_id}/retire`, { headers: auth(founder), data: { reason: "e2e clean-up" } });
  for (const old of await inCourse("Draft")) await request.delete(`/api/v1/curriculum-versions/${old.curriculum_version_id}`, { headers: auth(bm) });
  const courses = (await (await request.get("/api/v1/reference/courses", { headers: auth(bm) })).json()).data as { course_id: number; course_code: string }[];
  const created = await request.post("/api/v1/curriculum-versions", {
    headers: auth(bm),
    data: { course_id: courses.find((c) => c.course_code === COURSE)!.course_id },
  });
  expect(created.status()).toBe(201);
  const draft = (await created.json()).data as Version;
  const id = draft.curriculum_version_id;
  expect((await request.post(`/api/v1/curriculum-versions/${id}/hours-verification`, { headers: auth(bm), data: {} })).ok()).toBeTruthy();
  const submitted = await request.post(`/api/v1/curriculum-versions/${id}/submit`, { headers: auth(bm), data: {} });
  expect(submitted.ok(), JSON.stringify(await submitted.json())).toBeTruthy();
  return { id, label: draft.version_label, bm };
}

const tomorrow = () => new Date(Date.now() + 2 * 86_400_000).toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });

test("the home leads with Needs you, the navigation is grouped with a count, and CRM tiles wait for the CRM", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const founder = await apiLogin(request, USERS.founder);
  const inbox = (await (await request.get("/api/v1/founder/inbox", { headers: auth(founder) })).json()).data as { total: number; crm_connected: boolean };

  await login(page, USERS.founder);
  await expect(page.getByRole("heading", { level: 1, name: "Founder / CEO home" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Needs you" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Main" });
  for (const label of ["Home", "Curriculum approvals", "Certificate decisions", "Access extensions"])
    await expect(nav.getByRole("link", { name: label, exact: true })).toBeVisible();
  await expect(nav.getByText("Approvals", { exact: true })).toBeVisible();
  for (const gone of ["Founder Dashboard", "Curriculum Approvals", "Certificate Decisions"])
    await expect(nav.getByRole("link", { name: gone, exact: true })).toHaveCount(0);
  if (inbox.total > 0) await expect(nav.getByTestId("nav-badge").first()).toHaveText(String(inbox.total));

  // the CRM tiles follow the CRM's own status
  const tiles = page.getByRole("group", { name: "Overdue amount" });
  if (inbox.crm_connected) await expect(tiles).toHaveCount(1);
  else {
    await expect(tiles).toHaveCount(0);
    await expect(page.getByText("appear here once the CRM has sent them")).toBeVisible();
  }
  await expect(page.getByRole("group", { name: "Active enrolments in delivery" })).toBeVisible();

  // nothing on the Founder's pages sends them to the Branch Manager's screens
  for (const path of ["/founder", "/founder/curriculum", "/founder/certificates", "/founder/access"]) {
    await page.goto(path);
    await expect(page.locator("#main").locator('a[href*="/branch/"]')).toHaveCount(0);
  }
});

test("a curriculum opens in a side panel with what changes and who is affected; Return needs a reason", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const { id, label, bm } = await submitDraft(request);
  await login(page, USERS.founder);
  await page.goto("/founder");
  const row = page.getByRole("listitem").filter({ hasText: `Approve curriculum ${label} for` });
  await expect(row).toBeVisible();
  await row.getByRole("link", { name: "Review" }).click();

  const panel = page.getByRole("dialog");
  await expect(panel.getByRole("heading", { name: `Approve ${label}` })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "What changes" })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "Who is affected" })).toBeVisible();
  await expect(panel.getByText(/Compared with CV/)).toBeVisible();
  const bar = panel.getByTestId("decision-bar");
  await expect(bar.getByRole("button", { name: "Approve" })).toBeVisible();
  await expect(bar.getByRole("button", { name: "Return" })).toBeVisible();
  expect(page.url()).toContain("item=curriculum-");

  await bar.getByRole("button", { name: "Return" }).click();
  const ask = page.getByRole("dialog").last();
  const send = ask.getByRole("button", { name: "Return it" });
  await expect(send).toBeDisabled();
  await ask.getByLabel(/What needs to change/).fill("no");
  await expect(send).toBeDisabled();
  await ask.getByLabel(/What needs to change/).fill(`Topic notes need work ${RUN}`);
  await send.click();
  await expect(page.getByText(`${label} returned`)).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: `Approve curriculum ${label} for` })).toHaveCount(0);

  const status = ((await (await request.get(`/api/v1/curriculum-versions/${id}`, { headers: auth(bm) })).json()).data as Version).status;
  expect(status).toBe("Draft");
  await request.delete(`/api/v1/curriculum-versions/${id}`, { headers: auth(bm) });
});

test("Approve & activate: the choice is explicit, a chosen day schedules it", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const { id, label } = await submitDraft(request);
  const founder = await apiLogin(request, USERS.founder);
  try {
    await login(page, USERS.founder);
    await page.goto("/founder/curriculum");
    await page
      .getByRole("listitem")
      .filter({ hasText: `Approve curriculum ${label} for` })
      .getByRole("link", { name: "Review" })
      .click();
    const panel = page.getByRole("dialog");
    await panel.getByTestId("decision-bar").getByRole("button", { name: "Approve" }).click();

    const choose = page.getByRole("dialog").last();
    await expect(choose.getByRole("heading", { name: `Approve ${label}?` })).toBeVisible();
    await expect(choose.getByRole("radio", { name: "Activate it now" })).toBeChecked();
    await expect(choose.getByRole("button", { name: "Approve & activate" })).toBeEnabled();
    await choose.getByRole("radio", { name: "Only approve it. I will activate it later" }).check();
    await expect(choose.getByRole("button", { name: "Approve only" })).toBeVisible();
    await choose.getByRole("radio", { name: "Activate it on a day I choose" }).check();
    const schedule = choose.getByRole("button", { name: "Approve and schedule" });
    await expect(schedule).toBeDisabled();
    await choose.getByLabel("Activate on").fill(tomorrow());
    await schedule.click();

    await expect(page.getByText(`${label} approved`)).toBeVisible();
    await expect(page.getByText(/It will be activated on/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Approved, activating on a chosen day" })).toBeVisible();
    await expect(page.getByRole("listitem").filter({ hasText: `${label} for` })).toContainText("Activates on");
    await expect(page.getByRole("listitem").filter({ hasText: `Approve curriculum ${label} for` })).toHaveCount(0);
  } finally {
    await request.post(`/api/v1/curriculum-versions/${id}/retire`, { headers: auth(founder), data: { reason: "e2e clean-up" } }); // so the scheduled day never activates it
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

test("@mobile the Founder's screens and the panel fit a phone", async ({ page, request }) => {
  const { id, label, bm } = await submitDraft(request);
  try {
    await login(page, USERS.founder);
    await expect(page.getByRole("heading", { level: 1, name: "Founder / CEO home" })).toBeVisible();
    await noHorizontalScroll(page);
    await page.goto("/founder/access");
    await noHorizontalScroll(page);
    await page.goto("/founder/certificates");
    await noHorizontalScroll(page);
    await page.goto("/founder/curriculum");
    await page
      .getByRole("listitem")
      .filter({ hasText: `Approve curriculum ${label} for` })
      .getByRole("link", { name: "Review" })
      .click();
    const panel = page.getByRole("dialog");
    await expect(panel.getByRole("heading", { name: `Approve ${label}` })).toBeVisible();
    await expect(panel.getByTestId("decision-bar").getByRole("button", { name: "Approve" })).toBeInViewport();
    await expect(panel.getByTestId("decision-bar").getByRole("button", { name: "Return" })).toBeInViewport();
    await noHorizontalScroll(page);
  } finally {
    const founder = await apiLogin(request, USERS.founder);
    await request.post(`/api/v1/curriculum-versions/${id}/return`, { headers: auth(founder), data: { reason: "e2e clean-up" } });
    await request.delete(`/api/v1/curriculum-versions/${id}`, { headers: auth(bm) });
  }
});

test("dark mode keeps the panel and its bar readable", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const { id, label, bm } = await submitDraft(request);
  try {
    await page.emulateMedia({ colorScheme: "dark" });
    await login(page, USERS.founder);
    await page.goto("/founder");
    await page.screenshot({ path: "test-results/founder-home-dark.png", fullPage: true });
    await page
      .getByRole("listitem")
      .filter({ hasText: `Approve curriculum ${label} for` })
      .getByRole("link", { name: "Review" })
      .click();
    await expect(page.getByRole("dialog").getByTestId("decision-bar").getByRole("button", { name: "Approve" })).toBeVisible();
    await page.waitForTimeout(700); // the panel slides in
    await page.screenshot({ path: "test-results/founder-panel-dark.png" });
  } finally {
    const founder = await apiLogin(request, USERS.founder);
    await request.post(`/api/v1/curriculum-versions/${id}/return`, { headers: auth(founder), data: { reason: "e2e clean-up" } });
    await request.delete(`/api/v1/curriculum-versions/${id}`, { headers: auth(bm) });
  }
});
