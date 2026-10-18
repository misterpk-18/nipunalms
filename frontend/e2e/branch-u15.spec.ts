import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * UX phase U15: the Branch Manager's Curriculum, Content & questions, Marks & results, Attendance & progress, Completion &
 * certificates, Issues, Recordings, Student support (with access extensions) and Reports, plus the finished navigation and the old
 * routes. Data comes from the staging seed; the flows add a few rows (a draft that is discarded again, one content item, one note,
 * one recommendation) under a suffix that is new on every run.
 */

test.describe.configure({ mode: "serial" });

const RUN = Date.now().toString(36).slice(-5);
const noHorizontalScroll = async (page: Page) =>
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);

async function apiLogin(request: APIRequestContext, loginId: string) {
  const response = await request.post("/api/v1/auth/login", { data: { login: loginId, password: PASSWORD } });
  expect(response.ok()).toBeTruthy();
  const { data } = await response.json();
  return { token: data.token as string };
}
const auth = (token: string) => ({ Authorization: `Bearer ${token}` });

test("the navigation is the decided list and the old screens still open", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  const nav = page.getByRole("navigation").first();
  for (const label of [
    "My work",
    "Class day",
    "Batches",
    "Waiting for a batch",
    "Schedule & calendar",
    "Attendance & progress",
    "Courses",
    "Content review",
    "Question approvals",
    "Marks & results",
    "Recordings",
    "Completion & certificates",
    "Certificate requests",
    "Student support",
    "Access extensions",
    "Issues",
    "Reports",
    "Payment instructions",
  ])
    await expect(nav.getByRole("link", { name: label })).toBeVisible();
  for (const gone of ["Content Review", "Reviews", "Completion Review", "Certificate Eligibility", "Exceptions", "Recording Exceptions", "Escalations & Extensions", "Academic Reports"])
    await expect(nav.getByRole("link", { name: gone })).toHaveCount(0);

  const redirects: [string, RegExp][] = [
    ["/branch/content-review", /\/branch\/content$/],
    ["/branch/assessments", /\/branch\/results$/],
    ["/branch/exceptions", /\/branch\/issues$/],
    ["/branch/recording-exceptions", /\/branch\/recordings$/],
    ["/branch/certificates", /\/branch\/completion\?stage=completed/],
    ["/branch/requests", /\/branch\/support\?tab=extensions/],
    ["/branch/academic-reports", /\/branch\/reports$/],
    ["/academic/progress", /\/branch\/progress$/],
  ];
  for (const [from, to] of redirects) {
    await page.goto(from);
    await expect(page).toHaveURL(to);
  }
});

test("Issues is one paged inbox: filter, add a note, go fix it", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/issues");
  await expect(page.getByRole("heading", { level: 1, name: "Issues" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^All\s*\d+/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Recordings\s*\d+/ })).toBeVisible();
  await expect(page.getByText(/Page 1 of \d+/)).toBeVisible();

  await page.getByRole("button", { name: /^Recordings\s*\d+/ }).click();
  await expect(page).toHaveURL(/type=recordings/);
  const first = page.getByRole("listitem").filter({ hasText: "Recording problem" }).first();
  await expect(first).toBeVisible();
  await first.getByRole("button", { name: "Add note" }).click();
  await page.getByRole("dialog").getByLabel("Note").fill(`Checking the Drive file ${RUN}`);
  await page.getByRole("dialog").getByRole("button", { name: "Add note" }).click();
  await expect(page.getByText("Note added. You now own this issue.")).toBeVisible();

  await page.getByLabel("Owner").selectOption({ label: "Mine" });
  await expect(page).toHaveURL(/owner=me/);
  await expect(page.getByText(`Checking the Drive file ${RUN}`).first()).toBeVisible();
  await page.getByRole("listitem").filter({ hasText: "Recording problem" }).first().getByRole("button", { name: "Go fix it" }).click();
  await expect(page).toHaveURL(/\/branch\/recordings\?.*exception=/);
  await expect(page.getByRole("heading", { level: 1, name: "Recordings" })).toBeVisible();
});

test("Recordings: pick the class, report a problem with a reason, release with a confirm", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/recordings");
  await expect(page.getByRole("heading", { level: 1, name: "Recordings" })).toBeVisible();
  await expect(page.getByText(/Open problems \(\d+\)/)).toBeVisible();
  await expect(page.getByLabel("Date")).toBeVisible();
  await expect(page.getByLabel("Batch")).toBeVisible();
  // an open problem jumps to its class
  await page.getByRole("button", { name: "Open", exact: true }).first().click();
  await expect(page.getByRole("button", { name: "Report a problem" }).first()).toBeVisible();
  await page.getByRole("button", { name: "Report a problem" }).first().click();
  const dialog = page.getByRole("dialog");
  for (const reason of ["It is still being prepared", "Only part of the class was captured", "No recording exists", "Hold it back for review"])
    await expect(dialog.getByRole("radio", { name: reason })).not.toBeChecked();
  await expect(dialog.getByRole("button", { name: "Report problem" })).toBeDisabled();
  await dialog.getByRole("radio", { name: "Hold it back for review" }).check();
  await expect(dialog.getByRole("button", { name: "Report problem" })).toBeDisabled(); // a note is needed
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await page.getByRole("button", { name: "Release", exact: true }).first().click();
  await expect(page.getByRole("alertdialog").or(page.getByRole("dialog")).getByText(/will be told and can watch it now/)).toBeVisible();
  await page.keyboard.press("Escape");
});

test("Content & questions: one Review claims the item, the decision has a preview and no default", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const trainer = await apiLogin(request, USERS.trainerG1);
  const options = await (await request.get("/api/v1/content-items/options", { headers: auth(trainer.token) })).json();
  const option = options.data[0];
  const batch = { batch_id: option.batch.batch_id, topic_id: option.versions[0].modules[0].topics[0].topic_id };
  const created = await request.post("/api/v1/content-items", {
    headers: auth(trainer.token),
    multipart: {
      title: `E2E reading list ${RUN}`,
      content_type: "Link",
      url: "https://example.com/reading",
      batch_id: String(batch.batch_id),
      topic_id: String(batch.topic_id),
    },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const item = (await created.json()).data;
  expect((await request.post(`/api/v1/content-items/${item.content_item_id}/submit`, { headers: auth(trainer.token) })).ok()).toBeTruthy();

  await login(page, USERS.bmGnt);
  await page.goto("/branch/content");
  await expect(page.getByRole("heading", { level: 1, name: "Content review" })).toBeVisible();
  for (const tab of ["To review", "Ready to release", "Changes requested", "Released"])
    await expect(page.getByRole("tab", { name: new RegExp(`^${tab}`) })).toBeVisible();
  const row = page.getByRole("row", { name: new RegExp(`E2E reading list ${RUN}`) });
  await row.getByRole("button", { name: "Review", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText(`E2E reading list ${RUN}`).first()).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Approve & release" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Approve and release later" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Request changes" })).toBeVisible();
  await dialog.getByRole("button", { name: "Request changes" }).click();
  await expect(page.getByRole("dialog").last().getByRole("button", { name: "Send request" })).toBeDisabled(); // a comment is required
  await page.getByRole("dialog").last().getByRole("button", { name: "Cancel" }).click();
  await dialog.getByRole("button", { name: "Approve and release later" }).click();
  await page.getByRole("tab", { name: /^Ready to release/ }).click();
  const ready = page.getByRole("row", { name: new RegExp(`E2E reading list ${RUN}`) });
  await expect(ready).toBeVisible();
  await ready.getByRole("button", { name: "Release", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Release", exact: true }).click();
  await page.getByRole("tab", { name: /^Released/ }).click();
  await expect(page.getByRole("row", { name: new RegExp(`E2E reading list ${RUN}`) })).toBeVisible();
  await page.goto("/branch/questions");
  await expect(page.getByRole("heading", { level: 1, name: "Question approvals" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve", exact: true }).first()).toBeVisible(); // question approval has its own page
});

test("Marks & results: gaps name their owner and publishing asks first with counts", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/results");
  await expect(page.getByRole("heading", { level: 1, name: "Marks & results" })).toBeVisible();
  await expect(page.getByText("Needs your review").first()).toBeVisible();
  await page.getByRole("button", { name: "Review marks" }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Publish results" }).click();
  const confirm = page.getByRole("alertdialog");
  await expect(confirm.getByText(/^Publish \d+ results?\?/)).toBeVisible();
  await expect(confirm.getByText(/still unreviewed/)).toBeVisible();
  await expect(confirm.getByText(/Students will see their marks now/)).toBeVisible();
  await confirm.getByRole("button", { name: "Cancel" }).click();
});

test("Attendance & progress: students at risk first, counts on the tabs, confirms with the consequence", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/attendance");
  await expect(page.getByRole("heading", { level: 1, name: "Attendance & progress" })).toBeVisible();
  const tabs = page.getByRole("tablist");
  await expect(tabs.getByRole("tab", { name: /^Students/ })).toBeVisible();
  await expect(tabs.getByRole("tab", { name: /^Recovery requests/ })).toBeVisible();
  await expect(tabs.getByRole("tab", { name: /^Corrections/ })).toBeVisible();
  await page.getByRole("button", { name: /Show all students/ }).click();
  await expect(page).toHaveURL(/risk=(0|%220%22)/);
  await expect(page.getByRole("button", { name: /Show only students at risk/ })).toBeVisible();
  await page.getByRole("tab", { name: /^Recovery requests/ }).click();
  await expect(page).toHaveURL(/tab=recoveries/);
  const approve = page.getByRole("button", { name: "Approve", exact: true }).first();
  if (await approve.isVisible().catch(() => false)) {
    await approve.click();
    await expect(page.getByRole("dialog").getByText(/will be told they can make up/)).toBeVisible();
    await page.keyboard.press("Escape");
  }
  await page.getByRole("tab", { name: /^Corrections/ }).click();
  await expect(page).toHaveURL(/tab=corrections/);
});

test("Student support opens on Needs action and access extensions beyond the limit take a recommendation", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/support");
  await expect(page.getByRole("heading", { level: 1, name: "Student support" })).toBeVisible();
  for (const tab of ["Needs action", "Waiting for the student", "Done", "All"]) await expect(page.getByRole("tab", { name: new RegExp(`^${tab}`) })).toBeVisible();
  await expect(page.getByRole("tab", { name: /^Needs action/ })).toHaveAttribute("aria-selected", "true");

  await page.goto("/branch/support?tab=extensions"); // the old tab address opens the Access extensions page
  await expect(page).toHaveURL(/\/branch\/extensions/);
  await expect(page.getByText(/This is beyond what you can approve/).first()).toBeVisible();
  const trigger = page.getByRole("button", { name: /^(Add|Change) recommendation$/ }).first();
  const first = (await trigger.textContent())?.startsWith("Add");
  await trigger.click();
  const dialog = page.getByRole("dialog");
  if (first) {
    // no default choice (a run that already saved one opens the dialog with it filled in)
    await expect(dialog.getByRole("radio", { name: "I recommend approving" })).not.toBeChecked();
    await expect(dialog.getByRole("radio", { name: "I recommend rejecting" })).not.toBeChecked();
  }
  await dialog.getByRole("radio", { name: "I recommend rejecting" }).check();
  await dialog.getByLabel(/Note|Why/).first().fill(`The course finished long ago ${RUN}`);
  await dialog.getByRole("button", { name: /Save recommendation|Send to the Founder|Save/ }).last().click();
  await expect(page.getByText("With the Founder").first()).toBeVisible();
});

test("Completion & certificates: the pipeline with counts, evidence and the rare actions under More", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/completion");
  await expect(page.getByRole("heading", { level: 1, name: "Completion & certificates" })).toBeVisible();
  for (const tab of ["Ready to decide", "Completed", "Waiting for fee", "Ready to issue", "Issued"]) await expect(page.getByRole("tab", { name: new RegExp(`^${tab}`) })).toBeVisible();
  await page.getByRole("tab", { name: /^Completed/ }).click();
  await expect(page).toHaveURL(/stage=completed/);
  await page.getByRole("tab", { name: /^Issued/ }).click();
  await expect(page).toHaveURL(/stage=issued/);
  await expect(page.getByText(/NIT-CERT-\d{4}-\d{6}/).first()).toBeVisible();
  await page.getByRole("button", { name: "More" }).first().click();
  await expect(page.getByRole("menuitem", { name: /Request (revocation|reinstatement|a correction)/ }).first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Issue certificate" })).toHaveCount(0); // issuing is never offered on an issued one
});

test("Curriculum: a draft is named for you, shows its checklist with incomplete topics marked, and discarding asks first", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  const bm = await apiLogin(request, USERS.bmGnt);
  const drafts = async () =>
    ((await (await request.get("/api/v1/curriculum-versions?status=Draft", { headers: auth(bm.token) })).json()).data as { curriculum_version_id: number; course: { course_code: string } }[]).filter(
      (v) => v.course.course_code === "NIT-CRS-026",
    );
  for (const old of await drafts()) await request.delete(`/api/v1/curriculum-versions/${old.curriculum_version_id}`, { headers: auth(bm.token) }); // an earlier failed run
  await login(page, USERS.bmGnt);
  await page.goto("/branch/curriculum");
  const row = page.getByRole("row", { name: /Professional Video Editing/ });
  await row.getByRole("button", { name: "Manage versions" }).click();
  await page.getByRole("button", { name: "New draft" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText(/Start from the current Active version \(CV 1\.2\)/)).toBeVisible();
  await expect(dialog.getByLabel("Start empty instead")).not.toBeChecked();
  await dialog.getByRole("button", { name: "Create draft" }).click();
  await expect(page.getByText("CV 1.3").first()).toBeVisible();
  // describe nothing for one new topic, so the checklist has something to mark
  await expect.poll(async () => (await drafts()).length).toBe(1);
  const [draft] = await drafts();
  const module = await (await request.post(`/api/v1/curriculum-versions/${draft!.curriculum_version_id}/modules`, { headers: auth(bm.token), data: { title: `E2E module ${RUN}` } })).json();
  await request.post(`/api/v1/curriculum-modules/${module.data.module_id}/topics`, { headers: auth(bm.token), data: { title: `E2E topic ${RUN}` } });
  await page.reload();
  await page.getByRole("row", { name: /Professional Video Editing/ }).getByRole("button", { name: "Manage versions" }).click().catch(() => undefined);
  await expect(page.getByText("Before you submit")).toBeVisible();
  for (const step of ["Modules", "Topic details", "Hours", "Completion rules", "Required assessments"]) await expect(page.getByText(step, { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Submit for review" })).toBeDisabled();
  await expect(page.getByText(/Needs: /).first()).toBeVisible(); // incomplete topics are marked on their rows
  await expect(page.getByRole("button", { name: /^Move module .* down$/ }).first()).toBeVisible();

  await page.getByRole("button", { name: "Discard draft" }).first().click();
  await expect(page.getByRole("alertdialog").getByText(/cannot be undone|This cannot be undone/i)).toBeVisible();
  await page.getByRole("alertdialog").getByRole("button", { name: "Discard draft" }).click();
  await expect(page.getByRole("button", { name: "New draft" })).toBeVisible();
});

test("Reports: this month by default, every figure drills down, CSV downloads", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.bmGnt);
  await page.goto("/branch/reports");
  await expect(page.getByRole("heading", { level: 1, name: "Reports" })).toBeVisible();
  await expect(page.getByLabel("Period")).toHaveValue("this_month");
  await expect(page.getByRole("heading", { name: "Classes and attendance" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Last six months" })).toBeVisible();
  await page.getByLabel("Period").selectOption("custom");
  await expect(page.getByLabel("From")).toBeVisible();
  await page.getByLabel("Period").selectOption("last_month");
  await expect(page).toHaveURL(/period=last_month/);
  await page.getByLabel("Period").selectOption("this_month");

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download CSV" }).click();
  await page.getByRole("menuitem", { name: "Figures" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/report-.*\.csv$/);

  await page.getByRole("link", { name: /Certificates issued/ }).click();
  await expect(page).toHaveURL(/\/branch\/completion\?.*stage=issued/);
});

test("the new screens fit a phone @mobile", async ({ page }) => {
  await login(page, USERS.bmGnt);
  for (const path of ["/branch/issues", "/branch/completion", "/branch/attendance", "/branch/support", "/branch/content", "/branch/results", "/branch/recordings", "/branch/reports", "/branch/curriculum"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await page.waitForTimeout(800);
    await noHorizontalScroll(page);
  }
});
