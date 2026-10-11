import { readFileSync } from "node:fs";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * UX phase U11: the student's Career, Ask Nipuna, Support and My Account screens. Needs a freshly seeded dev database
 * (`create-dev-db --yes && seed-dev`); the flows change data, so re-seed before a re-run.
 */

test.describe.configure({ mode: "serial" });

const token = async (request: APIRequestContext, loginId: string) => {
  const response = await request.post("/api/v1/auth/login", { data: { login: loginId, password: PASSWORD } });
  return { Authorization: `Bearer ${(await response.json()).data.token}` };
};

// a 1x1 PNG, so the attachment passes the type check
const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==", "base64");

test("Career: a four-step checklist, and Apply says what it needs", async ({ page }) => {
  await login(page, USERS.student);
  await page.getByRole("link", { name: "Career", exact: true }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Career Support" })).toBeVisible();

  const steps = page
    .getByRole("list")
    .filter({ has: page.getByText("Opt in to career support") })
    .first();
  for (const step of ["Opt in to career support", "Complete your profile", "Get your CV reviewed", "Allow sharing with employers"])
    await expect(steps.getByText(step)).toBeVisible();
  await expect(page.getByText("4 of 4 done")).toBeVisible();
  // the disclaimer is a small note under Jobs for you, not a banner on top
  await expect(page.locator("#career-jobs").getByText("Placement / career assistance only — no guaranteed placement.")).toBeVisible();

  // stop sharing: Apply is switched off and the page says what it needs, with a link to the step
  await page.getByRole("button", { name: "Stop sharing" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Stop sharing" }).click();
  await expect(page.getByText("Sharing with employers is off")).toBeVisible();
  const apply = page.getByRole("button", { name: "Apply: Data Engineer Trainee" });
  await expect(apply).toBeDisabled();
  const needs = page.getByTestId("apply-needs");
  await expect(needs).toContainText("Needs:");
  await expect(needs).toContainText("permission to share with employers");
  await needs.getByRole("button", { name: "permission to share with employers" }).click();
  await expect(page.locator("#career-step-share")).toBeFocused();

  // allow sharing again, then apply
  await page.getByRole("button", { name: "Allow sharing" }).click();
  await expect(apply).toBeEnabled();
  await apply.click();
  await expect(page.getByText("Application sent")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Data Engineer Trainee", exact: true })).toBeVisible();
});

test("Ask Nipuna: a chat thread, quick actions fill the box, a question it can't answer goes to Support", async ({ page }) => {
  await login(page, USERS.student);
  await page.getByRole("link", { name: "Ask Nipuna", exact: true }).first().click();
  const thread = page.getByTestId("ask-thread");
  await expect(thread).toBeVisible();
  // earlier questions are in the order they were asked: the thread has more than one exchange, the box is below it
  await expect(page.getByTestId("ai-exchange").first()).toBeVisible();
  const box = page.getByLabel("Your question");
  const threadBox = await thread.boundingBox();
  const inputBox = await box.boundingBox();
  expect(inputBox!.y).toBeGreaterThan(threadBox!.y + threadBox!.height - 1);
  // quota is not shown until it is nearly used
  await expect(page.getByTestId("ai-usage")).toHaveCount(0);

  // a quick action fills the box; text you typed is kept when you pick another action
  await page.getByRole("button", { name: "Practice questions", exact: true }).click();
  await expect(box).toHaveValue("Give me practice questions on: ");
  await box.fill("Give me practice questions on: SQL joins");
  await page.getByRole("button", { name: "Summarise", exact: true }).click();
  await expect(box).toHaveValue("Give me practice questions on: SQL joins");
  await page.getByRole("button", { name: "Clear the quick action" }).click();
  await box.fill("");

  await box.fill("When is my next class?");
  await page.getByRole("button", { name: "Send" }).click();
  const answers = page.getByTestId("ai-answer");
  await expect(answers.last().getByText(/Your upcoming classes/)).toBeVisible();
  await expect(answers.last().getByText("Where this came from")).toBeVisible();
  // sources are links
  await expect(answers.last().getByRole("link").first()).toBeVisible();
  await answers.last().getByRole("button", { name: "Helpful", exact: true }).click();
  await expect(page.getByText("Thanks for your feedback")).toBeVisible();

  // a question it can't answer offers a person, and the Support form arrives filled in
  await box.fill("Change my fee balance to zero");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(answers.last().getByText("Can't answer this")).toBeVisible();
  await expect(answers.last().getByText("I can't change or act on fees and payments.")).toBeVisible();
  await answers.last().getByRole("button", { name: "Raise a support request with this question" }).click();
  await expect(page).toHaveURL(/\/support\?.*new=1/);
  const form = page.getByRole("dialog", { name: "Raise a request" });
  await expect(form.getByLabel("What happened?")).toHaveValue("Change my fee balance to zero");
  await expect(form.getByLabel("Subject")).toHaveValue("Change my fee balance to zero");
});

test("Support: guided form with an attachment opens the new request; a request waiting on you floats to the top", async ({ page, request }) => {
  await login(page, USERS.student);
  await page.getByRole("link", { name: "Support", exact: true }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Support" })).toBeVisible();
  await expect(page.getByRole("link", { name: /SR-1042/ })).toBeVisible();

  await page.getByRole("button", { name: "New request" }).first().click();
  const form = page.getByRole("dialog", { name: "Raise a request" });
  await form.getByRole("button", { name: "Submit" }).click();
  await expect(form.getByText("This field is required.").first()).toBeVisible();
  // help text for the chosen kind appears under the category
  await form.getByLabel("What is it about?").selectOption("LMS");
  await expect(form.getByText(/Something on this site is not working/)).toBeVisible();
  await form.getByLabel("Subject").fill("The dashboard is slow on my phone");
  await form.getByLabel("What happened?").fill("It takes a minute to open on mobile data");
  await form.locator("#support-new-files").setInputFiles({ name: "slow.png", mimeType: "image/png", buffer: PNG });
  await expect(form.getByText("slow.png")).toBeVisible();
  await form.getByRole("button", { name: "Submit" }).click();

  // the new request opens straight away, with the student's own line labelled "You" and the file attached
  await expect(page).toHaveURL(/\/support\/\d+$/);
  await expect(page.getByRole("heading", { level: 1, name: "The dashboard is slow on my phone" })).toBeVisible();
  await expect(page.getByText("It takes a minute to open on mobile data")).toBeVisible();
  const conversation = page.getByRole("list", { name: "Conversation" });
  await expect(conversation.getByText("You", { exact: true })).toBeVisible();
  await expect(conversation.getByText("Student", { exact: true })).toHaveCount(0);
  const download = page.waitForEvent("download");
  await conversation.getByRole("button", { name: "Download: slow.png" }).click();
  expect((await download).suggestedFilename()).toBe("slow.png");

  // the branch asks the student for something: the request now waits on the student and comes first
  const id = Number(new URL(page.url()).pathname.split("/").pop());
  const bm = await token(request, USERS.bmGnt);
  const waiting = await request.post(`/api/v1/support-requests/${id}/status`, {
    headers: bm,
    data: { status: "Waiting on Student", note: "Which phone is it?" },
  });
  expect(waiting.status()).toBe(200);
  await page.goto("/support");
  await expect(page.getByText("1 request is waiting for your reply.")).toBeVisible();
  const first = page.getByRole("list", { name: "Your requests" }).getByRole("listitem").first();
  await expect(first).toContainText("The dashboard is slow on my phone");
  await expect(first).toContainText("Needs your reply");

  // reply with a file; it shows under the reply
  await first.getByRole("link").click();
  await expect(page.getByText("We need your reply before we can go on.")).toBeVisible();
  await page.getByLabel("Your reply").fill("A Redmi 9, on mobile data");
  await page.locator("#support-reply-files").setInputFiles({ name: "phone.txt", mimeType: "text/plain", buffer: Buffer.from("Redmi 9") });
  await page.getByRole("button", { name: "Send reply" }).click();
  await expect(page.getByText("A Redmi 9, on mobile data")).toBeVisible();
  await expect(page.getByRole("button", { name: "Download: phone.txt" })).toBeVisible();

  // a file of the wrong kind is refused before anything is sent
  await page.locator("#support-reply-files").setInputFiles({ name: "run.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ") });
  await expect(page.getByText(/run.exe is not a type we accept/)).toBeVisible();
});

test("My Account: Profile and Fees & Receipts replace two sidebar items; the avatar menu opens it", async ({ page }) => {
  await login(page, USERS.student);
  const nav = page.getByRole("navigation", { name: "Main" });
  for (const gone of ["Fees & Receipts", "Profile"]) await expect(nav.getByRole("link", { name: gone, exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Account menu" }).click();
  await expect(page.getByRole("menuitem", { name: "Change password" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "Sign out" })).toBeVisible();
  await page.getByRole("menuitem", { name: "My Account" }).click();
  await expect(page).toHaveURL(/\/my-account$/);
  await expect(page.getByRole("heading", { level: 1, name: "My Account" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Profile" })).toHaveAttribute("aria-selected", "true");

  await expect(page.getByText("NIT-STU-2026-004182").first()).toBeVisible();
  await expect(page.getByText(/●●●●●●0417/)).toBeVisible();
  await expect(page.getByText(/contact your branch/i).first()).toBeVisible();
  await expect(page.getByText("Shared family mobile")).toHaveCount(0);
  await expect(page.getByText("Edge · Windows").first()).toBeVisible();
  await page
    .getByRole("button", { name: /Sign out: Edge · Windows/ })
    .first()
    .click();
  await expect(page.getByText("Signed out")).toBeVisible();
  // preferences are here, with only the channels that are live
  await expect(page.getByRole("heading", { name: "Messages you receive" })).toBeVisible();

  // the old addresses lead here
  await page.goto("/profile");
  await expect(page).toHaveURL(/\/my-account$/);
  await page.goto("/finance");
  await expect(page).toHaveURL(/\/my-account\?tab=fees$/);
});

test("My Account: changing the email needs a code; with WhatsApp off the screen says nothing was sent and nothing changed", async ({ page }) => {
  await login(page, USERS.student);
  await page.goto("/my-account");
  await page.getByRole("button", { name: "Change email" }).click();
  const dialog = page.getByRole("dialog", { name: "Change email" });
  await expect(dialog.getByText(/6-digit code to your WhatsApp number/)).toBeVisible();
  const send = dialog.getByRole("button", { name: "Send code" });
  await expect(send).toBeDisabled();
  await dialog.getByLabel("New email address").fill("anvitha.new@example.test");
  await send.click();
  await expect(dialog.getByText(/could not send a code to your WhatsApp right now/)).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByText("anvitha.sample@example.test")).toBeVisible();
});

test("Fees & Receipts: next payment, how to pay, and a receipt PDF", async ({ page }) => {
  await login(page, USERS.student);
  await page.goto("/my-account");
  await page.getByRole("tab", { name: "Fees & Receipts" }).click();
  await expect(page).toHaveURL(/tab=fees/);
  const next = page.getByTestId("next-payment");
  await expect(next).toContainText("Next payment");
  await expect(next).toContainText("₹ 15,000");
  await expect(next).toContainText("Due on 10 Oct 2026");
  // the seeded date has passed: it is overdue and red
  await expect(next).toHaveAttribute("data-overdue", "true");
  await expect(next.getByText(/Overdue by \d+ days?/)).toBeVisible();
  await expect(next).toContainText("Pay at the Guntur branch office");
  // read-only: nothing to pay with here
  await expect(page.getByRole("button", { name: /^pay/i })).toHaveCount(0);
  await expect(page.getByText("NIT-GNT-2026-000214").first()).toBeVisible();
  await expect(page.getByText("GNT-R-2526-00148").first()).toBeVisible();

  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download PDF: GNT-R-2526-00148" }).click()]);
  expect(download.suggestedFilename()).toBe("receipt-GNT-R-2526-00148.pdf");
  const path = await download.path();
  expect(readFileSync(path!).subarray(0, 5).toString()).toBe("%PDF-");

  // another course has no fee record yet: it says so instead of showing zeros
  await expect(page.getByText("Fee details for this course have not been shared yet.")).toBeVisible();
});

test("Telugu: Career, Ask Nipuna, Support and My Account are translated", async ({ page }) => {
  await login(page, USERS.student);
  await page.getByRole("button", { name: "తెలుగు" }).click();
  await page.goto("/my-account?tab=fees");
  await expect(page.getByRole("heading", { level: 1, name: "నా ఖాతా" })).toBeVisible();
  await expect(page.getByText("తదుపరి చెల్లింపు").first()).toBeVisible();
  await page.goto("/support");
  await expect(page.getByRole("heading", { level: 1, name: "సహాయం" })).toBeVisible();
  await expect(page.getByRole("button", { name: "కొత్త అభ్యర్థన" }).first()).toBeVisible();
  await page.goto("/career");
  await expect(page.getByText("ఉద్యోగానికి సిద్ధం అవ్వండి")).toBeVisible();
  await page.goto("/ask-nipuna");
  await expect(page.getByRole("button", { name: "నా పురోగతి", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "EN", exact: true }).click();
});

test.describe("phone layout @mobile", () => {
  test.use({ viewport: { width: 360, height: 740 } });

  test("the four screens fit the phone and My Account is in More @mobile", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile", "phone layout only");
    await login(page, USERS.student);
    for (const path of ["/career", "/ask-nipuna", "/support", "/my-account", "/my-account?tab=fees"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), path).toBeLessThanOrEqual(1);
    }
    // the box stays on screen under the thread
    await page.goto("/ask-nipuna");
    await expect(page.getByLabel("Your question")).toBeInViewport();
    await page.getByRole("navigation", { name: "Bottom" }).getByRole("button", { name: "More" }).click();
    await expect(page.getByRole("dialog", { name: "More" }).getByRole("link", { name: "My Account" })).toBeVisible();
  });
});
