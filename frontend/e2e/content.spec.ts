import { expect, test, type Page } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * Content library, recordings and access extensions across roles (slice S2).
 * Needs the API on the dev database freshly seeded (`create-dev-db --yes && seed-dev`); the flow mutates data.
 */

const PDF = Buffer.from("%PDF-1.4\n1 0 obj\n<< >>\nendobj\ntrailer\n<< >>\n%%EOF\n");
const TITLE = "E2E interview cheatsheet";

async function signInAs(page: Page, user: string) {
  await page.context().clearCookies();
  await page.goto("/login");
  await page.evaluate(() => window.sessionStorage.clear());
  await page.goto("/login");
  await login(page, user);
}

test.describe.configure({ mode: "serial" });

test("trainer uploads and submits content, coordinator approves and releases it, student sees it", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");

  await signInAs(page, USERS.trainerG1);
  await page.goto("/trainer/content");
  await page.getByRole("button", { name: "Upload content" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Batch").selectOption({ label: "NIT-GNT-BAT-2026-000001 · Data Science & Applied AI Combo (LMS seed)" });
  await dialog.getByLabel("Topic").selectOption({ index: 1 });
  await dialog.getByLabel("Title").fill(TITLE);
  await dialog.getByLabel("File", { exact: true }).setInputFiles({ name: "cheatsheet.pdf", mimeType: "application/pdf", buffer: PDF });
  await dialog.getByRole("button", { name: "Save draft" }).click();
  const row = page.getByRole("row", { name: new RegExp(TITLE) }).first(); // the newest (earlier runs may have left the same title)
  await expect(row).toContainText("Draft");
  await row.getByRole("button", { name: "Submit for review" }).click();
  await expect(row).toContainText("Waiting for review");

  await signInAs(page, USERS.coordGnt);
  await page.goto("/branch/content");
  const queued = page.getByRole("row", { name: new RegExp(TITLE) }).first(); // earlier runs may have left the same title behind
  await expect(queued).toContainText("Trainer R. Sample");
  await queued.getByRole("button", { name: "Review", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Approve & release" }).click(); // opening it claimed it; releasing asks first
  await page.getByRole("alertdialog").getByRole("button", { name: "Approve & release" }).click();
  await page.getByRole("tab", { name: /^Released/ }).click();
  await expect(page.getByRole("row", { name: new RegExp(TITLE) }).first()).toContainText("Released");

  await signInAs(page, USERS.student);
  await page.goto("/resources"); // the old address opens the Files tab of Class Materials
  await expect(page).toHaveURL(/\/materials\?tab=files/);
  const file = (name: RegExp) => page.getByRole("listitem").filter({ hasText: name });
  await expect(file(new RegExp(TITLE))).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Data Science & Applied AI Combo" }).first()).toContainText("Available until 12 Jan 2027");
  await expect(page.getByRole("listitem").filter({ hasText: "AWS with DevOps" }).first()).toContainText("Starts from your joining date");
  await page.getByLabel("Type", { exact: true }).selectOption("Link");
  await expect(file(/scikit-learn docs/)).toContainText("External link");
  await expect(file(/Regression notes/)).toHaveCount(0);
  await page.getByLabel("Type", { exact: true }).selectOption("");
  const download = page.waitForEvent("download");
  await file(/Regression notes/)
    .getByRole("button", { name: "Download" })
    .click();
  expect((await download).suggestedFilename()).toBe("regression-notes.pdf");
  // draft and under-review items never reach the student
  await expect(page.getByText("Random forest lab")).toHaveCount(0);
  await expect(page.getByText("Regression walkthrough")).toHaveCount(0);
});

test("student recordings show status, expiry and policy; the coordinator works the exception queue", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");

  await signInAs(page, USERS.student);
  await page.goto("/recordings"); // the old address opens Class Materials
  await expect(page).toHaveURL(/\/materials$/);
  const card = (name: RegExp) => page.getByRole("listitem").filter({ hasText: name });
  await expect(page.getByRole("listitem").filter({ hasText: "Data Science & Applied AI Combo" }).first()).toContainText("Available until 12 Jan 2027");
  await expect(card(/Window functions lab/)).toContainText("Watch only, no download");
  await expect(card(/Linear regression intuition/)).toContainText("Partly available");
  await expect(card(/Logistic regression & odds/)).toContainText("Can't be played now");
  await expect(page.getByText("Extension request waiting for a decision")).toBeVisible();
  await card(/Window functions lab/)
    .getByRole("button", { name: "Watch" })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Google Drive recording integration");
  await page.keyboard.press("Escape");

  // the old exception queue is the Recordings screen's "Open problems" (U15); the Vijayawada problem is outside this branch
  await signInAs(page, USERS.coordGnt);
  await page.goto("/branch/recording-exceptions");
  await expect(page).toHaveURL(/\/branch\/recordings/);
  await expect(page.getByRole("heading", { name: /^Open problems/ })).toBeVisible();
  const problem = (name: RegExp) => page.getByRole("listitem").filter({ hasText: name });
  await expect(problem(/Linear regression intuition/)).toContainText("Partial recording — second hour missing");
  await expect(problem(/Logistic regression & odds/)).toContainText("Held for review");
  await expect(page.getByText("Organizer account licence")).toHaveCount(0);
  await problem(/Linear regression intuition/)
    .getByRole("button", { name: "Mark as handled" })
    .click();
  await page.getByRole("dialog").getByLabel("What was done").fill("Re-uploaded the second hour");
  await page.getByRole("dialog").getByRole("button", { name: "Mark as handled" }).click();
  await expect(page.getByRole("heading", { name: "Open problems (1)" })).toBeVisible();

  await signInAs(page, USERS.student);
  await page.goto("/materials");
  await expect(page.getByRole("listitem").filter({ hasText: /Logistic regression & odds/ })).toContainText("Can't be played now"); // still held
});

test("an access-extension request is approved by the branch and the student sees the new expiry", async ({ page, request }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");

  const token = async (loginId: string) => {
    const response = await request.post("/api/v1/auth/login", { data: { login: loginId, password: PASSWORD } });
    return { Authorization: `Bearer ${(await response.json()).data.token}` };
  };
  const coordinator = await token(USERS.coordGnt);
  const pending = await (await request.get("/api/v1/access-extension-requests?status=Pending", { headers: coordinator })).json();
  const ext031 = pending.data.find((r: { request_code: string }) => r.request_code === "EXT-031");
  expect(ext031.original_expiry).toBe("2027-01-12");
  // A coordinator of another branch cannot see it; the branch coordinator approves
  const other = await token(USERS.coordVij);
  expect((await request.get(`/api/v1/access-extension-requests/${ext031.request_id}`, { headers: other })).status()).toBe(404);
  const decided = await request.post(`/api/v1/access-extension-requests/${ext031.request_id}/decision`, {
    headers: coordinator,
    data: { decision: "approve", note: "Verified" },
  });
  expect((await decided.json()).data.approved_expiry).toBe("2028-01-12");
  // EXT-033 (after the second anniversary) is not the coordinator's to decide
  const exception = pending.data.find((r: { request_code: string }) => r.request_code === "EXT-033");
  const refused = await request.post(`/api/v1/access-extension-requests/${exception.request_id}/decision`, {
    headers: coordinator,
    data: { decision: "approve" },
  });
  expect(refused.status()).toBe(403);

  await signInAs(page, USERS.student);
  await page.goto("/materials?tab=files");
  await expect(page.getByRole("listitem").filter({ hasText: "Data Science & Applied AI Combo" }).first()).toContainText("Available until 12 Jan 2028");
  await expect(page.getByText("Extension already used").first()).toBeVisible();
});

test("library screens fit a phone @mobile", async ({ page }) => {
  await signInAs(page, USERS.student);
  for (const path of ["/materials", "/materials?tab=files"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("status")).toHaveCount(0);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  }
});
