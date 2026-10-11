import { expect, test, type APIRequestContext } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * UX phase U10: Class Materials, My Progress and Certificates. Needs a freshly seeded dev database
 * (`create-dev-db --yes && seed-dev`); the flows change data, so re-seed before a re-run.
 */

test.describe.configure({ mode: "serial" });

const token = async (request: APIRequestContext, loginId: string) => {
  const response = await request.post("/api/v1/auth/login", { data: { login: loginId, password: PASSWORD } });
  return { Authorization: `Bearer ${(await response.json()).data.token}` };
};

test("Class Materials: recordings and files in tabs, one access line per course, the rules folded away", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.getByRole("link", { name: "Class Materials" }).first().click();
  await expect(page).toHaveURL(/\/materials$/);
  await expect(page.getByRole("heading", { level: 1, name: "Class Materials" })).toBeVisible();

  // the five old student items are gone from the nav, the two merged ones are there
  const nav = page.getByRole("navigation").first();
  for (const gone of ["Recordings", "Resources", "Attendance", "Results"]) await expect(nav.getByRole("link", { name: gone, exact: true })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "My Progress" })).toBeVisible();

  await expect(page.getByRole("tab", { name: /Recordings/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText(/Available until \d{1,2} \w{3} \d{4}/).first()).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /Data Science & Applied AI Combo/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Watch" }).first()).toBeVisible();

  await page.getByRole("tab", { name: /Files/ }).click();
  await expect(page).toHaveURL(/tab=files/);
  await expect(page.getByRole("button", { name: "Open", exact: true }).first()).toBeVisible();

  // the policy lives in the folded section
  const rules = page.getByRole("button", { name: "How access works" });
  await expect(page.getByText(/one extension, up to the second anniversary/)).toBeHidden();
  await rules.click();
  await expect(page.getByText(/one extension, up to the second anniversary/)).toBeVisible();
});

test("My Progress: what to do next, request recovery only on absent rows, report a mistake and see the request on the row", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.getByRole("link", { name: "My Progress" }).first().click();
  await expect(page).toHaveURL(/\/progress$/);
  await expect(page.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "What to do next" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Request recovery" })).toBeVisible(); // the seed has an absence with no recovery

  await page.getByRole("tab", { name: "Attendance" }).click();
  await expect(page).toHaveURL(/tab=attendance/);
  // only an absent row without a recovery offers it
  const recoverable = page.getByRole("row", { name: /Cleaning messy data/ });
  await expect(recoverable.getByRole("button", { name: "Request recovery" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Request recovery" })).toHaveCount(1);
  await expect(page.getByRole("row", { name: /Linear regression intuition/ }).getByRole("button", { name: "Request recovery" })).toHaveCount(0);

  // report a mistake from the row menu
  const present = page.getByRole("row", { name: /Track 1 revision/ });
  await present.getByRole("button", { name: /More actions for/ }).click();
  await page.getByRole("menuitem", { name: "Report a mistake" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("It should say").selectOption("Late");
  await dialog.getByLabel("Reason").fill("I joined ten minutes late");
  await dialog.getByRole("button", { name: "Send request" }).click();
  await expect(page.getByText("Report sent")).toBeVisible();
  await expect(present).toContainText("Mistake report");
  await expect(present).toContainText("Waiting for a decision");
  await expect(present).toContainText("Your Branch Manager decides");

  // while it waits, the menu item is off
  await present.getByRole("button", { name: /More actions for/ }).click();
  await expect(page.getByRole("menuitem", { name: "Report a mistake" })).toHaveAttribute("aria-disabled", "true");
  await page.keyboard.press("Escape");

  // asking for the recovery turns the button into a status
  await recoverable.getByRole("button", { name: "Request recovery" }).click();
  await page.getByRole("dialog").getByLabel("Reason").fill("I was unwell");
  await page.getByRole("dialog").getByRole("button", { name: "Request recovery" }).click();
  await expect(recoverable).toContainText("Requested");
  await expect(recoverable.getByRole("button", { name: "Request recovery" })).toHaveCount(0);
});

test("My Progress, Results: a row opens the assignment or test it came from", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await login(page, USERS.student);
  await page.goto("/results"); // the old address opens the Results tab
  await expect(page).toHaveURL(/\/progress\?tab=results/);
  await expect(page.getByRole("tab", { name: "Results" })).toHaveAttribute("aria-selected", "true");
  const row = page.getByRole("row", { name: /Python Foundations module test/ });
  await expect(row).toContainText("42.00 / 50.00");
  await row.getByRole("link", { name: "See feedback" }).click();
  await expect(page).toHaveURL(/\/tests\/\d+/);
});

test("Certificates: the tracker follows the course to Issued, then the PDF downloads and the verification link copies", async ({
  page,
  request,
  context,
}, info) => {
  test.skip(info.project.name === "mobile", "desktop flow");
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await login(page, USERS.student);
  await page.goto("/certificates");
  const card = page.getByRole("listitem").filter({ hasText: "Data Science & Applied AI Combo" });
  await expect(card.getByRole("list", { name: "Certificate steps" })).toContainText("Course completed");
  await expect(card).toContainText("Finish the course to start your certificate");
  await expect(card.getByRole("button", { name: "Download PDF" })).toHaveCount(0);

  // the branch completes the course: the open recovery is finished, the trainer recommends, the Branch Manager decides
  const trainer = await token(request, USERS.trainerG1);
  const bm = await token(request, USERS.bmGnt);
  type Recovery = { recovery_id: number; student: { student_code: string } };
  const ofStudent = async (status: string): Promise<Recovery[]> =>
    ((await (await request.get(`/api/v1/attendance/recoveries?status=${status}`, { headers: bm })).json()).data as Recovery[]).filter(
      (r) => r.student.student_code === USERS.student,
    );
  for (const r of await ofStudent("Requested")) {
    await request.post(`/api/v1/attendance/recoveries/${r.recovery_id}/decision`, { headers: bm, data: { decision: "Approved", target_date: "2026-10-16" } });
  }
  for (const r of await ofStudent("Approved")) {
    await request.post(`/api/v1/attendance/recoveries/${r.recovery_id}/completion`, { headers: trainer, data: { evidence_note: "Watched the recording" } });
  }
  const mine = await (await request.get("/api/v1/me/certificates", { headers: await token(request, USERS.student) })).json();
  const enrolmentId = mine.data.cards.find((c: { course: { title: string } }) => c.course.title.startsWith("Data Science")).enrolment.enrolment_id;
  const review = await (await request.post("/api/v1/completion-reviews", { headers: trainer, data: { enrolment_id: enrolmentId } })).json();
  await request.post(`/api/v1/completion-reviews/${review.data.review_id}/recommendation`, { headers: trainer, data: { recommendation: "Complete" } });
  const decided = await request.post(`/api/v1/completion-reviews/${review.data.review_id}/decision`, { headers: bm, data: { decision: "Complete" } });
  expect(decided.status()).toBe(200);

  // the seed's fee is unpaid: the screen says so and points to Fees
  await page.reload();
  await expect(page.getByRole("heading", { name: "Certificates" })).toBeVisible();
  await expect(page.getByText("A fee payment is holding your certificate")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open Fees & Receipts" })).toHaveAttribute("href", "/my-account?tab=fees");
  await expect(card).toContainText("In review");

  // the Founder releases the certificate despite the balance; the Branch Manager approves and issues it
  const founder = await token(request, USERS.founder);
  const certificateId = mine.data.cards.find((c: { course: { title: string } }) => c.course.title.startsWith("Data Science")).certificate.certificate_id;
  const asked = await request.post(`/api/v1/certificates/${certificateId}/financial-exception`, {
    headers: bm,
    data: { reason: "Scholarship letter pending in the CRM" },
  });
  const exception = (await asked.json()).data.exception_id;
  await request.post(`/api/v1/certificate-financial-exceptions/${exception}/decision`, { headers: founder, data: { decision: "Approved", note: "Released" } });
  expect((await request.post(`/api/v1/certificates/${certificateId}/approval`, { headers: bm })).status()).toBe(200);
  await page.reload();
  await expect(card).toContainText("Approved. Your branch will issue it next.");
  expect((await request.post(`/api/v1/certificates/${certificateId}/issue`, { headers: bm })).status()).toBe(200);

  await page.reload();
  await expect(card).toContainText(/Issued on \d{1,2} \w{3} \d{4}/);
  await expect(card).toContainText(/NIT-CERT-\d{4}-\d{6}/);
  const download = page.waitForEvent("download");
  await card.getByRole("button", { name: "Download PDF" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^NIT-CERT-\d{4}-\d{6}\.pdf$/);
  const path = await file.path();
  const bytes = (await import("node:fs")).readFileSync(path);
  expect(bytes.subarray(0, 4).toString()).toBe("%PDF");

  await card.getByRole("button", { name: "Copy verification link" }).click();
  await expect(page.getByText("Verification link copied")).toBeVisible();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toMatch(/\/verify\/NIT-CERT-\d{4}-\d{6}$/);
});

test("Class Materials, My Progress and Certificates fit a phone @mobile", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile", "phone layout only");
  await login(page, USERS.student);
  for (const path of ["/materials", "/materials?tab=files", "/progress", "/progress?tab=attendance", "/progress?tab=results", "/certificates"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForTimeout(500);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, path).toBeLessThanOrEqual(1);
  }
  // the phone bar keeps its four pinned items and the new ones sit under More
  await page.goto("/dashboard");
  await page.getByRole("navigation", { name: "Bottom" }).getByRole("button", { name: "More" }).click();
  const sheet = page.getByRole("dialog", { name: "More" });
  await expect(sheet.getByRole("link", { name: "Class Materials" })).toBeVisible();
  await expect(sheet.getByRole("link", { name: "My Progress" })).toBeVisible();
  await expect(sheet.getByRole("link", { name: "Certificates" })).toBeVisible();
});
